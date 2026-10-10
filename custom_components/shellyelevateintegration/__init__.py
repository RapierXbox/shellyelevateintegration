"""The Shelly Elevate integration: one device per Shelly Wall Display running ShellyElevate."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import SOURCE_SYSTEM
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError, ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_registry as er
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
from .const import (
    CONF_DEVICE_ID,
    CONF_FEATURES_AUTO_ENABLED,
    CONF_FEATURES_AUTO_HANDLED,
    CONF_FINGERPRINT,
    CONF_LEGACY,
    CONF_TOKEN,
    DOMAIN,
    is_panel_entry,
)
from .device import ShellyElevateIntegrationConfigEntry, ShellyElevateIntegrationDevice
from .features import FeatureWatcher
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
    if not any(is_panel_entry(entry) for entry in hass.config_entries.async_entries(DOMAIN)):
        # The panel only exists while the integration has an entry: give it its own, so it stays
        # when the last display is removed (or reverted to stock).
        hass.async_create_task(hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_SYSTEM}, data={}))
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
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="setup_failed",
            translation_placeholders={"host": entry.data[CONF_HOST], "error": str(err)},
        ) from err

    if not client.legacy and client.info is not None and entry.unique_id and client.info.device_id != entry.unique_id:
        # the app keeps its id for good so a different id is a different display
        await client.disconnect()
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="device_id_mismatch",
            translation_placeholders={
                "host": entry.data[CONF_HOST],
                "actual": client.info.device_id,
                "expected": entry.unique_id,
            },
        )

    device = ShellyElevateIntegrationDevice(hass, entry, client)
    entry.runtime_data = device
    try:
        await device.async_setup()

        from .adb.manager import async_get_adb_manager

        device.adb = await async_get_adb_manager(hass, device)
        if not device.legacy:
            from .permissions import PermissionGuard

            device.permissions = PermissionGuard(device)

        device.backups = BackupManager(device, await async_get_backup_store(hass))
        device.backups.async_start()
        entry.async_on_unload(device.backups.async_stop)

        # Voice needs the Assist pipeline stack; without it the display still works.
        device.voice_enabled = device.info.capabilities.voice and await async_setup_component(
            hass, "assist_satellite", {}
        )
        # the entities depend on the visibility rules of the schema
        await device.async_get_schema()
        # only a display added with this version is still pending (see async_migrate_entry)
        auto_enabled: set[str] = set()
        if not device.legacy and entry.data.get(CONF_FEATURES_AUTO_ENABLED) is False:
            auto_enabled = await _async_auto_enable_features(hass, device)

        bluetooth_setup = None
        if device.info.capabilities.bluetooth and not device.legacy:
            # bluetooth is a dependency so it is loaded here
            from .bluetooth import async_setup_bluetooth

            bluetooth_setup = async_setup_bluetooth

        # entities only exist while their feature is on: a change reloads the entry
        watcher = FeatureWatcher(hass, device, _platforms(device), bluetooth_setup)
        entry.async_on_unload(watcher.async_stop)
        await watcher.async_start()
        await hass.config_entries.async_forward_entry_setups(entry, _platforms(device))
        watcher.async_setup_done()
        if auto_enabled:
            _async_enable_feature_switches(hass, device, auto_enabled)
    except Exception:
        await device.async_shutdown()
        raise

    async_check_issues(hass, device)
    if not device.legacy:
        from .ha_login import DisplayLogin, async_get_ha_login_manager

        device.ha_login = DisplayLogin(device, await async_get_ha_login_manager(hass))
        device.ha_login.async_start()
        entry.async_on_unload(device.ha_login.async_stop)
    if device.permissions is not None:
        device.permissions.async_start()
        entry.async_on_unload(device.permissions.async_stop)

    @callback
    def _recheck(message: dict[str, Any]) -> None:
        if message.get("type") == "settings_changed":
            async_check_issues(hass, device)

    entry.async_on_unload(device.async_add_message_listener(_recheck))
    return True


FEATURE_SWITCHES = {
    "mediaEnabled": "media_enabled",
    "bleScannerEnabled": "bluetooth_proxy",
    "haVoiceEnabled": "voice_assistant",
}
"""Settings turned on once on a newly added display -> unique id suffix of their switch."""


async def _async_auto_enable_features(hass: HomeAssistant, device: ShellyElevateIntegrationDevice) -> set[str]:
    """Turn on media, the Bluetooth proxy and voice once on a newly added display.

    They are off on the display by default but only work through this integration. Each one is
    handled once per entry so a feature the user turns off later stays off: a key that an older app
    does not know yet stays pending until the app has it. A key a profile or the installer set when
    the display was added is handled already, and only a key still at the app default is changed.
    Returns the keys turned on now.
    """
    entry = device.entry
    caps = device.info.capabilities
    wanted = {
        "mediaEnabled": caps.speaker,
        "bleScannerEnabled": caps.bluetooth,
        "haVoiceEnabled": device.voice_enabled,
    }
    handled = set(entry.data.get(CONF_FEATURES_AUTO_HANDLED) or ())
    known = await device.async_known_keys()
    evaluator = device.visibility()
    changes: dict[str, bool] = {}
    for key, want in wanted.items():
        if key in handled or (want and key not in known):
            continue
        definition = evaluator.definition(key)
        default = False if definition is None else definition.default
        if want and device.settings.get(key) is False and default is False:
            changes[key] = True
        else:
            # nothing to do on this display or already on or not at the default
            handled.add(key)
    turned_on: set[str] = set()
    if changes:
        try:
            result = await device.async_set_settings(changes)
        except HomeAssistantError as err:
            # tried again on the next setup
            _LOGGER.warning("Could not turn on %s on %s: %s", ", ".join(changes), entry.title, err)
        else:
            turned_on = set(result.applied)
            handled |= turned_on
            _LOGGER.info("Turned on %s on %s", ", ".join(sorted(turned_on)) or "nothing", entry.title)
    done = handled >= set(wanted)
    data = {**entry.data, CONF_FEATURES_AUTO_ENABLED: done, CONF_FEATURES_AUTO_HANDLED: sorted(handled)}
    if done:
        data.pop(CONF_FEATURES_AUTO_HANDLED)
    hass.config_entries.async_update_entry(entry, data=data)
    return turned_on


@callback
def _async_enable_feature_switches(hass: HomeAssistant, device: ShellyElevateIntegrationDevice, keys: set[str]) -> None:
    """Enable the switches of the features just turned on if the integration created them disabled.

    The switches are enabled by default, so this only finds one that Home Assistant restored from a
    removed entry of the same display that an older version created disabled. Enabling it makes Home
    Assistant reload the entry 30 seconds later (EntityRegistryDisabledHandler), once.
    """
    registry = er.async_get(hass)
    for key in keys:
        entity_id = registry.async_get_entity_id(Platform.SWITCH, DOMAIN, f"{device.device_id}_{FEATURE_SWITCHES[key]}")
        if (
            entity_id is not None
            and (reg_entry := registry.async_get(entity_id)) is not None
            and reg_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        ):
            registry.async_update_entity(entity_id, disabled_by=None)


async def async_migrate_entry(hass: HomeAssistant, entry: ShellyElevateIntegrationConfigEntry) -> bool:
    """Migrate an entry to the current version."""
    if entry.version > 1:
        # a newer version of the integration made it
        return False
    if entry.minor_version < 2:
        data = dict(entry.data)
        if not is_panel_entry(entry):
            # displays added before 1.2 are not new: never turn on their features (the microphone)
            data.setdefault(CONF_FEATURES_AUTO_ENABLED, True)
        hass.config_entries.async_update_entry(entry, data=data, minor_version=2)
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
    """Revoke our token on the display and its dashboard login when the entry is deleted (best effort)."""
    from .ha_login import async_remove_token

    async_remove_token(hass, entry)
    if entry.data.get(CONF_LEGACY) or not entry.data.get(CONF_TOKEN):
        return
    client = _create_client(hass, entry)
    assert isinstance(client, ShellyElevateIntegrationClient)
    try:
        await client.revoke()
    except ShellyElevateIntegrationError as err:
        _LOGGER.debug("Could not revoke token on %s: %s", entry.data[CONF_HOST], err)
