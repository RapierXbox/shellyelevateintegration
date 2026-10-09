"""ADB over TCP that fails fast when the display closes the connection.

adb-shell 0.4.4 treats an empty read as "no data yet" and keeps reading until its read
timeout. At EOF `StreamReader.read()` returns b"" without suspending, so that loop spins
and freezes the event loop. This transport turns EOF into an error instead.
"""

from __future__ import annotations

from typing import IO, TYPE_CHECKING, Literal, Protocol

from adb_shell.adb_device_async import AdbDeviceAsync

if TYPE_CHECKING:
    from adb_shell.auth.sign_pythonrsa import PythonRSASigner

    class TcpTransportAsync:
        """Typed view of the adb-shell transport (the library has no type hints)."""

        _host: str
        _port: int

        def __init__(self, host: str, port: int = 5555) -> None: ...

        async def bulk_read(self, numbytes: int, transport_timeout_s: float | None) -> bytes: ...

else:
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


class AdbDevice(Protocol):
    """The parts of the adb-shell AdbDeviceAsync used here (the library has no type hints)."""

    async def connect(
        self,
        rsa_keys: list[PythonRSASigner] | None = None,
        transport_timeout_s: float | None = None,
        auth_timeout_s: float = ...,
    ) -> bool:
        """Open the connection and authenticate."""

    async def shell(
        self,
        command: str,
        transport_timeout_s: float | None = None,
        read_timeout_s: float = ...,
        timeout_s: float | None = None,
        decode: Literal[True] = True,
    ) -> str:
        """Run a shell command and return its decoded output."""

    async def exec_out(
        self,
        command: str,
        transport_timeout_s: float | None = None,
        read_timeout_s: float = ...,
        timeout_s: float | None = None,
        *,
        decode: Literal[False],
    ) -> bytes:
        """Run an exec-out command and return its raw output."""

    async def reboot(
        self,
        fastboot: bool = False,
        transport_timeout_s: float | None = None,
        read_timeout_s: float = ...,
        timeout_s: float | None = None,
    ) -> None:
        """Reboot the device."""

    async def push(
        self,
        local_path: str | IO[bytes],
        device_path: str,
        *,
        transport_timeout_s: float | None = None,
        read_timeout_s: float = ...,
    ) -> None:
        """Push a file to the device."""

    async def close(self) -> None:
        """Close the connection."""


def create_device(host: str, port: int) -> AdbDevice:
    """An ADB device using the EOF-safe transport."""
    device: AdbDevice = AdbDeviceAsync(EofSafeTcpTransport(host, port), default_transport_timeout_s=CONNECT_TIMEOUT)
    return device
