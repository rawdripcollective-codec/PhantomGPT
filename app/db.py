import sqlite3, threading, time
from . import config

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS chats(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  persona TEXT NOT NULL,
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS messages(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  chat_id INTEGER NOT NULL,
  role TEXT NOT NULL,
  content TEXT,
  tool_name TEXT,
  tool_args TEXT,
  tool_result TEXT,
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  chat_id INTEGER NOT NULL,
  ev_id TEXT NOT NULL,
  tool TEXT NOT NULL,
  target TEXT,
  sha256 TEXT NOT NULL,
  payload TEXT,
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS findings(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  chat_id INTEGER NOT NULL,
  title TEXT NOT NULL,
  severity TEXT NOT NULL,
  host TEXT,
  ev_id TEXT,
  status TEXT DEFAULT 'open',
  notes TEXT,
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS egress(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  label TEXT NOT NULL,
  kind TEXT NOT NULL,
  host TEXT,
  port INTEGER,
  username TEXT,
  password TEXT,
  ss_uri TEXT,
  plugin TEXT,
  ua TEXT,
  locale TEXT,
  tz TEXT,
  enabled INTEGER DEFAULT 1,
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS settings(
  key TEXT PRIMARY KEY,
  value TEXT
);
"""


def init():
    with sqlite3.connect(config.DB_PATH) as c:
        c.executescript(SCHEMA)


def _conn():
    c = sqlite3.connect(config.DB_PATH)
    c.row_factory = sqlite3.Row
    return c


# ---------- chats ----------

def create_chat(title, persona):
    with _lock, _conn() as c:
        cur = c.execute(
            "INSERT INTO chats(title, persona, created_at) VALUES(?,?,?)",
            (title, persona, time.time()))
        return cur.lastrowid


def list_chats():
    with _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT id, title, persona, created_at FROM chats ORDER BY id DESC")]


def get_chat(cid):
    with _conn() as c:
        r = c.execute("SELECT * FROM chats WHERE id=?", (cid,)).fetchone()
        return dict(r) if r else None


def delete_chat(cid):
    with _lock, _conn() as c:
        for t in ("messages", "evidence", "findings"):
            c.execute(f"DELETE FROM {t} WHERE chat_id=?", (cid,))
        c.execute("DELETE FROM chats WHERE id=?", (cid,))


def rename_if_default(cid, text):
    with _lock, _conn() as c:
        row = c.execute("SELECT title FROM chats WHERE id=?", (cid,)).fetchone()
        if row and row["title"] == "New session":
            c.execute("UPDATE chats SET title=? WHERE id=?", (text[:60], cid))


# ---------- messages ----------

def add_message(cid, role, content=None, tool_name=None, tool_args=None, tool_result=None):
    with _lock, _conn() as c:
        cur = c.execute(
            """INSERT INTO messages(chat_id, role, content, tool_name, tool_args, tool_result, created_at)
               VALUES(?,?,?,?,?,?,?)""",
            (cid, role, content, tool_name, tool_args, tool_result, time.time()))
        return cur.lastrowid


def get_messages(cid):
    with _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM messages WHERE chat_id=? ORDER BY id", (cid,))]


# ---------- evidence ----------

def next_evidence_id(cid):
    with _conn() as c:
        n = c.execute("SELECT COUNT(*) FROM evidence WHERE chat_id=?", (cid,)).fetchone()[0]
    return f"EV-{n + 1:04d}"


def add_evidence(cid, ev_id, tool, target, sha, payload):
    with _lock, _conn() as c:
        c.execute(
            """INSERT INTO evidence(chat_id, ev_id, tool, target, sha256, payload, created_at)
               VALUES(?,?,?,?,?,?,?)""",
            (cid, ev_id, tool, target, sha, payload, time.time()))


def get_evidence(cid):
    with _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM evidence WHERE chat_id=? ORDER BY id", (cid,))]


# ---------- findings ----------

def add_finding(cid, title, severity, host=None, ev_id=None, notes=None):
    with _lock, _conn() as c:
        cur = c.execute(
            """INSERT INTO findings(chat_id, title, severity, host, ev_id, notes, created_at)
               VALUES(?,?,?,?,?,?,?)""",
            (cid, title, severity, host, ev_id, notes, time.time()))
        return cur.lastrowid


def get_findings(cid):
    with _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM findings WHERE chat_id=? ORDER BY id", (cid,))]


def update_finding(fid, **kw):
    if not kw:
        return
    cols = ", ".join(f"{k}=?" for k in kw)
    with _lock, _conn() as c:
        c.execute(f"UPDATE findings SET {cols} WHERE id=?", (*kw.values(), fid))


def delete_finding(fid):
    with _lock, _conn() as c:
        c.execute("DELETE FROM findings WHERE id=?", (fid,))


# ---------- egress ----------

def add_egress(row):
    with _lock, _conn() as c:
        cur = c.execute(
            """INSERT INTO egress(label, kind, host, port, username, password,
                                  ss_uri, plugin, ua, locale, tz, created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (row["label"], row["kind"], row.get("host"), row.get("port"),
             row.get("username"), row.get("password"), row.get("ss_uri"),
             row.get("plugin"), row["ua"], row["locale"], row["tz"], time.time()))
        return cur.lastrowid


def list_egress():
    with _conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM egress WHERE enabled=1 ORDER BY id")]


def get_egress(eid):
    with _conn() as c:
        r = c.execute("SELECT * FROM egress WHERE id=?", (eid,)).fetchone()
        return dict(r) if r else None


def del_egress(eid):
    with _lock, _conn() as c:
        c.execute("DELETE FROM egress WHERE id=?", (eid,))


# ---------- settings ----------

def setting(key, default=None):
    with _conn() as c:
        r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return r["value"] if r else default


def set_setting(key, value):
    with _lock, _conn() as c:
        c.execute(
            "INSERT INTO settings(key, value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))