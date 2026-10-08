"""Transport-independent client interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
import logging
from typing import Any

from .models import Capabilities, DeviceInfo, MediaStatus, SettingDef, SettingsWrite

_LOGGER = logging.getLogger(__name__)

_MISSING = object()

StateCallback = Callable[[dict[str, Any]], None]
"""Called with the changed keys (full state on snapshot)."""
EventCallback = Callable[[dict[str, Any]], None]
"""Called with every non-state message (events, media_status, voice.*, settings_changed)."""
ConnectionCallback = Callable[[bool], None]
BinaryCallback = Callable[[bytes], None]


def base_url(host: str, port: int, *, tls: bool = False) -> str:
    """Base URL of a display (IPv6 literals are bracketed)."""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    return f"{'https' if tls else 'http'}://{host}:{port}"


class ShellyElevateIntegrationApi(ABC):
    """Common interface of the v1 and legacy clients.

    Clients keep a flat state dict (see protocol-v1.md, "State keys") and notify
    subscribers on changes, so the Home Assistant side does not care whether the
    data came from a WebSocket push or from polling.
    """

    legacy: bool = False
    upgrade_available: bool = False
    """A legacy display now also answers protocol v1 (the app was updated)."""

    def __init__(self, host: str, port: int) -> None:
        """Initialize."""
        self.host = host
        self.port = port
        self.info: DeviceInfo | None = None
        self.state: dict[str, Any] = {}
        self.media: MediaStatus = MediaStatus()
        self.voice_config: dict[str, Any] | None = None
        """Last `voice.config`; the display sends it on connect, before the satellite entity exists."""
        self.settings: dict[str, Any] = {}
        self._connected = False
        self._state_cbs: list[StateCallback] = []
        self._event_cbs: list[EventCallback] = []
        self._conn_cbs: list[ConnectionCallback] = []
        self._binary_cbs: dict[int, list[BinaryCallback]] = {}

    # ---------------------------------------------------------------- lifecycle

    @abstractmethod
    async def connect(self) -> DeviceInfo:
        """Fetch info and start receiving updates (push or polling)."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Stop receiving updates."""

    @property
    def connected(self) -> bool:
        """Whether the display is currently reachable."""
        return self._connected

    @property
    def capabilities(self) -> Capabilities:
        """Capabilities of the connected display."""
        return self.info.capabilities if self.info else Capabilities()

    # ---------------------------------------------------------------- requests

    @abstractmethod
    async def command(self, action: str, /, **params: Any) -> dict[str, Any]:
        """Run a command (see protocol-v1.md, "Commands")."""

    @abstractmethod
    async def get_settings(self) -> dict[str, Any]:
        """Return all settings and update the cache."""

    @abstractmethod
    async def set_settings(self, changes: dict[str, Any]) -> SettingsWrite:
        """Apply partial settings and return all settings with what was written."""

    @abstractmethod
    async def get_settings_schema(self) -> list[SettingDef]:
        """Return the settings schema."""

    async def screenshot(self) -> bytes | None:
        """Return a PNG screenshot, or None if unsupported."""
        return None

    async def get_logs(self, lines: int = 500) -> str | None:
        """Return recent app log lines, or None if unsupported."""
        return None

    async def send_binary(self, channel: int, payload: bytes) -> None:  # noqa: B027
        """Send a binary frame to the display (unused in v1.0)."""

    # ---------------------------------------------------------------- subscriptions

    def subscribe_state(self, cb: StateCallback) -> Callable[[], None]:
        """Subscribe to state changes."""
        self._state_cbs.append(cb)
        return lambda: self._state_cbs.remove(cb)

    def subscribe_events(self, cb: EventCallback) -> Callable[[], None]:
        """Subscribe to events and other messages."""
        self._event_cbs.append(cb)
        return lambda: self._event_cbs.remove(cb)

    def subscribe_connection(self, cb: ConnectionCallback) -> Callable[[], None]:
        """Subscribe to connection changes."""
        self._conn_cbs.append(cb)
        return lambda: self._conn_cbs.remove(cb)

    def subscribe_binary(self, channel: int, cb: BinaryCallback) -> Callable[[], None]:
        """Subscribe to a binary channel."""
        self._binary_cbs.setdefault(channel, []).append(cb)
        return lambda: self._binary_cbs[channel].remove(cb)

    # ---------------------------------------------------------------- helpers for subclasses

    def _set_connected(self, connected: bool) -> None:
        if connected == self._connected:
            return
        self._connected = connected
        for cb in list(self._conn_cbs):
            _safe_call(cb, connected)

    def _apply_state(self, changes: dict[str, Any], *, snapshot: bool = False) -> None:
        if snapshot:
            self.state = dict(changes)
            changed = dict(changes)
        else:
            changed = {k: v for k, v in changes.items() if self.state.get(k, _MISSING) != v}
            if not changed:
                return
            self.state.update(changed)
        for cb in list(self._state_cbs):
            _safe_call(cb, changed)

    def _emit(self, message: dict[str, Any]) -> None:
        if message.get("type") == "media_status":
            self.media = MediaStatus.from_dict(message.get("status") or {})
        elif message.get("type") == "voice.config":
            self.voice_config = message
        elif message.get("type") == "settings_changed":
            self.settings.update(message.get("changes") or {})
        for cb in list(self._event_cbs):
            _safe_call(cb, message)

    def _emit_binary(self, channel: int, payload: bytes) -> None:
        for cb in list(self._binary_cbs.get(channel, ())):
            _safe_call(cb, payload)


def _safe_call(cb: Callable[..., None], *args: Any) -> None:
    try:
        cb(*args)
    except Exception:
        _LOGGER.exception("Error in ShellyElevate subscriber %s", cb)
