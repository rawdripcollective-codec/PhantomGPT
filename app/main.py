import asyncio, json, os, re
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import (builder, cards, config, db, evidence, findings, llm, personas,
               preflight, report, scope, terminal, tools, workspace)
from .net import egress, fingerprint, leaks, scrub, ss_uri
from .personas import GROUNDING

app = FastAPI(title="PhantomGPT")
db.init()
workspace.ensure()

HERE = os.path.dirname(__file__)
app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")), name="static")


@app.middleware("http")
async def hygiene(request, call_next):
    resp = await call_next(request)
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    if request.url.path == "/" or request.url.path.startswith("/api"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


class NewChat(BaseModel):
    persona: str = personas.DEFAULT
    title: str = "New session"


class ChatIn(BaseModel):
    chat_id: int
    message: str
    use_tools: bool = config.TOOLS_DEFAULT


class BuildIn(BaseModel):
    ws_id: int
    prompt: str
    model: str | None = None


class ExecIn(BaseModel):
    cmd: str


def sse(obj):
    return f"data: {json.dumps(obj, default=str)}\n\n"


def build_context(chat):
    msgs = [{"role": "system", "content": personas.PERSONAS[chat["persona"]][1] + GROUNDING}]
    for m in db.get_messages(chat["id"]):
        if m["role"] == "user":
            msgs.append({"role": "user", "content": m["content"]})
        elif m["role"] == "assistant" and m["content"]:
            msgs.append({"role": "assistant", "content": m["content"]})
        elif m["role"] == "tool":
            tid = f'{m["tool_name"]}{m["id"]}'
            msgs.append({"role": "assistant", "content": None,
                         "tool_calls": [{"id": tid, "type": "function",
                                         "function": {"name": m["tool_name"],
                                                      "arguments": m["tool_args"]}}]})
            msgs.append({"role": "tool", "tool_call_id": tid,
                         "content": m["tool_result"]})
    return msgs


@app.get("/")
async def index():
    return FileResponse(os.path.join(HERE, "static", "index.html"))


@app.get("/api/personas")
async def get_personas():
    return [{"id": k, "label": v[0]} for k, v in personas.PERSONAS.items()]


@app.get("/api/tools")
async def get_tools():
    return [s["function"]["name"] for s in tools.SCHEMAS]


@app.get("/api/status")
async def status():
    return {"model": config.MODEL, "preflight": config.PREFLIGHT, "scope": scope.summary(),
            "providers": {"shodan": bool(config.SHODAN_KEY),
                          "censys": bool(config.CENSYS_ID and config.CENSYS_SECRET),
                          "dehashed": bool(config.DEHASHED_EMAIL and config.DEHASHED_KEY)}}


# ---------- chats ----------

@app.get("/api/chats")
async def list_chats():
    return db.list_chats()


@app.post("/api/chats")
async def new_chat(body: NewChat):
    if body.persona not in personas.PERSONAS:
        raise HTTPException(400, "unknown persona")
    return {"id": db.create_chat(body.title, body.persona)}


@app.get("/api/chats/{cid}")
async def get_chat(cid: int):
    chat = db.get_chat(cid)
    if not chat:
        raise HTTPException(404, "no such chat")
    return {"chat": chat, "messages": db.get_messages(cid)}


@app.delete("/api/chats/{cid}")
async def del_chat(cid: int):
    db.delete_chat(cid)
    return {"ok": True}


@app.post("/api/chat")
async def chat(body: ChatIn):
    chat_row = db.get_chat(body.chat_id)
    if not chat_row:
        raise HTTPException(404, "no such chat")

    db.rename_if_default(body.chat_id, body.message)
    db.add_message(body.chat_id, "user", body.message)

    async def gen():
        messages = build_context(chat_row)
        schemas = tools.SCHEMAS if body.use_tools else None

        if body.use_tools and config.PREFLIGHT:
            for tool_name, args in preflight.plan(body.message, config.PREFLIGHT_BUDGET):
                if tool_name == "__scope__":
                    yield sse({"type": "preflight", "name": "scope",
                               "args": {"host": args["host"], "note": "out of scope"}})
                    continue
                yield sse({"type": "preflight", "name": tool_name, "args": args})
                result = await tools.dispatch(tool_name, args, chat_id=body.chat_id)
                meta = evidence.record(body.chat_id, tool_name, str(args)[:200], result)
                payload = json.dumps(result, default=str)[:20000]
                db.add_message(body.chat_id, "tool", tool_name=tool_name,
                               tool_args=json.dumps(args), tool_result=payload)
                yield sse({"type": "preflight_result", "name": tool_name,
                           "ev_id": meta["ev_id"], "result": payload[:6000]})
            if db.get_evidence(body.chat_id):
                messages.insert(1, {"role": "system",
                                    "content": evidence.digest_block(db.get_evidence(body.chat_id))})

        for _ in range(config.MAX_TOOL_ROUNDS + 1):
            text_parts, calls = [], {}
            async for chunk in llm.stream(messages, tools=schemas):
                if not chunk.choices:
                    continue
                d = chunk.choices[0].delta
                if d.content:
                    text_parts.append(d.content)
                    yield sse({"type": "token", "text": d.content})
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
                db.add_message(body.chat_id, "assistant", text)
            if not calls:
                yield sse({"type": "done"})
                return

            messages.append({"role": "assistant", "content": text or None,
                             "tool_calls": [{"id": c["id"] or f"call_{i}", "type": "function",
                                             "function": {"name": c["name"], "arguments": c["args"]}}
                                            for i, c in calls.items()]})

            for i, c in calls.items():
                try:
                    args = json.loads(c["args"] or "{}")
                except json.JSONDecodeError:
                    args = {}
                yield sse({"type": "tool_call", "name": c["name"], "args": args})
                result = await tools.dispatch(c["name"], args, chat_id=body.chat_id)
                meta = evidence.record(body.chat_id, c["name"], str(args)[:200], result)
                payload = json.dumps(result, default=str)[:20000]
                db.add_message(body.chat_id, "tool", tool_name=c["name"],
                               tool_args=json.dumps(args), tool_result=payload)
                messages.append({"role": "tool", "tool_call_id": c["id"] or f"call_{i}",
                                 "content": payload})
                yield sse({"type": "tool_result", "name": c["name"],
                           "ev_id": meta["ev_id"], "result": payload[:6000]})

        yield sse({"type": "done"})

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"X-Accel-Buffering": "no", "Cache-Control": "no-store"})


