import os, shutil, sqlite3
from pathlib import Path
from .. import cache, config


def _shred(path):
    p = Path(path)
    if not p.exists():
        return
    size = p.stat().st_size
    with open(p, "r+b") as f:
        for _ in range(2):
            f.seek(0)
            f.write(os.urandom(size))
            f.flush()
            os.fsync(f.fileno())
    p.unlink()


def run(opts):
    out = {}

    if opts.get("cache"):
        cache._store.clear()
        cache._buckets.clear()
        out["cache"] = "cleared"

    if opts.get("db"):
        with sqlite3.connect(config.DB_PATH) as c:
            for t in ("messages", "evidence", "findings", "chats", "egress", "settings"):
                c.execute(f"DELETE FROM {t}")
            c.execute("VACUUM")
        for suffix in ("", "-wal", "-shm"):
            _shred(config.DB_PATH + suffix)
        out["db"] = "vacuumed + shredded"

    if opts.get("workspaces") and config.SCRUB_WORKSPACES:
        root = Path(config.WORKSPACE_ROOT)
        if root.exists():
            shutil.rmtree(root, ignore_errors=True)
        root.mkdir(parents=True, exist_ok=True)
        out["workspaces"] = "removed"

    if opts.get("pycache"):
        for p in Path(".").rglob("__pycache__"):
            shutil.rmtree(p, ignore_errors=True)
        out["pycache"] = "removed"

    return out
