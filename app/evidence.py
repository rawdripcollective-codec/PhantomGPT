import hashlib, json, time
from . import db


def digest(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def record(chat_id, tool, target, payload):
    ev_id = db.next_evidence_id(chat_id)
    sha = digest(payload)
    db.add_evidence(chat_id, ev_id, tool, target, sha, json.dumps(payload, default=str))
    return {"ev_id": ev_id, "sha256": sha, "collected_at": time.time()}


def digest_block(rows):
    lines = ["EVIDENCE LEDGER - cite these ids, do not invent facts beyond them:"]
    for r in rows:
        lines.append(f"[{r['ev_id']}] {r['tool']}({r['target']}) sha256:{r['sha256'][:16]}")
        lines.append("  " + (r["payload"] or "")[:1400].replace("\n", "\n  "))
    lines.append("Rules: cite [EV-xxxx] for every version/header/CVE claim. "
                 "Tag anything not backed by evidence as UNVERIFIED.")
    return "\n".join(lines)