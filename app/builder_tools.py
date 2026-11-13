import json
from . import terminal, workspace

SCHEMAS = [
    {"type": "function", "function": {
        "name": "write_file", "description": "Create or overwrite a file with full contents.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"]}}},
    {"type": "function", "function": {
        "name": "read_file", "description": "Read a file back.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}},
                       "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "list_files", "description": "List workspace files.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "delete_file", "description": "Delete a file or directory.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}},
                       "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "run_command", "description": "Run a shell command in the workspace.",
        "parameters": {"type": "object", "properties": {
            "cmd": {"type": "string"}, "purpose": {"type": "string"}},
            "required": ["cmd"]}}},
]


async def dispatch(name, args, ws_id, emit):
    if name == "write_file":
        size = workspace.write(ws_id, args["path"], args.get("content", ""))
        return {"path": args["path"], "bytes": size}
    if name == "read_file":
        return {"path": args["path"], "content": workspace.read(ws_id, args["path"])[:40000]}
    if name == "list_files":
        return {"files": workspace.tree(ws_id)}
    if name == "delete_file":
        workspace.remove(ws_id, args["path"])
        return {"deleted": args["path"]}
    if name == "run_command":
        cmd = args["cmd"]
        tail = []
        async for kind, text in terminal.run(ws_id, cmd):
            if kind == "url":
                await emit({"type": "preview", "url": text})
            else:
                tail.append(text)
                await emit({"type": "exec_output", "text": text})
        return {"cmd": cmd, "exit_tail": "".join(tail)[-4000:]}
    return {"error": f"unknown tool {name}"}