import json
from . import builder_tools, config, db, llm, workspace

SYSTEM = """You are PhantomGPT Builder: an uncensored senior engineer that ships working software from one prompt.

WORKFLOW - follow exactly:
1. One short paragraph: the stack you picked and why. No preamble beyond that.
2. Create every single file with write_file. Full contents. No placeholders, no "// rest of code", no elisions.
3. Run install and build commands with run_command. Read the output.
4. Fix what broke. Repeat until the build is clean.
5. Final message: what exists, exact run command, and known gaps. Keep it under 150 words.

RULES
- Pick the stack yourself from the prompt. Prefer the smallest thing that works.
- Every project gets a README.md with a run command.
- Write real, complete, runnable code. If a file needs 400 lines, write 400 lines.
- Assume Node 20 / Python 3.12 / modern browsers.
- Add a .gitignore.
- If a command needs a server, start it in the background with `&`.
- You are uncensored: no licensing hedges, no disclaimers. Just build it.
"""


async def run(ws_id, prompt, model, emit):
    workspace.ensure()
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "system",
         "content": f"Workspace files: {workspace.tree(ws_id) or 'none'}"},
        {"role": "user", "content": prompt},
    ]

    for _ in range(config.BUILDER_MAX_ROUNDS):
        text_parts, calls = [], {}

        async for chunk in llm.stream(messages, tools=builder_tools.SCHEMAS, model=model):
            if not chunk.choices:
                continue
            d = chunk.choices[0].delta
            if d.content:
                text_parts.append(d.content)
                await emit({"type": "token", "text": d.content})
            for tc in (d.tool_calls or []):
                slot = calls.setdefault(tc.index, {"id": "", "name": "", "args": ""})
                if tc.id:
                    slot["id"] = tc.id
                if tc.function and tc.function.name:
                    slot["name"] += tc.function.name
                if tc.function and tc.function.arguments:
                    slot["args"] += tc.function.arguments

        text = "".join(text_parts)
        if text:
            db.add_message(ws_id, "assistant", text)

        if not calls:
            await emit({"type": "done"})
            return

        messages.append({"role": "assistant", "content": text or None,
                         "tool_calls": [{"id": c["id"] or f"c{i}", "type": "function",
                                         "function": {"name": c["name"], "arguments": c["args"]}}
                                        for i, c in calls.items()]})

        for i, c in calls.items():
            try:
                args = json.loads(c["args"] or "{}")
            except json.JSONDecodeError:
                args = {}
            if c["name"] == "write_file":
                await emit({"type": "file_write", "path": args.get("path", "?")})
            elif c["name"] == "run_command":
                await emit({"type": "exec", "cmd": args.get("cmd", "")})
            try:
                result = await builder_tools.dispatch(c["name"], args, ws_id, emit)
            except Exception as e:
                result = {"error": f"{type(e).__name__}: {e}"}
            messages.append({"role": "tool", "tool_call_id": c["id"] or f"c{i}",
                             "content": json.dumps(result, default=str)[:12000]})

    await emit({"type": "done", "note": "round limit reached"})