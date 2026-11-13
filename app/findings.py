SEVERITIES = ["critical", "high", "medium", "low", "info"]
_ORDER = {s: i for i, s in enumerate(SEVERITIES)}


def sort(rows):
    return sorted(rows, key=lambda r: (_ORDER.get(r["severity"], 9), r["id"]))


def counts(rows):
    out = {s: 0 for s in SEVERITIES}
    for r in rows:
        out[r["severity"]] = out.get(r["severity"], 0) + 1
    return out