from fnmatch import fnmatch
from . import config


class OutOfScope(Exception):
    pass


def allowed(host):
    if not config.SCOPE_ALLOW:
        return True
    h = (host or "").lower().strip(".")
    return any(h == p.lstrip("*.") or fnmatch(h, p) for p in config.SCOPE_ALLOW)


def require(host):
    if not allowed(host):
        raise OutOfScope(f"{host} outside scope {config.SCOPE_ALLOW}")


def summary():
    return {"enforced": bool(config.SCOPE_ALLOW), "allow": config.SCOPE_ALLOW}