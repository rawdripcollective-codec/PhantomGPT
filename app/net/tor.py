import asyncio, os, secrets, shutil, tempfile
from pathlib import Path
from .. import config

BOOT_MARK = "Bootstrapped 100%"


class TorError(RuntimeError):
    pass


class Tor:
    """Isolated Tor instance. Optionally socks5-chained upstream so the ISP sees only the bridge."""

    def __init__(self, socks_port: int, control_port: int, upstream_port: int | None = None):
        self.socks_port = socks_port
        self.control_port = control_port
        self.upstream_port = upstream_port
        self.dir = Path(tempfile.mkdtemp(prefix="pgtor-"))
        self.log = self.dir / "tor.log"
        self.proc = None

    def _torrc(self) -> str:
        lines = [
            f"SocksPort 127.0.0.1:{self.socks_port}",
            f"ControlPort 127.0.0.1:{self.control_port}",
            "CookieAuthentication 1",
            f"DataDirectory {self.dir}",
            f"Log notice file {self.log}",
            f"MaxCircuitDirtiness {config.TOR_MAX_CIRCUIT_DIRTINESS}",
            "NewCircuitPeriod 30",
            "ClientUseIPv6 0",
            "AvoidDiskWrites 1",
            "SafeLogging 1",
        ]
        if self.upstream_port:
            lines.append(f"Socks5Proxy 127.0.0.1:{self.upstream_port}")
        return "\n".join(lines) + "\n"

    async def start(self):
        if not shutil.which(config.TOR_BIN):
            raise TorError(f"{config.TOR_BIN} not found on PATH")
        rc = self.dir / "torrc"
        rc.write_text(self._torrc())
        os.chmod(rc, 0o600)
        self.proc = await asyncio.create_subprocess_exec(
            config.TOR_BIN, "-f", str(rc),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            start_new_session=True)

        deadline = config.TOR_BOOTSTRAP_TIMEOUT * 10
        for _ in range(deadline):
            await asyncio.sleep(0.1)
            if self.proc.returncode is not None:
                raise TorError(f"tor exited: {(self.log.read_text()[-600:] if self.log.exists() else 'no log')}")
            if self.log.exists() and BOOT_MARK in self.log.read_text(errors="replace"):
                return True
        await self.stop()
        raise TorError("tor did not bootstrap in time")

    async def _control(self, cmd: str) -> str:
        reader, writer = await asyncio.open_connection("127.0.0.1", self.control_port)
        try:
            cookie = (self.dir / "control_auth_cookie").read_bytes().hex()
            writer.write(f"AUTHENTICATE {cookie}\r\n".encode())
            await writer.drain()
            await reader.readline()
            writer.write(f"{cmd}\r\n".encode())
            await writer.drain()
            return (await reader.readline()).decode(errors="replace").strip()
        finally:
            writer.close()

    async def new_identity(self):
        resp = await self._control("SIGNAL NEWNYM")
        if not resp.startswith("250"):
            raise TorError(f"NEWNYM rejected: {resp}")
        await asyncio.sleep(1.5)
        return True

    async def stop(self):
        if self.proc and self.proc.returncode is None:
            self.proc.terminate()
            try:
                await asyncio.wait_for(self.proc.wait(), 5)
            except asyncio.TimeoutError:
                self.proc.kill()
        shutil.rmtree(self.dir, ignore_errors=True)
