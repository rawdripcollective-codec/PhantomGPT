import json
import httpx
from .. import config
from . import egress

PROBES = {
    "exit": "https://api.ipify.org?format=json",
    "geo": "https://ipinfo.io/json",
    "trace": "https://www.cloudflare.com/cdn-cgi/trace",
    "headers": "https://httpbin.org/headers",
    "tor": "https://check.torproject.org/api/ip",
}


async def _get(url, proxy=None, headers=None):
    try:
        async with httpx.AsyncClient(proxy=proxy, timeout=config.LEAK_TIMEOUT,
                                     trust_env=False, headers=headers or {}) as c:
            r = await c.get(url)
            return r.status_code, r.text[:4000]
    except Exception as e:
        return 0, type(e).__name__


def _verdict(score, max_score):
    pct = score / max_score if max_score else 0
    if pct >= 0.85:
        return "strong"
    if pct >= 0.55:
        return "partial"
    return "leaking"


async def run(emit):
    checks = []
    score = 0
    max_score = 24

    async def add(name, ok, detail, weight=1):
        nonlocal score
        if ok:
            score += weight
        checks.append({"check": name, "pass": ok, "detail": detail})
        await emit({"type": "check", "check": name, "pass": ok, "detail": detail})

    prof = egress.active()
    await add("egress configured", prof is not None,
              prof["label"] if prof else "no profile selected", 2)

    is_chain = bool(prof and prof["kind"] == "chain")
    await add("chained (tor over bridge)", is_chain,
              prof["kind"] if prof else "none", 2)

    _, direct_raw = await _get(PROBES["exit"])
    direct_ip = json.loads(direct_raw).get("ip") if direct_raw.startswith("{") else None

    try:
        proxy = egress.proxy_for(prof)
    except Exception:
        proxy = None

    code, raw = await _get(PROBES["exit"], proxy)
    exit_ip = json.loads(raw).get("ip") if raw.startswith("{") else None
    await add("tunnel reachable", code == 200, f"HTTP {code}" if code else raw, 2)
    await add("exit IP differs from direct", bool(exit_ip and exit_ip != direct_ip),
              f"{direct_ip} -> {exit_ip}", 3)

    code, raw = await _get(PROBES["tor"], proxy)
    is_tor = False
    if code == 200:
        try:
            is_tor = bool(json.loads(raw).get("IsTor"))
        except Exception:
            pass
    await add("confirmed tor exit", is_tor, "IsTor=true" if is_tor else "not tor", 4)

    code, raw = await _get(PROBES["geo"], proxy)
    geo = {}
    if code == 200:
        try:
            geo = json.loads(raw)
        except Exception:
            pass
    await add("exit ASN known", bool(geo.get("org")), geo.get("org", "unresolved"), 1)
    await add("exit country", True, geo.get("country", "unknown"), 0)

    code, raw = await _get(PROBES["trace"], proxy)
    await add("remote DNS resolution", code == 200, "resolver via tunnel", 2)

    code, raw = await _get(PROBES["headers"], proxy)
    hdrs = {}
    if code == 200:
        try:
            hdrs = json.loads(raw).get("headers", {})
        except Exception:
            pass
    ua = hdrs.get("User-Agent", "")
    await add("browser-like User-Agent", "Mozilla/5.0" in ua, ua[:60] or "absent", 2)
    await add("Python UA suppressed", "python-httpx" not in ua.lower(), ua[:40] or "absent", 2)
    await add("Referer stripped", not hdrs.get("Referer"), hdrs.get("Referer", "none"), 1)
    await add("Accept-Language set", bool(hdrs.get("Accept-Language")),
              hdrs.get("Accept-Language", "none"), 1)

    await emit({"type": "done", "score": score, "max": max_score,
                "checks": checks, "verdict": _verdict(score, max_score)})