# ---------- findings ----------

@app.get("/api/chats/{cid}/findings")
async def list_findings(cid: int):
    return findings.sort(db.get_findings(cid))


@app.post("/api/findings/{fid}")
async def patch_finding(fid: int, body: dict):
    db.update_finding(fid, **{k: v for k, v in body.items()
                              if k in ("status", "notes", "severity")})
    return {"ok": True}


@app.delete("/api/findings/{fid}")
async def rm_finding(fid: int):
    db.delete_finding(fid)
    return {"ok": True}


# ---------- export ----------

@app.get("/api/export/{cid}")
async def export(cid: int, fmt: str = "pdf"):
    chat = db.get_chat(cid)
    if not chat:
        raise HTTPException(404, "no such chat")
    payload = {"chat": chat, "messages": db.get_messages(cid),
               "evidence": db.get_evidence(cid),
               "findings": findings.sort(db.get_findings(cid))}
    if fmt == "json":
        return Response(json.dumps(payload, indent=2, default=str),
                        media_type="application/json")
    if fmt == "md":
        return Response(report.markdown(payload), media_type="text/markdown")
    return Response(report.pdf(payload), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="report-{cid}.pdf"'})


# ---------- builder ----------

@app.get("/api/builder/models")
async def builder_models():
    return {"models": config.BUILDER_MODELS, "default": config.BUILDER_MODEL,
            "shell": config.ALLOW_SHELL}


@app.post("/api/workspaces")
async def new_workspace(body: dict):
    name = (body.get("name") or "untitled")[:60]
    ws_id = db.create_chat(name, "builder")
    workspace.ensure()
    workspace.base(ws_id).mkdir(parents=True, exist_ok=True)
    return {"id": ws_id, "name": name}


@app.get("/api/workspaces/{ws_id}/files")
async def list_files(ws_id: int):
    return {"files": workspace.tree(ws_id)}


@app.get("/api/workspaces/{ws_id}/file")
async def get_file(ws_id: int, path: str):
    return {"path": path, "content": workspace.read(ws_id, path)}


@app.put("/api/workspaces/{ws_id}/file")
async def put_file(ws_id: int, body: dict):
    workspace.write(ws_id, body["path"], body.get("content", ""))
    return {"ok": True}


@app.post("/api/workspaces/{ws_id}/exec")
async def exec_cmd(ws_id: int, body: ExecIn):
    async def gen():
        async for kind, text in terminal.run(ws_id, body.cmd):
            yield sse({"type": "preview" if kind == "url" else "exec_output",
                       **({"url": text} if kind == "url" else {"text": text})})
        yield sse({"type": "done"})
    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/api/workspaces/{ws_id}/download")
async def download(ws_id: int):
    return Response(workspace.zip_bytes(ws_id), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="workspace-{ws_id}.zip"'})


@app.get("/api/workspaces/{ws_id}/preview/{path:path}")
async def preview(ws_id: int, path: str):
    p = workspace.resolve(ws_id, path or "index.html")
    if not p.is_file():
        raise HTTPException(404, "not found")
    return FileResponse(p)


@app.post("/api/build")
async def build(body: BuildIn):
    db.rename_if_default(body.ws_id, body.prompt)
    db.add_message(body.ws_id, "user", body.prompt)

    async def gen():
        q = asyncio.Queue()

        async def emit(ev):
            await q.put(ev)

        task = asyncio.create_task(builder.run(body.ws_id, body.prompt,
                                               body.model or config.BUILDER_MODEL, emit))
        while True:
            ev = await q.get()
            yield sse(ev)
            if ev["type"] == "done":
                break
        await task

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"X-Accel-Buffering": "no"})


