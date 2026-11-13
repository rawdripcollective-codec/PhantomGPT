import asyncio, os, re
from . import config, workspace

URL = re.compile(r"https?://(?:localhost|127\.0\.0\.1)(:\d+)")


async def run(ws_id, cmd):
    if not config.ALLOW_SHELL:
        yield "out", "shell disabled (ALLOW_SHELL=0)\n"
        return

    cwd = str(workspace.base(ws_id))
    proc = await asyncio.create_subprocess_shell(
        cmd, cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env={**os.environ, "CI": "1", "FORCE_COLOR": "0", "NODE_ENV": "development"},
        start_new_session=True)

    try:
        async with asyncio.timeout(config.EXEC_TIMEOUT):
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                text = line.decode("utf-8", "replace")
                m = URL.search(text)
                if m:
                    yield "url", f"http://localhost{m.group(1)}"
                yield "out", text
            await proc.wait()
    except TimeoutError:
        try:
            os.killpg(os.getpgid(proc.pid), 15)
        except Exception:
            pass
        yield "out", f"\n[timeout after {config.EXEC_TIMEOUT}s]\n"

    yield "out", f"\n[exit {proc.returncode}]\n"