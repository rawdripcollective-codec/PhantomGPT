import random, re, time, uuid
from . import config
from .net import egress

BRAND_SPECS = {
    "visa": {"lengths": [16, 13, 19], "cvv": 3, "test": lambda p: p[0] == "4"},
    "mastercard": {"lengths": [16], "cvv": 3,
                   "test": lambda p: 51 <= int(p[:2]) <= 55 or 2221 <= int(p[:4]) <= 2720},
    "amex": {"lengths": [15], "cvv": 4, "test": lambda p: p[:2] in ("34", "37")},
    "discover": {"lengths": [16, 19], "cvv": 3,
                 "test": lambda p: p[:4] == "6011" or p[:2] == "65" or 644 <= int(p[:3]) <= 649},
    "jcb": {"lengths": [16, 17, 18, 19], "cvv": 3,
            "test": lambda p: 3528 <= int(p[:4]) <= 3589},
    "diners": {"lengths": [14, 16, 19], "cvv": 3,
               "test": lambda p: p[:2] in ("36", "38", "39") or 300 <= int(p[:3]) <= 305},
    "unionpay": {"lengths": [16, 17, 18, 19], "cvv": 3, "test": lambda p: p[:2] == "62"},
}

CATALOG = [
    ("414720", "visa", "Chase", "US"), ("402400", "visa", "Bank of America", "US"),
    ("426684", "visa", "Wells Fargo", "US"), ("453201", "visa", "Citi", "US"),
    ("491183", "visa", "Capital One", "US"), ("400344", "visa", "US Bank", "US"),
    ("492910", "visa", "Barclays", "GB"), ("454313", "visa", "HSBC", "GB"),
    ("459632", "visa", "Lloyds", "GB"), ("498820", "visa", "Revolut", "GB"),
    ("535456", "mastercard", "Chase", "US"), ("519123", "mastercard", "Citi", "US"),
    ("542523", "mastercard", "Barclaycard", "GB"), ("552204", "mastercard", "HSBC", "GB"),
    ("539983", "mastercard", "Commonwealth Bank", "AU"), ("222300", "mastercard", "Nationwide", "GB"),
    ("543612", "mastercard", "Deutsche Bank", "DE"), ("555555", "mastercard", "Mastercard Test", "US"),
    ("378282", "amex", "American Express", "US"), ("371449", "amex", "American Express", "US"),
    ("378734", "amex", "American Express", "US"), ("376482", "amex", "American Express", "GB"),
    ("601111", "discover", "Discover", "US"), ("601100", "discover", "Discover", "US"),
    ("644564", "discover", "Discover", "US"), ("353011", "jcb", "JCB", "JP"),
    ("356600", "jcb", "JCB", "JP"), ("305693", "diners", "Diners Club", "US"),
    ("367001", "diners", "Diners Club", "US"), ("621234", "unionpay", "UnionPay", "CN"),
    ("625094", "unionpay", "UnionPay", "CN"),
]

CATALOG_PUBLIC = [{"bin": b, "brand": br, "issuer": i, "country": c} for b, br, i, c in CATALOG]

FIRST = ["James", "Maria", "Wei", "Fatima", "Liam", "Sofia", "Noah", "Aisha", "Lucas", "Yuki",
         "Omar", "Elena", "Ethan", "Priya", "Mateo", "Chloe", "Ivan", "Amara", "Diego", "Hana"]
LAST = ["Smith", "Garcia", "Chen", "Okafor", "Muller", "Rossi", "Novak", "Haddad", "Silva",
        "Tanaka", "Kowalski", "Dubois", "Andersen", "Petrov", "Ferreira", "Yilmaz", "Nguyen",
        "Costa", "Murphy", "Rahman"]
STREETS = ["Maple Ave", "Oak St", "Cedar Ln", "Park Rd", "Elm St", "Sunset Blvd", "King St", "Mill Rd"]
CITIES = [("US", "Springfield", "IL", "62704"), ("US", "Austin", "TX", "78701"),
          ("US", "Portland", "OR", "97205"), ("GB", "London", "", "EC1A"),
          ("CA", "Toronto", "ON", "M5H"), ("DE", "Berlin", "", "10115")]


def luhn_digit(body):
    total = 0
    for i, ch in enumerate(reversed(body)):
        d = int(ch)
        if i % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return (10 - total % 10) % 10


