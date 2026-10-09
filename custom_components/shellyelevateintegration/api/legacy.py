"""Client for the current (pre-v1) ShellyElevate app.

The legacy app has an unauthenticated HTTP API on port 8080 and no push channel, so this
client polls and maps everything onto the v1 state keys and commands. Features the legacy
app cannot provide (media status, voice, BLE, screenshots) are simply not advertised in
the capabilities.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from typing import Any, overload

import aiohttp

from .base import ShellyElevateIntegrationApi, base_url
from .client import async_probe
from .errors import (
    ShellyElevateIntegrationAuthError,
    ShellyElevateIntegrationCommandError,
    ShellyElevateIntegrationConnectionError,
    ShellyElevateIntegrationError,
    ShellyElevateIntegrationUnsupportedError,
)
from .models import (
    DEFAULT_NAME,
    LEGACY_PORT,
    MODELS,
    POWER_BASE_MODELS,
    Capabilities,
    DeviceInfo,
    SettingDef,
    SettingsWrite,
)

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = 8
FAST_INTERVAL = 5  # relays, inputs, night mode, screen
SLOW_INTERVAL = 30  # sensors, settings
FAILURES_BEFORE_UNAVAILABLE = 3
NO_SENSOR = -900
"""Readings at or below this are the app's "no such sensor" value (-999)."""
PRESENCE_DISTANCE = 0.5

TOAST_JS = """(function(){var d=document.createElement('div');d.textContent=%s;
d.style.cssText='position:fixed;left:50%%;bottom:8%%;transform:translateX(-50%%);z-index:2147483647;'
+'background:rgba(20,20,20,.88);color:#fff;font:500 22px/1.35 sans-serif;padding:16px 24px;'
+'border-radius:14px;max-width:80vw;box-shadow:0 6px 24px rgba(0,0,0,.4);text-align:center';
document.body.appendChild(d);setTimeout(function(){d.remove()},%d);})();"""


