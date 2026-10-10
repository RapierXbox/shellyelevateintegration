"""A fake ShellyElevate display: stands in for the v1 and the legacy API client."""

from __future__ import annotations

from collections.abc import Generator
import contextlib
import copy
from typing import Any
from unittest.mock import AsyncMock, patch
from urllib.parse import urlsplit

from custom_components.shellyelevateintegration.api import (
    Capabilities,
    DeviceInfo,
    Hello,
    SettingDef,
    SettingsWrite,
    ShellyElevateIntegrationApi,
    ShellyElevateIntegrationCommandError,
)
from custom_components.shellyelevateintegration.api.app_schema import with_app_rules
from custom_components.shellyelevateintegration.api.client import _with_transport_caps
from custom_components.shellyelevateintegration.api.legacy_schema import LEGACY_SCHEMA

from .const import (
    FINGERPRINT,
    INFO,
    LEGACY_DEVICE_ID,
    LEGACY_PORT,
    LEGACY_ROOT,
    LEGACY_SETTINGS,
    PAIRING_ID,
    PORT,
    SCHEMA,
    SETTINGS,
    STATE,
    TOKEN,
)

PACKAGE = "custom_components.shellyelevateintegration"
PNG = b"\x89PNG\r\n\x1a\nfake-screenshot"


