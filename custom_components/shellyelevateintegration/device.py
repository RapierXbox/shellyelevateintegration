"""Runtime object for one Shelly Wall Display."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo as HADeviceInfo

from .api import ShellyElevateIntegrationApi, ShellyElevateIntegrationError
from .api.base import base_url
from .api.models import DeviceInfo, SettingDef
from .const import DOMAIN, EVENT_SHELLY_ELEVATE, MANUFACTURER

if TYPE_CHECKING:
    from .adb.manager import AdbManager
    from .image import ShellyElevateIntegrationScreenshot
    from .permissions import PermissionGuard
    from .settings.backups import BackupManager

_LOGGER = logging.getLogger(__name__)

type ShellyElevateIntegrationConfigEntry = ConfigEntry[ShellyElevateIntegrationDevice]


@dataclass
class _Listeners:
    state: set[Callable[[dict[str, Any]], None]] = field(default_factory=set)
    message: set[Callable[[dict[str, Any]], None]] = field(default_factory=set)
    availability: set[Callable[[], None]] = field(default_factory=set)


class ShellyElevateIntegrationDevice:
    """Glue between an API client and the Home Assistant entities."""

    def __init__(
        self, hass: HomeAssistant, entry: ShellyElevateIntegrationConfigEntry, client: ShellyElevateIntegrationApi
    ) -> None:
        """Initialize."""
        self.hass = hass
        self.entry = entry
        self.client = client
        self._listeners = _Listeners()
        self._unsubs: list[Callable[[], None]] = []
        self.backups: BackupManager | None = None
        self.adb: AdbManager | None = None
        self.permissions: PermissionGuard | None = None
        self.screenshot_entity: ShellyElevateIntegrationScreenshot | None = None
        self.voice_enabled = False
        self.device_entry_id: str | None = None
        self._schema: list[SettingDef] | None = None

    # ---------------------------------------------------------------- properties

    @property
    def info(self) -> DeviceInfo:
        """Device info (only valid after setup)."""
        assert self.client.info is not None
        return self.client.info

    @property
    def device_id(self) -> str:
        """Stable device id: the id the entry was paired with."""
        return self.entry.unique_id or self.info.device_id

    @property
    def available(self) -> bool:
        """Whether the display is reachable."""
        return self.client.connected

    @property
    def state(self) -> dict[str, Any]:
        """Current flat state."""
        return self.client.state

    @property
    def settings(self) -> dict[str, Any]:
        """Cached settings."""
        return self.client.settings

    @property
    def legacy(self) -> bool:
        """Whether this is a legacy (pre-v1) app."""
        return self.client.legacy

    @property
    def device_info(self) -> HADeviceInfo:
        """Device registry info."""
        info = self.info
        device = HADeviceInfo(
            identifiers={(DOMAIN, self.device_id)},
            manufacturer=MANUFACTURER,
            model=info.model_name,
            model_id=info.model,
            name=self.entry.title,
            sw_version=info.fw_version,
            configuration_url=base_url(self.client.host, self.client.port, tls=not self.client.legacy),
        )
        if info.mac:
            device["connections"] = {(dr.CONNECTION_NETWORK_MAC, dr.format_mac(info.mac))}
        if info.android:
            device["hw_version"] = f"Android {info.android}"
        return device

    # ---------------------------------------------------------------- lifecycle

    async def async_setup(self) -> None:
        """Connect the client callbacks. The client must already be connected."""
        self._unsubs += [
            self.client.subscribe_state(self._on_state),
            self.client.subscribe_events(self._on_message),
            self.client.subscribe_connection(self._on_connection),
        ]
        registry = dr.async_get(self.hass)
        device = registry.async_get_or_create(config_entry_id=self.entry.entry_id, **self.device_info)
        self.device_entry_id = device.id
        if self.client.upgrade_available:
            self.entry.async_start_reauth(self.hass)

    async def async_shutdown(self) -> None:
        """Unsubscribe from the client and disconnect."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        await self.client.disconnect()

    # ---------------------------------------------------------------- listeners

    @callback
    def async_add_state_listener(self, cb: Callable[[dict[str, Any]], None]) -> Callable[[], None]:
        """Listen for state changes (called with the changed keys)."""
        self._listeners.state.add(cb)
        return lambda: self._listeners.state.discard(cb)

    @callback
    def async_add_message_listener(self, cb: Callable[[dict[str, Any]], None]) -> Callable[[], None]:
        """Listen for events / media_status / voice / settings messages."""
        self._listeners.message.add(cb)
        return lambda: self._listeners.message.discard(cb)

    @callback
    def async_add_availability_listener(self, cb: Callable[[], None]) -> Callable[[], None]:
        """Listen for availability changes."""
        self._listeners.availability.add(cb)
        return lambda: self._listeners.availability.discard(cb)

    @callback
    def _on_state(self, changes: dict[str, Any]) -> None:
        for cb in list(self._listeners.state):
            _safe_call(cb, changes)

    @callback
    def _on_message(self, message: dict[str, Any]) -> None:
        if message.get("type") == "event":
            self.hass.bus.async_fire(
                EVENT_SHELLY_ELEVATE,
                {"device_id": self.device_entry_id, "entry_id": self.entry.entry_id, **message},
            )
        elif message.get("type") in ("_auth_failed", "_upgrade_available"):
            # The upgrade from the legacy app reuses the reauth flow: pair, then switch to v1.
            self.entry.async_start_reauth(self.hass)
            return
        elif message.get("type") == "_incompatible":
            # Setup then fails with the incompatible_api error the user can see.
            self.hass.config_entries.async_schedule_reload(self.entry.entry_id)
            return
        elif message.get("type") == "_info_changed":
            self._async_refresh_device_registry()
        for cb in list(self._listeners.message):
            _safe_call(cb, message)

    @callback
    def _on_connection(self, connected: bool) -> None:
        if connected:
            self._schema = None  # the app may have been updated while it was away
            if not self.legacy and self.entry.unique_id and self.info.device_id != self.entry.unique_id:
                # another display took over the address: setup then fails with a clear error
                _LOGGER.error(
                    "%s now reports the id %s instead of %s",
                    self.entry.title,
                    self.info.device_id,
                    self.entry.unique_id,
                )
                self.hass.config_entries.async_schedule_reload(self.entry.entry_id)
                return
            _LOGGER.info("%s is available again", self.entry.title)
            self._async_refresh_device_registry()
        else:
            _LOGGER.warning("%s is unavailable", self.entry.title)
        for cb in list(self._listeners.availability):
            _safe_call(cb)

    @callback
    def _async_refresh_device_registry(self) -> None:
        if self.device_entry_id is None:
            return
        registry = dr.async_get(self.hass)
        registry.async_update_device(self.device_entry_id, sw_version=self.info.fw_version)

    # ---------------------------------------------------------------- actions

    async def async_get_schema(self) -> list[SettingDef] | None:
        """The display's settings schema (cached), or None if it cannot be fetched.

        None makes the schema helpers fall back to the built-in legacy schema plus the
        always-secret and always-per-device keys.
        """
        if self._schema is None:
            try:
                self._schema = await self.client.get_settings_schema()
            except ShellyElevateIntegrationError as err:
                _LOGGER.debug("Could not fetch the settings schema of %s: %s", self.entry.title, err)
        return self._schema

    async def async_known_keys(self) -> set[str]:
        """Setting keys the display accepts: the cached settings narrowed to its schema on v1."""
        keys = set(self.settings)
        if not self.legacy and (schema := await self.async_get_schema()):
            keys &= {item.key for item in schema}
        return keys

    async def async_command(self, action: str, /, **params: Any) -> dict[str, Any]:
        """Run a command and translate API errors."""
        try:
            return await self.client.command(action, **params)
        except ShellyElevateIntegrationError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"action": action, "error": str(err)},
            ) from err

    async def async_refresh_settings(self) -> None:
        """Re-read the settings from the display; errors become HomeAssistantError."""
        try:
            await self.client.get_settings()
        except ShellyElevateIntegrationError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="settings_read_failed",
                translation_placeholders={"error": str(err)},
            ) from err

    async def async_set_settings(self, changes: dict[str, Any]) -> dict[str, Any]:
        """Write settings and translate API errors."""
        try:
            result = await self.client.set_settings(changes)
        except ShellyElevateIntegrationError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="settings_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        self._on_message({"type": "settings_changed", "changes": changes})
        return result


def _safe_call(cb: Callable[..., None], *args: Any) -> None:
    """Call a listener; one failing entity must not keep the others from updating."""
    try:
        cb(*args)
    except Exception:
        _LOGGER.exception("Error in Shelly Elevate listener %s", cb)
