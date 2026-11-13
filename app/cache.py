import asyncio, hashlib, json, time

_store = {}
_buckets = {}
_lock = asyncio.Lock()


def key(tool, args):
    return hashlib.sha256((tool + json.dumps(args, sort_keys=True)).encode()).hexdigest()


def get(tool, args):
    k = key(tool, args)
    hit = _store.get(k)
    if not hit:
        return None
    expires, payload = hit
    if expires < time.time():
        _store.pop(k, None)
        return None
    return json.loads(payload)


def put(tool, args, payload, ttl):
    _store[key(tool, args)] = (time.time() + ttl, json.dumps(payload, default=str))


async def throttle(host, rate, burst):
    async with _lock:
        now = time.time()
        b = [t for t in _buckets.get(host, []) if now - t < 1.0]
        if len(b) >= burst:
            wait = 1.0 - (now - b[0])
            if wait > 0:
                await asyncio.sleep(wait)
            now = time.time()
            b = [t for t in b if now - t < 1.0]
        b.append(now)
        _buckets[host] = b