# ---------- cards ----------

@app.get("/api/cards/bins")
async def card_bins():
    return {"bins": cards.CATALOG_PUBLIC, "brands": list(cards.BRAND_SPECS),
            "live": {"stripe": bool(config.STRIPE_KEY), "binlookup": config.BINLOOKUP}}


@app.post("/api/cards/generate")
async def card_generate(body: dict):
    rows = cards.generate(
        bin_pattern=body.get("bin", ""),
        count=max(1, min(int(body.get("count", 10)), 500)),
        brand=body.get("brand") or None,
        country=body.get("country") or None,
        exp_from=body.get("exp_from"), exp_to=body.get("exp_to"),
        with_name=body.get("with_name", True),
        with_address=body.get("with_address", False))
    return {"batch": cards.store(rows), "cards": rows}


def parse_line(line: str):
    parts = [p.strip() for p in re.split(r"[|/,\t; ]+", line.strip()) if p.strip()]
    if not parts:
        return None
    num = re.sub(r"\D", "", parts[0])
    if len(num) < 12:
        return None
    return {"num": num, "mm": parts[1] if len(parts) > 1 else None,
            "yy": parts[2] if len(parts) > 2 else None,
            "cvv": parts[3] if len(parts) > 3 else None,
            "name": parts[4] if len(parts) > 4 else None}


