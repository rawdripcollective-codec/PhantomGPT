import random

UA = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
]
LOCALES = ["en-US,en;q=0.9", "en-GB,en;q=0.9", "en-CA,en;q=0.8", "de-DE,de;q=0.9,en;q=0.7"]
ZONES = ["America/New_York", "Europe/London", "Europe/Berlin", "America/Toronto", "Asia/Singapore"]

CH_UA = {
    "Chrome": '"Chromium";v="131", "Not_A Brand";v="24", "Google Chrome";v="131"',
    "Firefox": '"Firefox";v="133", "Gecko";v="133"',
    "Safari": '"Safari";v="18.1"',
}


def roll():
    return {"ua": random.choice(UA),
            "locale": random.choice(LOCALES),
            "tz": random.choice(ZONES)}


def headers(prof):
    ua = (prof or {}).get("ua") or UA[0]
    h = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": (prof or {}).get("locale") or "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Upgrade-Insecure-Requests": "1",
        "DNT": "1",
        "Sec-GPC": "1",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    for brand, val in CH_UA.items():
        if brand in ua:
            h["Sec-CH-UA"] = val
            break
    if "Windows" in ua:
        h["Sec-CH-UA-Platform"] = '"Windows"'
    elif "Macintosh" in ua:
        h["Sec-CH-UA-Platform"] = '"macOS"'
    elif "Android" in ua:
        h["Sec-CH-UA-Platform"] = '"Android"'
        h["Sec-CH-UA-Mobile"] = "?1"
    elif "iPhone" in ua or "iPad" in ua:
        h["Sec-CH-UA-Platform"] = '"iOS"'
        h["Sec-CH-UA-Mobile"] = "?1"
    return h
