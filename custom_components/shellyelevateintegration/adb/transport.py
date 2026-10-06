"""ADB over TCP that fails fast when the display closes the connection.

adb-shell 0.4.4 treats an empty read as "no data yet" and keeps reading until its read
timeout. At EOF `StreamReader.read()` returns b"" without suspending, so that loop spins
and freezes the event loop. This transport turns EOF into an error instead.
"""

from __future__ import annotations

from adb_shell.adb_device_async import AdbDeviceAsync
from adb_shell.transport.tcp_transport_async import TcpTransportAsync

CONNECT_TIMEOUT = 9.0
"""Socket and handshake timeout. Commands pass their own (see AdbManager)."""


class AdbConnectionClosed(ConnectionResetError):
    """The display closed the ADB connection."""


class EofSafeTcpTransport(TcpTransportAsync):
    """TcpTransportAsync that raises on EOF instead of returning b""."""

    async def bulk_read(self, numbytes: int, transport_timeout_s: float | None) -> bytes:
        """Read up to `numbytes`; raise if the peer has closed the connection."""
        data = await super().bulk_read(numbytes, transport_timeout_s)
        if not data and numbytes > 0:
            raise AdbConnectionClosed(f"{self._host}:{self._port} closed the ADB connection")
        return data


def create_device(host: str, port: int) -> AdbDeviceAsync:
    """An ADB device using the EOF-safe transport."""
    return AdbDeviceAsync(EofSafeTcpTransport(host, port), default_transport_timeout_s=CONNECT_TIMEOUT)