class LegacyClient(ShellyElevateIntegrationApi):
    """Polling client for the legacy HTTP API."""

    legacy = True

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int = LEGACY_PORT,
        device_id: str | None = None,
    ) -> None:
        """Initialize."""
        super().__init__(host, port)
        self._session = session
        self._base = base_url(host, port)
        self._device_id = device_id
        self._poll_task: asyncio.Task[None] | None = None
        self._failures = 0
        self._last_slow = 0.0
        self._last_upgrade_check = -float(SLOW_INTERVAL)
        # The legacy API has no readback for these, track them optimistically.
        self._optimistic: dict[str, Any] = {"screen.on": True}

    async def _call(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            async with self._session.request(
                method,
                f"{self._base}{path}",
                data=json.dumps(body) if body is not None else None,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as resp:
                try:
                    data = await resp.json(content_type=None)
                except ValueError:
                    data = {}
                if resp.status >= 400 or (isinstance(data, dict) and data.get("success") is False):
                    error = data.get("error") if isinstance(data, dict) else None
                    raise ShellyElevateIntegrationCommandError(str(resp.status), error)
                return data if isinstance(data, dict) else {}
        except (aiohttp.ClientError, TimeoutError) as err:
            raise ShellyElevateIntegrationConnectionError(f"{method} {path} failed: {err}") from err

    async def _get(self, path: str) -> dict[str, Any] | None:
        """GET that returns None instead of raising on command errors (missing sensors)."""
        try:
            return await self._call("GET", path)
        except ShellyElevateIntegrationCommandError:
            return None

    # ---------------------------------------------------------------- lifecycle

    async def connect(self) -> DeviceInfo:
        """Fetch info, do a first poll, start polling."""
        try:
            root = await self._call("GET", "/")
        except ShellyElevateIntegrationError:
            # An updated app may have switched the legacy API off.
            if await self._check_upgrade():
                raise ShellyElevateIntegrationAuthError("The app was updated to API v1; pair again") from None
            raise
        await self.get_settings()
        codename = str(root.get("modelName") or "STARGATE").upper()
        # The app treats unknown hardware like the original Wall Display; so do we, but we
        # don't pretend to know its SKU.
        known = MODELS.get(codename)
        sku, _name, relays, inputs, buttons, proximity, power_button = known or MODELS["STARGATE"]
        caps = Capabilities(
            relays=relays,
            optional_relays_from=1 if codename in POWER_BASE_MODELS else None,
            inputs=_int(root.get("numOfInputs"), inputs),
            buttons=_int(root.get("numOfButtons"), buttons),
            proximity=str(root.get("proximity", proximity)).lower() == "true",
            power_button=power_button,
            speaker=True,
        )
        self.info = DeviceInfo(
            device_id=self._device_id or self.settings.get("mqttDeviceId") or f"shellyelevate-{self.host}",
            name=root.get("name") or DEFAULT_NAME,
            model=sku if known else None,
            codename=codename,
            fw_version=root.get("version"),
            api_version=None,
            legacy=True,
            capabilities=caps,
        )
        await self._poll(slow=True)
        self._set_connected(True)
        self._poll_task = asyncio.create_task(self._poll_loop(), name=f"shellyelevateintegration poll {self.host}")
        return self.info

    async def disconnect(self) -> None:
        """Stop polling."""
        if self._poll_task is not None:
            self._poll_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._poll_task
            self._poll_task = None
        self._set_connected(False)

    async def _poll_loop(self) -> None:
        while True:
            await asyncio.sleep(FAST_INTERVAL)
            slow = time.monotonic() - self._last_slow >= SLOW_INTERVAL
            try:
                await self._poll(slow=slow)
            except Exception as err:  # the loop must survive anything the app sends
                self._failures += 1
                if isinstance(err, ShellyElevateIntegrationError) or self._failures > 1:
                    _LOGGER.debug("Poll of %s failed (%s): %r", self.host, self._failures, err)
                else:
                    _LOGGER.warning("Unexpected error polling %s", self.host, exc_info=True)
                if self._failures >= FAILURES_BEFORE_UNAVAILABLE:
                    self._set_connected(False)
                    await self._check_upgrade()
                continue
            self._failures = 0
            self._set_connected(True)

    async def _poll(self, *, slow: bool) -> None:
        caps = self.capabilities
        changes: dict[str, Any] = dict(self._optimistic)
        for idx in range(caps.relays):
            if (data := await self._get(f"/device/relay?num={idx}")) is not None:
                changes[f"relay.{idx}"] = bool(data.get("state"))
        for idx in range(caps.inputs):
            if (data := await self._get(f"/device/input?num={idx}")) is not None and "state" in data:
                changes[f"input.{idx}"] = data["state"]
        if (data := await self._get("/device/night_mode")) is not None:
            changes["night_mode"] = bool(data.get("state"))
        if slow:
            self._last_slow = time.monotonic()
            root = await self._get("/")
            version = root.get("version") if root else None
            if version and self.info is not None and str(version) != self.info.fw_version:
                # e.g. after an app update over ADB
                self.info.fw_version = str(version)
                self._emit({"type": "_info_changed"})
            # Models without a sensor (XL, X2i, X1i) answer -999 instead of an error.
            for key, path in (
                ("temperature", "/device/getTemperature"),
                ("humidity", "/device/getHumidity"),
                ("lux", "/device/getLux"),
            ):
                if (data := await self._get(path)) and (value := _reading(data.get(key))) is not None:
                    changes[key] = value
                    setattr(caps, key, True)
            if (
                caps.proximity
                and (data := await self._get("/device/getProximity"))
                and (distance := _reading(data.get("distance"))) is not None
            ):
                changes["proximity"] = distance
                # the app has no presence value; near (or 0 on binary sensors) means present
                changes["presence"] = distance < PRESENCE_DISTANCE
            if (data := await self._get("/device/dimmer")) is not None and "brightness" in data:
                caps.dimmer = True
                changes["dimmer.on"] = bool(data.get("on"))
                changes["dimmer.brightness"] = data.get("brightness")
                changes["dimmer.power"] = data.get("power")
            if (data := await self._get("/media/volume")) is not None and (
                volume := _float(data.get("volume"))
            ) is not None:
                self._update_media(volume=volume)
            await self.get_settings()
            await self._check_upgrade()
        if (brightness := _int(self.settings.get("brightness"))) is not None:
            changes["screen.brightness"] = brightness
        if "automaticBrightness" in self.settings:
            changes["screen.auto_brightness"] = bool(self.settings["automaticBrightness"])
        if "webviewUrl" in self.settings:
            changes["webview.url"] = self.settings["webviewUrl"]
        # Available first: listeners (the thermostat) act on fresh state only when available.
        self._failures = 0
        self._set_connected(True)
        self._apply_state(changes)

    async def _check_upgrade(self) -> bool:
        """Whether the display now speaks protocol v1 (checked at most every SLOW_INTERVAL)."""
        if self.upgrade_available or time.monotonic() - self._last_upgrade_check < SLOW_INTERVAL:
            return self.upgrade_available
        self._last_upgrade_check = time.monotonic()
        try:
            hello = await async_probe(self._session, self.host, self.port, plain_first=True)
        except ShellyElevateIntegrationError:
            return False
        if hello.legacy:
            return False
        expected = self.info.device_id if self.info else self._device_id
        if expected is not None and hello.device_id != expected:
            _LOGGER.debug("%s now answers as %s, not %s; not an upgrade", self.host, hello.device_id, expected)
            return False
        _LOGGER.info("%s now runs ShellyElevate with API %s", self.host, hello.api_version)
        self.upgrade_available = True
        self._emit({"type": "_upgrade_available"})
        return True

    # ---------------------------------------------------------------- settings

    async def get_settings(self) -> dict[str, Any]:
        """Return all settings."""
        data = await self._call("GET", "/settings")
        new = data.get("settings")
        if not isinstance(new, dict):
            raise ShellyElevateIntegrationCommandError("invalid_response", "GET /settings returned no settings")
        changed = {k: v for k, v in new.items() if self.settings.get(k) != v}
        self.settings = new
        if changed and self.info is not None:
            self._emit({"type": "settings_changed", "changes": changed})
        return self.settings

    async def set_settings(self, changes: dict[str, Any]) -> SettingsWrite:
        """Apply partial settings (and report them: the legacy app sends no settings_changed)."""
        data = await self._call("POST", "/settings", changes)
        if "settings" in data:
            self.settings = dict(data["settings"])
        else:
            self.settings.update(changes)
        applied = {key: self.settings.get(key, value) for key, value in changes.items()}
        self._emit({"type": "settings_changed", "changes": applied})
        return SettingsWrite(self.settings, applied)

    async def get_settings_schema(self) -> list[SettingDef]:
        """The legacy app has no schema endpoint; use the built-in one."""
        from .legacy_schema import LEGACY_SCHEMA

        return [SettingDef.from_dict(item) for item in LEGACY_SCHEMA]

    # ---------------------------------------------------------------- commands

    async def command(self, action: str, /, **params: Any) -> dict[str, Any]:
        """Map v1 commands onto legacy endpoints."""
        handler = getattr(self, f"_cmd_{action.replace('.', '_')}", None)
        if handler is None:
            raise ShellyElevateIntegrationUnsupportedError(f"{action} is not supported by the legacy app")
        result = await handler(**params)
        return result or {}

    async def _cmd_relay_set(self, index: int, on: bool) -> None:
        await self._call("POST", "/device/relay", {"num": index, "state": on})
        self._apply_state({f"relay.{index}": on})

    async def _cmd_dimmer_set(self, on: bool | None = None, brightness: int | None = None) -> None:
        if brightness is not None:
            await self._call("POST", "/device/dimmer", {"brightness": brightness})
            self._apply_state({"dimmer.brightness": brightness, "dimmer.on": brightness > 0})
        if on is not None:
            await self._call("POST", "/device/dimmer", {"on": on})
            self._apply_state({"dimmer.on": on})

    async def _cmd_screen_wake(self) -> None:
        await self._call("POST", "/device/wake")
        self._optimistic["screen.on"] = True
        self._apply_state({"screen.on": True})

    async def _cmd_screen_sleep(self) -> None:
        await self._call("POST", "/device/sleep")
        self._optimistic["screen.on"] = False
        self._apply_state({"screen.on": False})

    async def _cmd_screen_set(self, brightness: int | None = None, auto: bool | None = None) -> None:
        changes: dict[str, Any] = {}
        if brightness is not None:
            changes["brightness"] = int(brightness)
            changes["automaticBrightness"] = False if auto is None else auto
        elif auto is not None:
            changes["automaticBrightness"] = auto
        if changes:
            await self.set_settings(changes)
            state: dict[str, Any] = {"screen.auto_brightness": changes["automaticBrightness"]}
            if brightness is not None:
                state["screen.brightness"] = int(brightness)
            self._apply_state(state)

    async def _cmd_night_mode_set(self, on: bool) -> None:
        await self._call("POST", "/device/night_mode", {"state": on})
        self._apply_state({"night_mode": on})

    async def _cmd_webview_reload(self) -> None:
        await self._call("GET", "/webview/refresh")

    async def _cmd_webview_navigate(self, url: str | None = None, path: str | None = None) -> None:
        if url is None:
            if path is None:
                raise ShellyElevateIntegrationCommandError("invalid_params", "url or path required")
            base = str(self.settings.get("webviewUrl", "")).rstrip("/")
            url = f"{base}/{path.lstrip('/')}"
        await self._inject(f"window.location.assign({json.dumps(url)});")

    async def _cmd_ui_notify(
        self, message: str, title: str | None = None, duration: float = 5, level: str = "info"
    ) -> None:
        text = f"{title}\n{message}" if title else message
        await self._inject(TOAST_JS % (json.dumps(text), int(duration * 1000)))

    async def _cmd_device_reboot(self) -> None:
        await self._call("POST", "/device/reboot")

    async def _cmd_media_play(
        self,
        url: str,
        channel: str = "music",
        volume: float | None = None,
        title: str | None = None,
        **_ignored: Any,
    ) -> None:
        vol = volume if volume is not None else (self.media.volume if self.media.volume is not None else 0.5)
        await self._call("POST", "/media/play", {"url": url, "music": channel == "music", "volume": vol})
        if channel == "music":
            self._update_media(state="playing", url=url, title=title, volume=vol)

    async def _cmd_media_pause(self) -> None:
        await self._call("POST", "/media/pause")
        self._update_media(state="paused")

    async def _cmd_media_resume(self) -> None:
        await self._call("POST", "/media/resume")
        self._update_media(state="playing")

    async def _cmd_media_stop(self) -> None:
        await self._call("POST", "/media/stop")
        self._update_media(state="idle", url=None, title=None)

    async def _cmd_media_volume(self, volume: float | None = None, muted: bool | None = None) -> None:
        if muted is not None:
            raise ShellyElevateIntegrationUnsupportedError("mute is not supported by the legacy app")
        if volume is not None:
            await self._call("POST", "/media/volume", {"volume": volume})
            self._update_media(volume=volume)

    async def _inject(self, javascript: str) -> None:
        await self._call("POST", "/webview/inject", {"javascript": javascript})

    def _update_media(self, **changes: Any) -> None:
        self._emit({"type": "media_status", "status": {**self.media.as_dict(), **changes}})


@overload
def _int(value: Any) -> int | None: ...
@overload
def _int(value: Any, default: int) -> int: ...
def _int(value: Any, default: int | None = None) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _reading(value: Any) -> float | None:
    """A sensor value, or None for garbage and the app's "no sensor" marker."""
    number = _float(value)
    return None if number is None or number <= NO_SENSOR else number