class FakeDisplay:
    """What a display answers; the clients the integration creates read it."""

    def __init__(self, *, legacy: bool = False) -> None:
        """Initialize with a Wall Display X2 running the current app (or the legacy app)."""
        self.legacy = legacy
        self.info: dict[str, Any] = copy.deepcopy(INFO)
        self.settings: dict[str, Any] = copy.deepcopy(LEGACY_SETTINGS if legacy else SETTINGS)
        self.schema: list[dict[str, Any]] = copy.deepcopy(SCHEMA)
        self.state: dict[str, Any] = copy.deepcopy(STATE)
        self.legacy_caps = Capabilities(
            relays=2, optional_relays_from=1, inputs=1, proximity=True, speaker=True, temperature=True, lux=True
        )
        self.connect_error: Exception | None = None
        self.settings_error: Exception | None = None
        self.set_settings_error: Exception | None = None
        self.schema_error: Exception | None = None
        self.logs_error: Exception | None = None
        self.revoke_error: Exception | None = None
        self.info_errors: list[Exception] = []
        self.screenshot_error: Exception | None = None
        self.screenshot: bytes | None = PNG
        self.logs: str | None = "line 1\nline 2\n"
        self.upgrade_available = False
        self.voice_config: dict[str, Any] | None = None
        self.command_errors: dict[str, Exception] = {}
        self.command_results: dict[str, dict[str, Any]] = {}
        self.commands: list[tuple[str, dict[str, Any]]] = []
        self.writes: list[dict[str, Any]] = []
        self.clients: list[FakeClient] = []
        self.mocks: dict[str, AsyncMock] = {}
        self.others: dict[str, FakeDisplay] = {}
        """Further displays the clients of this one reach, by host."""
        self.ha_login_supported = False
        """The app knows ha_login.* (off by default like an app from before the dashboard login)."""
        self.ha_login: dict[str, Any] | None = None
        """The dashboard login the app holds."""
        self.ha_login_refused = False
        self.login_commands: list[tuple[str, dict[str, Any]]] = []
        """ha_login.* commands (kept out of `commands` so the background login check stays invisible)."""

    def ha_login_origin(self) -> str | None:
        """Origin of the dashboard url like the app derives it."""
        url = self.settings.get("webviewUrl") or ""
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            return None
        default = {"http": 80, "https": 443}[parts.scheme]
        port = "" if parts.port in (None, default) else f":{parts.port}"
        return f"{parts.scheme}://{parts.hostname}{port}"

    def ha_login_status(self) -> dict[str, Any]:
        """What ha_login.status answers."""
        origin = self.ha_login_origin()
        if self.ha_login is not None and self.ha_login["origin"] != origin:
            self.ha_login = None  # the app wipes a login for another origin
        state = "none"
        if self.ha_login is not None:
            state = "invalid" if self.ha_login_refused else "ok"
        return {
            "state": state,
            "user": self.ha_login["user"] if self.ha_login else None,
            "origin": origin,
            "client_id": f"{origin}/" if origin else None,
        }

    def ha_login_command(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        """Answer an ha_login.* command like the app."""
        self.login_commands.append((action, params))
        if not self.ha_login_supported:
            raise ShellyElevateIntegrationCommandError("unknown_action", action)
        if (error := self.command_errors.get(action)) is not None:
            raise error
        if action == "ha_login.set":
            origin = self.ha_login_origin()
            if params["origin"] != origin or params["client_id"] != f"{origin}/":
                raise ShellyElevateIntegrationCommandError("origin_mismatch", "the dashboard url is elsewhere")
            self.ha_login = dict(params)
            self.ha_login_refused = False
        elif action == "ha_login.clear":
            self.ha_login = None
        return self.ha_login_status()

    @property
    def client(self) -> FakeClient:
        """The client created last (the one of the loaded entry)."""
        return self.clients[-1]

    def hello(self, **changes: Any) -> Hello:
        """What async_probe finds on this display."""
        if self.legacy:
            hello = Hello(
                device_id=self.settings.get("mqttDeviceId") or LEGACY_DEVICE_ID,
                name=LEGACY_ROOT["name"],
                model=None,
                codename=LEGACY_ROOT["modelName"],
                fw_version=LEGACY_ROOT["version"],
                api_version=None,
                mac=None,
                paired=False,
                legacy=True,
                port=LEGACY_PORT,
            )
        else:
            hello = Hello(
                device_id=self.info["id"],
                name=self.info["name"],
                model=self.info["model"],
                codename=self.info["codename"],
                fw_version=self.info["fw"],
                api_version=self.info["api"],
                mac=self.info["mac"],
                paired=False,
                legacy=False,
                port=PORT,
                fingerprint=FINGERPRINT,
            )
        for key, value in changes.items():
            setattr(hello, key, value)
        return hello

    def known_keys(self) -> set[str]:
        """Keys the display accepts."""
        if self.legacy:
            return set(self.settings) | {item["key"] for item in LEGACY_SCHEMA}
        return set(self.settings) | {item["key"] for item in self.schema}


class FakeClient(ShellyElevateIntegrationApi):
    """Both API clients; `display` is set on the class by `client_class`."""

    display: FakeDisplay
    displays: dict[str, FakeDisplay]
    """Further displays by host (several displays in one test)."""

    def __init__(self, session: Any, host: str, port: int = PORT, *args: Any) -> None:
        """Take the arguments of either client."""
        super().__init__(host, port)
        self.display = self.displays.get(host, self.display)
        self.legacy = self.display.legacy
        if self.legacy:
            self.device_id = args[0] if args else None
            self.token = None
            self.fingerprint = None
        else:
            self.token = args[0] if args else ""
            self.fingerprint = args[1] if len(args) > 1 else None
            self.device_id = args[2] if len(args) > 2 else None
        self.upgrade_available = self.display.upgrade_available
        self.revoked = False
        self.display.clients.append(self)

    # ---------------------------------------------------------------- lifecycle

    async def connect(self) -> DeviceInfo:
        """Connect like the real clients: info, state, settings."""
        if self.display.connect_error is not None:
            raise self.display.connect_error
        if self.legacy:
            self.info = DeviceInfo(
                device_id=self.device_id or LEGACY_DEVICE_ID,
                name=LEGACY_ROOT["name"],
                model=self.display.info["model"],
                codename=LEGACY_ROOT["modelName"],
                fw_version=LEGACY_ROOT["version"],
                api_version=None,
                legacy=True,
                capabilities=copy.deepcopy(self.display.legacy_caps),
            )
        else:
            self.info = _with_transport_caps(DeviceInfo.from_v1(copy.deepcopy(self.display.info)))
        self._apply_state(copy.deepcopy(self.display.state), snapshot=True)
        self.settings = copy.deepcopy(self.display.settings)
        self.voice_config = copy.deepcopy(self.display.voice_config)
        self._set_connected(True)
        return self.info

    async def get_info(self) -> DeviceInfo:
        """Info (checks the token)."""
        if self.display.info_errors:
            raise self.display.info_errors.pop(0)
        return DeviceInfo.from_v1(copy.deepcopy(self.display.info))

    async def disconnect(self) -> None:
        """Disconnect."""
        self._set_connected(False)

    # ---------------------------------------------------------------- requests

    async def command(self, action: str, /, **params: Any) -> dict[str, Any]:
        """Record the command."""
        if action.startswith("ha_login."):
            return self.display.ha_login_command(action, params)
        self.display.commands.append((action, params))
        if (error := self.display.command_errors.get(action)) is not None:
            raise error
        return dict(self.display.command_results.get(action, {}))

    async def get_settings(self) -> dict[str, Any]:
        """All settings."""
        if self.display.settings_error is not None:
            raise self.display.settings_error
        self.settings = copy.deepcopy(self.display.settings)
        return self.settings

    async def set_settings(self, changes: dict[str, Any]) -> SettingsWrite:
        """Write the keys the display knows."""
        if self.display.set_settings_error is not None:
            raise self.display.set_settings_error
        self.display.writes.append(dict(changes))
        known = self.display.known_keys()
        ignored = [key for key in changes if key not in known]
        defaults = {item["key"]: item.get("default") for item in self.display.schema}
        for key, value in changes.items():
            if key not in ignored:
                self.display.settings[key] = defaults.get(key) if value is None else value
        self.settings = copy.deepcopy(self.display.settings)
        applied = {key: self.settings.get(key) for key in changes if key not in ignored}
        if self.legacy:
            self._emit({"type": "settings_changed", "changes": applied})
        return SettingsWrite(self.settings, applied, ignored)

    async def get_settings_schema(self) -> list[SettingDef]:
        """The schema (the built-in one for the legacy app)."""
        if self.legacy:
            return [SettingDef.from_dict(item) for item in LEGACY_SCHEMA]
        if self.display.schema_error is not None:
            raise self.display.schema_error
        return with_app_rules([SettingDef.from_dict(copy.deepcopy(item)) for item in self.display.schema])

    async def screenshot(self) -> bytes | None:
        """A PNG."""
        if self.display.screenshot_error is not None:
            raise self.display.screenshot_error
        return self.display.screenshot

    async def get_logs(self, lines: int = 500) -> str | None:
        """App log."""
        if self.display.logs_error is not None:
            raise self.display.logs_error
        return self.display.logs

    async def revoke(self) -> None:
        """Revoke the token."""
        if self.display.revoke_error is not None:
            raise self.display.revoke_error
        self.revoked = True

    async def rotate_token(self) -> str:
        """New token."""
        self.token = f"{TOKEN}-rotated"
        return self.token

    # ---------------------------------------------------------------- display -> Home Assistant

    def push_state(self, changes: dict[str, Any], *, snapshot: bool = False) -> None:
        """The display reports changed state."""
        self.display.state.update(changes)
        self._apply_state(changes, snapshot=snapshot)

    def push(self, message: dict[str, Any]) -> None:
        """The display sends a message (event, media_status, settings_changed, ...)."""
        if message.get("type") == "settings_changed":
            self.display.settings.update(message.get("changes") or {})
        self._emit(message)

    def push_binary(self, channel: int, payload: bytes) -> None:
        """A binary frame."""
        self._emit_binary(channel, payload)

    def set_available(self, available: bool) -> None:
        """The connection drops or comes back."""
        self._set_connected(available)


def client_class(display: FakeDisplay) -> type[FakeClient]:
    """A FakeClient class bound to `display`."""
    return type("BoundFakeClient", (FakeClient,), {"display": display, "displays": display.others})


@contextlib.contextmanager
def patch_display(display: FakeDisplay) -> Generator[dict[str, AsyncMock]]:
    """Let the integration (setup, config flow, installer) talk to `display`."""
    v1 = client_class(display)
    legacy = client_class(display)
    probe = AsyncMock(side_effect=lambda *args, **kwargs: display.hello())
    pair_start = AsyncMock(return_value=PAIRING_ID)
    pair_confirm = AsyncMock(return_value=TOKEN)
    with (
        patch(f"{PACKAGE}.ShellyElevateIntegrationClient", v1),
        patch(f"{PACKAGE}.LegacyClient", legacy),
        patch(f"{PACKAGE}.config_flow.ShellyElevateIntegrationClient", v1),
        patch(f"{PACKAGE}.config_flow.LegacyClient", legacy),
        patch(f"{PACKAGE}.config_flow.async_probe", probe),
        patch(f"{PACKAGE}.config_flow.async_pair_start", pair_start),
        patch(f"{PACKAGE}.config_flow.async_pair_confirm", pair_confirm),
        patch(f"{PACKAGE}.installer.ShellyElevateIntegrationClient", v1),
        patch(f"{PACKAGE}.installer.LegacyClient", legacy),
    ):
        yield {"probe": probe, "pair_start": pair_start, "pair_confirm": pair_confirm}


def entity_id(hass: Any, domain: str, key: str, device_id: str | None = None) -> str:
    """Entity id of the entity `key` (unique id suffix) of the display."""
    from homeassistant.helpers import entity_registry as er

    from custom_components.shellyelevateintegration.const import DOMAIN

    from .const import DEVICE_ID

    found = er.async_get(hass).async_get_entity_id(domain, DOMAIN, f"{device_id or DEVICE_ID}_{key}")
    assert found is not None, f"no {domain} entity {key}"
    return found
