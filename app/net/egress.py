import httpx
from .. import config, db
from . import chain, fingerprint, ss_uri

_state = {"active": None, "tripped": False, "counter": 0, "ss_ports": {}, "next_port": 10800}


def profiles():
    return db.list_egress()


def active():
    aid = db.setting("egress_active")
    return db.get_egress(int(aid)) if aid else None


async def _teardown(pid):
    await chain.stop(pid)
    await ss_uri.stop(pid)
    _state["ss_ports"].pop(pid, None)


async def set_active(pid):
    prev = active()
    if prev and prev["id"] != pid:
        await _teardown(prev["id"])
    if pid is None:
        db.set_setting("egress_active", "")
        _state["active"] = None
        return {"active": None}

    prof = db.get_egress(pid)
    if not prof:
        raise KeyError("no such profile")

    if prof["kind"] == "chain":
        await chain.start(pid, prof["ss_uri"])
    elif prof["kind"] == "ss":
        port = _state["next_port"]
        _state["next_port"] += 1
        await ss_uri.start(pid, prof["ss_uri"], port)
        _state["ss_ports"][pid] = port

    db.set_setting("egress_active", pid)
    _state["active"] = pid
    _state["tripped"] = False
    return {"active": pid}


def proxy_for(prof):
    if not prof:
        return None
    k = prof["kind"]
    if k == "direct":
        return None
    if k == "chain":
        st = chain.state(prof["id"])
        if not st["up"]:
            raise RuntimeError("chain down")
        return f'socks5h://127.0.0.1:{st["socks"]}'
    if k == "tor":
        return "socks5h://127.0.0.1:9050"
    if k == "ss":
        port = _state["ss_ports"].get(prof["id"])
        if not port:
            raise RuntimeError("shadowsocks tunnel not running")
        return f"socks5h://127.0.0.1:{port}"
    if k in ("socks5", "socks5h"):
        auth = f'{prof["username"]}:{prof["password"]}@' if prof.get("username") else ""
        return f'{k}://{auth}{prof["host"]}:{prof["port"]}'
    if k in ("http", "https"):
        auth = f'{prof["username"]}:{prof["password"]}@' if prof.get("username") else ""
        return f'{k}://{auth}{prof["host"]}:{prof["port"]}'
    return None


def pick():
    if db.setting("egress_enabled", "1") != "1":
        return None
    mode = db.setting("rotation", config.EGRESS_ROTATION)
    pool = [p for p in profiles() if p["kind"] != "direct"]
    if not pool:
        return None
    if mode == "request":
        _state["counter"] += 1
        return pool[_state["counter"] % len(pool)]
    cur = active()
    if cur and cur["kind"] != "direct":
        return cur
    if mode == "round":
        _state["counter"] += 1
        return pool[_state["counter"] % len(pool)]
    return pool[0]


def guard():
    if _state["tripped"] and config.FAIL_CLOSED:
        raise RuntimeError("kill switch: egress down, refusing to send")


def client(**kw):
    guard()
    prof = pick()
    try:
        proxy = proxy_for(prof) if prof else None
    except RuntimeError:
        _state["tripped"] = True
        if config.FAIL_CLOSED:
            raise
        proxy = None
    kw.setdefault("timeout", 25)
    kw.setdefault("follow_redirects", True)
    kw.setdefault("trust_env", False)
    return httpx.AsyncClient(proxy=proxy, headers=fingerprint.headers(prof), **kw)


async def health(prof):
    try:
        proxy = proxy_for(prof)
        async with httpx.AsyncClient(proxy=proxy, timeout=config.LEAK_TIMEOUT,
                                     trust_env=False) as c:
            r = await c.get("https://check.torproject.org/api/ip")
            d = r.json()
            return {"ok": r.status_code == 200, "ip": d.get("IP"),
                    "is_tor": d.get("IsTor")}
    except Exception as e:
        _state["tripped"] = True
        return {"ok": False, "error": type(e).__name__}


async def new_identity(pid):
    c = chain.get(pid)
    if not c:
        raise RuntimeError("no active chain on this profile")
    return await c.new_identity()


def status():
    prof = active()
    out = {
        "enabled": db.setting("egress_enabled", "1") == "1",
        "active": {"id": prof["id"], "label": prof["label"], "kind": prof["kind"]} if prof else None,
        "rotation": db.setting("rotation", config.EGRESS_ROTATION),
        "fail_closed": config.FAIL_CLOSED,
        "kill_switch_tripped": _state["tripped"],
        "chain": None,
    }
    if prof and prof["kind"] == "chain":
        out["chain"] = chain.state(prof["id"])
    return out
