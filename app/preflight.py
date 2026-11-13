import re
from dataclasses import dataclass
from . import scope

DOMAIN = re.compile(r"\b(?:(?!-)[a-z0-9-]{1,63}(?<!-)\.)+(?:com|net|org|io|dev|co|ai|app|cloud|xyz|info|biz|me|us|uk|de|fr|nl|ru|cn|jp|br|in|au|ca|ch|se|no|es|it|pl|tk|sh|site|online|tech|store|edu|gov|mil)\b", re.I)
IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
CVE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.I)
HASH = re.compile(r"\b(?:[a-f0-9]{64}|[a-f0-9]{40}|[a-f0-9]{32})\b", re.I)
JWT = re.compile(r"\beyJ[\w-]{8,}\.[\w-]{8,}\.[\w-]*")
EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b")
URL = re.compile(r"https?://[^\s<>\"')\]]+")

NOISE = {"e.g", "i.e", "etc", "vs", "a.k.a"}

PLAN = {
    "url": [("http_probe", "url"), ("robots_sitemap", "base"), ("tls_cert", "host")],
    "domain": [("dns_lookup", "domain"), ("rdap_whois", "domain"),
               ("crt_sh", "domain"), ("tls_cert", "host")],
    "ip": [("port_scan", "host"), ("shodan_host", "host"), ("censys_host", "host")],
    "cve": [("cve_lookup", "cve")],
    "hash": [("identify_hash", "hash")],
    "jwt": [("jwt_inspect", "token")],
    "email": [("dehashed_search", "email")],
}

FIELD = {"url": "url", "base": "base_url", "host": "host", "domain": "domain",
         "cve": "cve_id", "hash": "hash", "token": "token", "email": "email"}


@dataclass(frozen=True)
class Target:
    kind: str
    value: str


def extract(text):
    found, seen, urls = [], set(), []
    for m in URL.finditer(text):
        urls.append(m.group(0))
        found.append(Target("url", m.group(0).rstrip(".,;")))
        seen.add(m.group(0))
    stripped = text
    for u in urls:
        stripped = stripped.replace(u, " ")
    for kind, rx in (("cve", CVE), ("jwt", JWT), ("ip", IPV4), ("hash", HASH),
                     ("email", EMAIL), ("domain", DOMAIN)):
        for m in rx.finditer(stripped):
            v = m.group(0).rstrip(".,;")
            if v.lower() in NOISE or v.lower() in seen:
                continue
            seen.add(v.lower())
            found.append(Target(kind, v))
    return found[:8]


def _host(value):
    return re.sub(r"^https?://", "", value).split("/")[0].split(":")[0]


def _args(field, target):
    return {FIELD[field]: target.value}


def plan(text, budget):
    out = []
    for t in extract(text):
        if t.kind not in ("hash", "jwt") and not scope.allowed(_host(t.value)):
            out.append(("__scope__", {"host": _host(t.value)}))
            continue
        for tool, field in PLAN.get(t.kind, []):
            if len(out) >= budget:
                return out
            out.append((tool, _args(field, t)))
    return out