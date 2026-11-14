import asyncio, base64, json, os, re, tempfile
from urllib.parse import unquote
from .. import config

_procs = {}


def parse(uri):
    raw = (uri or "").strip()
    if not raw.startswith("ss://"):
        raise ValueError("not an ss:// URI")
    body = raw[5:]
    tag = ""
    if "#" in body:
        body, tag = body.split("#", 1)
    plugin = ""
    if "?" in body:
        body, q = body.split("?", 1)
        m = re.search(r"plugin=([^&]+)", q)
        if m:
            plugin = unquote(m.group(1))

    if "@" in body:
        cred, hostport = body.rsplit("@", 1)
        cred = cred.split("/")[0]
        pad = cred + "=" * (-len(cred) % 4)
        method, _, password = base64.urlsafe_b64decode(pad).decode().partition(":")
    else:
        chunk = body.split("/")[0]
        pad = chunk + "=" * (-len(chunk) % 4)
        dec = base64.urlsafe_b64decode(pad).decode()
        cred, _, hostport = dec.rpartition("@")
        method, _, password = cred.partition(":")

    host, _, port = hostport.rpartition(":")
    return {"method": method, "password": password, "host": host.strip("[]"),
            "port": int(port), "plugin": plugin, "tag": tag}


async def start(profile_id, uri, local_port):
    if not config.SSLOCAL_BIN:
        raise RuntimeError("SSLOCAL_BIN unset")
    p = parse(uri)
    cfg = {"server": p["host"], "server_port": p["port"], "password": p["password"],
           "method": p["method"], "local_address": "127.0.0.1",
           "local_port": local_port, "mode": "tcp_and_udp", "timeout": 30}
    if p["plugin"]:
        bits = p["plugin"].split(";")
        cfg["plugin"] = bits[0]
        cfg["plugin_opts"] = ";".join(bits[1:])

    fd, path = tempfile.mkstemp(suffix=".json", prefix="ss-")
    with os.fdopen(fd, "w") as f:
        json.dump(cfg, f)
    os.chmod(path, 0o600)

    proc = await asyncio.create_subprocess_exec(
        config.SSLOCAL_BIN, "-c", path,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE)

    for _ in range(40):
        await asyncio.sleep(0.1)
        try:
            _, w = await asyncio.open_connection("127.0.0.1", local_port)
            w.close()
            _procs[profile_id] = proc
            return {"local_port": local_port, "server": f'{p["host"]}:{p["port"]}'}
        except OSError:
            if proc.returncode is not None:
                err = (await proc.stderr.read()).decode()[:400]
                raise RuntimeError(f"sslocal exited: {err}")
    raise RuntimeError("sslocal did not bind in time")


async def stop(profile_id):
    proc = _procs.pop(profile_id, None)
    if proc and proc.returncode is None:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), 3)
        except asyncio.TimeoutError:
            proc.kill()
