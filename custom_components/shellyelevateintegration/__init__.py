"""The Shelly Elevate integration: one device per Shelly Wall Display running ShellyElevate."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

from .api import (
    DEFAULT_PORT,
    LEGACY_PORT,
    LegacyClient,
    ShellyElevateIntegrationApi,
    ShellyElevateIntegrationAuthError,
    ShellyElevateIntegrationClient,
    ShellyElevateIntegrationConnectionError,
    ShellyElevateIntegrationError,
    ShellyElevateIntegrationIncompatibleError,
)
from .const import CONF_DEVICE_ID, CONF_FINGERPRINT, CONF_LEGACY, CONF_TOKEN, DOMAIN, is_panel_entry
from .device import ShellyElevateIntegrationConfigEntry, ShellyElevateIntegrationDevice
from .repairs import async_check_issues
from .services import async_setup_services
from .settings.backups import BackupManager, async_get_backup_store

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.EVENT,
    Platform.IMAGE,
    Platform.LIGHT,
    Platform.MEDIA_PLAYER,
    Platform.NOTIFY,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TEXT,
    Platform.UPDATE,
]
VOICE_PLATFORMS: list[Platform] = [Platform.ASSIST_SATELLITE]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up services, the websocket API and the sidebar panel."""
    async_setup_services(hass)
    from .websocket import async_setup_websocket

    async_setup_websocket(hass)
    from .panel import async_setup_panel

    await async_setup_panel(hass)
    return True


def _create_client(hass: HomeAssistant, entry: ShellyElevateIntegrationConfigEntry) -> ShellyElevateIntegrationApi:
    session = async_get_clientsession(hass)
    host = entry.data[CONF_HOST]
    if entry.data.get(CONF_LEGACY):
        return LegacyClient(session, host, entry.data.get(CONF_PORT, LEGACY_PORT), entry.data.get(CONF_DEVICE_ID))
    return ShellyElevateIntegrationClient(
        session,
        host,
        entry.data.get(CONF_PORT, DEFAULT_PORT),
        entry.data.get(CONF_TOKEN) or "",
        entry.data.get(CONF_FINGERPRINT),
        entry.unique_id,
    )


def _platforms(device: ShellyElevateIntegrationDevice) -> list[Platform]:
    return PLATFORMS + VOICE_PLATFORMS if device.voice_enabled else list(PLATFORMS)


async def async_setup_entry(hass: HomeAssistant, entry: ShellyElevateIntegrationConfigEntry) -> bool:
    """Set up one display (the panel-only entry has nothing to set up: async_setup added the panel)."""
    if is_panel_entry(entry):
        return True
    client = _create_client(hass, entry)
    try:
        await client.connect()
    except ShellyElevateIntegrationAuthError as err:
        raise ConfigEntryAuthFailed(translation_domain=DOMAIN, translation_key="auth_failed") from err
    except ShellyElevateIntegrationIncompatibleError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN, translation_key="incompatible_api", translation_placeholders={"error": str(err)}
        ) from err
    except ShellyElevateIntegrationConnectionError as err:
        await client.disconnect()
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"host": entry.data[CONF_HOST]},
        ) from err
    except ShellyElevateIntegrationError as err:
        await client.disconnect()
        raise ConfigEntryNotReady(str(err)) from err

    device = ShellyElevateIntegrationDevice(hass, entry, client)
    entry.runtime_data = device
    try:
        await device.async_setup()

        from .adb.manager import async_get_adb_manager

        device.adb = await async_get_adb_manager(hass, device)

        device.backups = BackupManager(device, await async_get_backup_store(hass))
        device.backups.async_start()
        entry.async_on_unload(device.backups.async_stop)

        # Voice needs the Assist pipeline stack; without it the display still works.
        device.voice_enabled = device.info.capabilities.voice and await async_setup_component(
            hass, "assist_satellite", {}
        )
        await hass.config_entries.async_forward_entry_setups(entry, _platforms(device))

        if device.info.capabilities.bluetooth and not device.legacy and "bluetooth" in hass.config.components:
            from .bluetooth import async_setup_bluetooth

            entry.async_on_unload(await async_setup_bluetooth(hass, device))
    except Exception:
        await device.async_shutdown()
        raise

    async_check_issues(hass, device)

    @callback
    def _recheck(message: dict[str, Any]) -> None:
        if message.get("type") == "settings_changed":
            async_check_issues(hass, device)

    entry.async_on_unload(device.async_add_message_listener(_recheck))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ShellyElevateIntegrationConfigEntry) -> bool:
    """Unload a display."""
    if is_panel_entry(entry):
        return True
    device = entry.runtime_data
    unloaded = await hass.config_entries.async_unload_platforms(entry, _platforms(device))
    if unloaded:
        await device.async_shutdown()
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: ShellyElevateIntegrationConfigEntry) -> None:
    """Revoke our token on the display when the entry is deleted (best effort)."""
    if entry.data.get(CONF_LEGACY) or not entry.data.get(CONF_TOKEN):
        return
    client = _create_client(hass, entry)
    assert isinstance(client, ShellyElevateIntegrationClient)
    try:
        await client.revoke()
    except ShellyElevateIntegrationError as err:
        _LOGGER.debug("Could not revoke token on %s: %s", entry.data[CONF_HOST], err)