@app.post("/api/cards/check")
async def card_check(body: dict):
    raw = body.get("cards") or []
    if isinstance(raw, str):
        raw = [parse_line(l) for l in raw.splitlines()]
    rows = [r for r in raw if r][: config.MAX_CHECK]
    live = bool(body.get("live") and config.STRIPE_KEY)
    sem = asyncio.Semaphore(config.CHECK_CONCURRENCY)

    async def one(row):
        async with sem:
            v = cards.validate(row["num"], row.get("mm"), row.get("yy"), row.get("cvv"))
            if v["verdict"] != "bad":
                if config.BINLOOKUP:
                    bl = await cards.bin_lookup(row["num"])
                    if bl and not bl.get("error"):
                        v["bin_info"] = bl
                        v["reasons"].append(f'issuer {bl.get("bank")} ({bl.get("country")})')
                        if bl.get("scheme") and v.get("brand") and bl["scheme"] != v["brand"]:
                            v["reasons"].append(f'BIN says {bl["scheme"]}')
                if live:
                    res = await cards.stripe_check(row["num"], row["mm"], row["yy"],
                                                   row["cvv"], row.get("name"))
                    v["verdict"] = res["status"]
                    v["reasons"].append(res.get("reason") or res.get("cvc_check") or "no detail")
                await asyncio.sleep(config.CHECK_DELAY)
            return {**row, **v}

    async def gen():
        done = 0
        for fut in asyncio.as_completed([one(r) for r in rows]):
            r = await fut
            done += 1
            yield sse({"type": "verdict", "row": r, "done": done, "total": len(rows)})
        yield sse({"type": "done"})

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/api/cards/export")
async def card_export(body: dict):
    txt = cards.as_text(body.get("rows", []), body.get("fmt", "txt"), body.get("only"))
    ext = "csv" if body.get("fmt") == "csv" else "txt"
    return Response(txt, media_type="text/plain",
                    headers={"Content-Disposition": f'attachment; filename="cards.{ext}"'})


# ---------- network ----------

@app.get("/api/net/status")
async def net_status():
    return egress.status()


@app.get("/api/net/profiles")
async def net_profiles():
    return [{"id": p["id"], "label": p["label"], "kind": p["kind"],
             "host": p["host"], "port": p["port"], "ua": (p["ua"] or "")[:48]}
            for p in egress.profiles()]


@app.post("/api/net/profiles")
async def net_add(body: dict):
    kind = body.get("kind", "socks5h")
    fp = fingerprint.roll()
    row = {"label": (body.get("label") or kind)[:40], "kind": kind,
           "host": body.get("host"), "port": body.get("port"),
           "username": body.get("username"), "password": body.get("password"),
           "ss_uri": body.get("ss_uri"), "plugin": None,
           "ua": body.get("ua") or fp["ua"], "locale": fp["locale"], "tz": fp["tz"]}
    if kind == "ss":
        parsed = ss_uri.parse(body.get("ss_uri") or "")
        row.update({"host": parsed["host"], "port": parsed["port"],
                    "label": parsed["tag"] or row["label"]})
    return {"id": db.add_egress(row)}


@app.delete("/api/net/profiles/{pid}")
async def net_del(pid: int):
    await ss_uri.stop(pid)
    db.del_egress(pid)
    return {"ok": True}


@app.post("/api/net/active/{pid}")
async def net_active(pid: int):
    return await egress.set_active(pid)


@app.post("/api/net/disable")
async def net_disable():
    db.set_setting("egress_enabled", "0")
    return {"ok": True}


@app.post("/api/net/enable")
async def net_enable():
    db.set_setting("egress_enabled", "1")
    return {"ok": True}


@app.post("/api/net/rotation")
async def net_rotation(body: dict):
    db.set_setting("rotation", body.get("mode", "sticky"))
    return {"ok": True}


@app.post("/api/net/health/{pid}")
async def net_health(pid: int):
    prof = db.get_egress(pid)
    if not prof:
        raise HTTPException(404, "no such profile")
    return await egress.health(prof)


@app.post("/api/net/test")
async def net_test():
    async def gen():
        q = asyncio.Queue()

        async def emit(ev):
            await q.put(ev)

        task = asyncio.create_task(leaks.run(emit))
        while True:
            ev = await q.get()
            yield sse(ev)
            if ev["type"] == "done":
                break
        await task

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/api/net/scrub")
async def net_scrub(body: dict):
    return scrub.run(body)