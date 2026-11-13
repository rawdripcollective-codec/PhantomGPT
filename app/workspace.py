import io, os, shutil, zipfile
from pathlib import Path
from . import config

ROOT = Path(config.WORKSPACE_ROOT).resolve()
SKIP = {"node_modules", ".git", "__pycache__", "dist", "build", "venv", ".venv", ".next"}


def ensure():
    ROOT.mkdir(parents=True, exist_ok=True)


def base(ws_id):
    return ROOT / str(ws_id)


def resolve(ws_id, rel):
    p = (base(ws_id) / rel).resolve()
    if not str(p).startswith(str(base(ws_id).resolve())):
        raise ValueError(f"path escapes workspace: {rel}")
    return p


def write(ws_id, rel, content):
    p = resolve(ws_id, rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return len(content.encode())


def read(ws_id, rel):
    return resolve(ws_id, rel).read_text()


def remove(ws_id, rel):
    p = resolve(ws_id, rel)
    if p.is_dir():
        shutil.rmtree(p)
    elif p.exists():
        p.unlink()


def tree(ws_id):
    b = base(ws_id)
    if not b.exists():
        return []
    out = []
    for dirpath, dirnames, filenames in os.walk(b):
        dirnames[:] = [d for d in dirnames if d not in SKIP]
        for f in filenames:
            out.append(os.path.relpath(os.path.join(dirpath, f), b))
    return sorted(out)


def zip_bytes(ws_id):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in tree(ws_id):
            z.write(base(ws_id) / f, f)
    return buf.getvalue()


def destroy(ws_id):
    shutil.rmtree(base(ws_id), ignore_errors=True)