def luhn_ok(num):
    total = 0
    for i, ch in enumerate(reversed(num)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def brand_of(num):
    for name, spec in BRAND_SPECS.items():
        try:
            if spec["test"](num):
                return name
        except (ValueError, IndexError):
            continue
    return None


def _pick_bin(brand, country):
    pool = [c for c in CATALOG
            if (not brand or c[1] == brand) and (not country or c[3] == country.upper())]
    return random.choice(pool or CATALOG)


def _make(prefix, length):
    body = list(prefix.ljust(length - 1, "x")[:length - 1])
    body = "".join(str(random.randint(0, 9)) if c == "x" else c for c in body)
    return body + str(luhn_digit(body))


def _expiry(exp_from=None, exp_to=None):
    now = time.localtime()
    lo = exp_from or f"{now.tm_year}-{(now.tm_mon % 12) + 1:02d}"
    try:
        y0, m0 = (int(x) for x in lo.split("-"))
    except ValueError:
        y0, m0 = now.tm_year, now.tm_mon
    m = m0 + random.randint(0, 48)
    y = y0 + (m - 1) // 12
    return f"{(m - 1) % 12 + 1:02d}", f"{y % 100:02d}"


def generate(bin_pattern="", count=10, brand=None, country=None,
             exp_from=None, exp_to=None, with_name=True, with_address=False):
    pattern = re.sub(r"[^0-9x]", "", (bin_pattern or "").lower())
    out, seen = [], set()

    for _ in range(count * 6):
        if len(out) >= count:
            break
        if pattern:
            chosen = pattern
            spec_brand = brand_of(pattern.replace("x", "0")) if pattern[0].isdigit() else None
        else:
            b, br, _, _ = _pick_bin(brand, country)
            chosen, spec_brand = b, br

        spec_brand = spec_brand or brand or "visa"
        spec = BRAND_SPECS.get(spec_brand, BRAND_SPECS["visa"])

        length = len(chosen) if len(chosen) > 1 else random.choice(spec["lengths"])
        if length not in spec["lengths"]:
            length = random.choice(spec["lengths"])
        if len(chosen) >= length:
            chosen = chosen[:length]

        num = _make(chosen, length)
        if num in seen:
            continue
        seen.add(num)

        mm, yy = _expiry(exp_from, exp_to)
        row = {"num": num, "mm": mm, "yy": yy,
               "cvv": "".join(random.choices("0123456789", k=spec["cvv"])),
               "brand": spec_brand, "bin": num[:6]}
        if with_name:
            row["name"] = f"{random.choice(FIRST)} {random.choice(LAST)}"
        if with_address:
            cc, city, state, zipc = random.choice(CITIES)
            row.update({"street": f"{random.randint(1, 9999)} {random.choice(STREETS)}",
                        "city": city, "state": state, "zip": zipc, "country": cc})
        out.append(row)
    return out


def validate(num, mm=None, yy=None, cvv=None):
    n = re.sub(r"\D", "", num or "")
    if not n:
        return {"verdict": "bad", "reasons": ["empty"]}
    if len(n) < 12 or len(n) > 19:
        return {"verdict": "bad", "reasons": [f"length {len(n)} out of range"]}

    brand = brand_of(n)
    if not brand:
        return {"verdict": "bad", "reasons": ["unknown BIN prefix"]}

    spec = BRAND_SPECS[brand]
    if len(n) not in spec["lengths"]:
        return {"verdict": "bad", "reasons": [f"{brand} cannot be {len(n)} digits"]}
    if not luhn_ok(n):
        return {"verdict": "bad", "reasons": ["luhn fail"]}
    if cvv and len(str(cvv)) != spec["cvv"]:
        return {"verdict": "bad", "reasons": [f"{brand} CVV must be {spec['cvv']} digits"]}

    if mm and yy:
        try:
            m, y = int(mm), 2000 + int(yy)
            if not 1 <= m <= 12:
                return {"verdict": "bad", "reasons": ["bad month"]}
            now = time.localtime()
            if (y, m) < (now.tm_year, now.tm_mon):
                return {"verdict": "bad", "reasons": ["expired"]}
            if y > now.tm_year + 20:
                return {"verdict": "bad", "reasons": ["expiry implausible"]}
        except ValueError:
            return {"verdict": "bad", "reasons": ["unparseable expiry"]}

    reasons = ["format ok"]
    if not any(n.startswith(b) for b, *_ in CATALOG):
        reasons.append("BIN not in catalog")
    return {"verdict": "unknown", "reasons": reasons, "brand": brand, "bin": n[:6]}


async def bin_lookup(num):
    if not config.BINLOOKUP:
        return None
    try:
        async with egress.client(timeout=8) as c:
            r = await c.get(f"https://lookup.binlist.net/{num[:8]}",
                            headers={"Accept-Version": "3"})
            if r.status_code != 200:
                return {"error": f"HTTP {r.status_code}"}
            d = r.json()
            return {"scheme": d.get("scheme"), "type": d.get("type"),
                    "bank": (d.get("bank") or {}).get("name"),
                    "country": (d.get("country") or {}).get("alpha2")}
    except Exception as e:
        return {"error": type(e).__name__}


async def stripe_check(num, mm, yy, cvv, name=None):
    if not config.STRIPE_KEY:
        return {"status": "skipped"}
    payload = {"type": "card", "card[number]": num, "card[exp_month]": mm,
               "card[exp_year]": yy, "card[cvc]": cvv}
    if name:
        payload["billing_details[name]"] = name
    try:
        async with egress.client(timeout=20) as c:
            r = await c.post("https://api.stripe.com/v1/payment_methods",
                             data=payload, auth=(config.STRIPE_KEY, ""))
            d = r.json()
    except Exception as e:
        return {"status": "unknown", "reason": type(e).__name__}

    if r.status_code == 200:
        checks = (d.get("card") or {}).get("checks") or {}
        return {"status": "good", "cvc_check": checks.get("cvc_check")}
    code = (d.get("error") or {}).get("code", "")
    if code in ("card_declined", "incorrect_cvc", "expired_card",
                "incorrect_number", "invalid_expiry_year"):
        return {"status": "bad", "reason": code}
    return {"status": "unknown", "reason": code or f"HTTP {r.status_code}"}


_BATCHES = {}


def store(rows):
    bid = uuid.uuid4().hex[:12]
    _BATCHES[bid] = rows
    return bid


def batch(bid):
    return _BATCHES.get(bid, [])


def as_text(rows, fmt="txt", only=None):
    rows = [r for r in rows if only in (None, r.get("verdict"))]
    if fmt == "csv":
        head = "number,mm,yy,cvv,brand,name,verdict,reasons"
        body = [f'{r["num"]},{r["mm"]},{r["yy"]},{r["cvv"]},{r.get("brand", "")},'
                f'"{r.get("name", "")}",{r.get("verdict", "")},'
                f'"{(chr(59) + chr(32)).join(r.get("reasons", []))}"' for r in rows]
        return "\n".join([head, *body])
    return "\n".join(f'{r["num"]}|{r["mm"]}|{r["yy"]}|{r["cvv"]}|{r.get("name", "")}' for r in rows)