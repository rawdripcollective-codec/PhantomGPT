import asyncio
from .. import config
from . import ss_uri
from .tor import Tor, TorError

_chains = {}


def _ports(pid: int):
    return (config.CHAIN_PORT_BASE + pid, config.TOR_SOCKS_BASE + pid,
            config.TOR_CONTROL_BASE + pid)


class Chain:
    def __init__(self, pid: int, ss_uri_str: str):
        self.pid = pid
        self.ss_uri = ss_uri_str
        self.ss_port, self.socks_port, self.control_port = _ports(pid)
        self.tor = None

    async def start(self):
        await ss_uri.start(self.pid, self.ss_uri, self.ss_port)
        try:
            self.tor = Tor(self.socks_port, self.control_port, self.ss_port)
            await self.tor.start()
        except TorError:
            await ss_uri.stop(self.pid)
            raise
        return self

    async def new_identity(self):
        if not self.tor:
            raise TorError("chain not running")
        return await self.tor.new_identity()

    async def stop(self):
        if self.tor:
            await self.tor.stop()
            self.tor = None
        await ss_uri.stop(self.pid)


async def start(pid: int, ss_uri_str: str):
    await stop(pid)
    chain = await Chain(pid, ss_uri_str).start()
    _chains[pid] = chain
    return chain


async def stop(pid: int):
    chain = _chains.pop(pid, None)
    if chain:
        await chain.stop()


def get(pid: int):
    return _chains.get(pid)


def state(pid: int):
    c = _chains.get(pid)
    if not c:
        return {"up": False}
    return {"up": True, "socks": c.socks_port, "control": c.control_port,
            "bridge": c.ss_port, "bootstrapped": True}


async def stop_all():
    for pid in list(_chains):
        await stop(pid)
