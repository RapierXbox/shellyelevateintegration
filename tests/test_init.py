"""Setup, unload, migration and removal of a display."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.shellyelevateintegration import async_migrate_entry
from custom_components.shellyelevateintegration.api import (
    ShellyElevateIntegrationAuthError,
    ShellyElevateIntegrationCommandError,
    ShellyElevateIntegrationConnectionError,
    ShellyElevateIntegrationIncompatibleError,
)
from custom_components.shellyelevateintegration.const import (
    CONF_FEATURES_AUTO_ENABLED,
    CONF_FEATURES_AUTO_HANDLED,
    CONF_PANEL,
    DOMAIN,
)

from .common import PACKAGE, FakeDisplay
from .conftest import entry_data, setup_entry
from .const import DEVICE_ID, MAC, OTHER_DEVICE_ID, TITLE, TOKEN

AUTO = ("mediaEnabled", "bleScannerEnabled", "haVoiceEnabled")


def _reauth_flows(hass: HomeAssistant) -> list[dict[str, Any]]:
    return [
        flow
        for flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN)
        if flow["context"]["source"] == SOURCE_REAUTH
    ]


async def test_setup_entry(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    display: FakeDisplay,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """A display becomes one device with its entities."""
    device = device_registry.async_get_device_by_identifier((DOMAIN, DEVICE_ID), init_integration.entry_id)
    assert device is not None
    assert device.name == TITLE
    assert device.manufacturer == "Shelly"
    assert device.model == "Wall Display X2"
    assert device.model_id == "SAWD-2A1XX10EU1"
    assert device.sw_version == "3.26150.1200"
    assert device.hw_version == "Android 8.1.0"
    assert device.configuration_url == "https://192.168.1.50:8443"
    assert (dr.CONNECTION_NETWORK_MAC, MAC.lower()) in device.connections
    entities = er.async_entries_for_config_entry(entity_registry, init_integration.entry_id)
    assert {entity.domain for entity in entities} == {
        "assist_satellite",
        "binary_sensor",
        "button",
        "event",
        "image",
        "light",
        "media_player",
        "notify",
        "number",
        "select",
        "sensor",
        "switch",
        "text",
        "update",
    }
    assert all(entity.device_id == device.id for entity in entities)
    # relay 2 needs the optional power base
    relay_2 = entity_registry.async_get_entity_id("switch", DOMAIN, f"{DEVICE_ID}_relay_1")
    assert entity_registry.async_get(relay_2).disabled_by is er.RegistryEntryDisabler.INTEGRATION
    runtime = init_integration.runtime_data
    assert runtime.available
    assert runtime.voice_enabled
    assert runtime.adb is None
    assert runtime.permissions is not None
    assert display.client.token == TOKEN


async def test_component_adds_panel_entry_once(hass: HomeAssistant) -> None:
    """The panel lives in its own entry so it stays when the last display goes."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    entries = hass.config_entries.async_entries(DOMAIN)
    assert [entry.data for entry in entries] == [{CONF_PANEL: True}]
    assert entries[0].state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(entries[0].entry_id)
    assert entries[0].state is ConfigEntryState.NOT_LOADED


async def test_panel_entry_existing(hass: HomeAssistant, panel_entry: MockConfigEntry) -> None:
    """No second panel entry is created when one exists."""
    await setup_entry(hass, panel_entry)
    assert panel_entry.state is ConfigEntryState.LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.parametrize(
    ("error", "state"),
    [
        (ShellyElevateIntegrationConnectionError("timeout"), ConfigEntryState.SETUP_RETRY),
        (ShellyElevateIntegrationCommandError("invalid_response", "bad info"), ConfigEntryState.SETUP_RETRY),
        (ShellyElevateIntegrationIncompatibleError("API 2.0"), ConfigEntryState.SETUP_ERROR),
        (ShellyElevateIntegrationAuthError("Token rejected"), ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_setup_errors(
    hass: HomeAssistant,
    display: FakeDisplay,
    mock_config_entry: MockConfigEntry,
    error: Exception,
    state: ConfigEntryState,
) -> None:
    """Unreachable displays are retried, rejected tokens start reauth, other protocols fail."""
    display.connect_error = error
    await setup_entry(hass, mock_config_entry)
    assert mock_config_entry.state is state
    assert bool(_reauth_flows(hass)) is isinstance(error, ShellyElevateIntegrationAuthError)


async def test_setup_device_id_mismatch(
    hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry
) -> None:
    """Another display at the address is not taken for this one."""
    display.info["id"] = OTHER_DEVICE_ID
    await setup_entry(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert not display.client.connected


async def test_setup_failure_disconnects(
    hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry
) -> None:
    """An unexpected error during setup does not leave the client connected."""
    with patch(f"{PACKAGE}.BackupManager.async_start", side_effect=RuntimeError("boom")):
        await setup_entry(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert not display.client.connected


async def test_setup_without_voice_stack(
    hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry, entity_registry: er.EntityRegistry
) -> None:
    """Without the Assist pipeline stack the display still works, only without voice."""
    with patch(f"{PACKAGE}.async_setup_component", return_value=False):
        await setup_entry(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not mock_config_entry.runtime_data.voice_enabled
    entities = er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
    assert "assist_satellite" not in {entity.domain for entity in entities}


async def test_legacy_upgrade_starts_reauth(
    hass: HomeAssistant, legacy_display: FakeDisplay, legacy_config_entry: MockConfigEntry
) -> None:
    """A legacy display that also answers protocol v1 asks to be paired."""
    legacy_display.upgrade_available = True
    legacy_display.mocks["probe"].side_effect = None
    legacy_display.mocks["probe"].return_value = FakeDisplay().hello(device_id=legacy_config_entry.unique_id)
    await setup_entry(hass, legacy_config_entry)
    assert legacy_config_entry.state is ConfigEntryState.LOADED
    assert _reauth_flows(hass)


async def test_unload_entry(hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay) -> None:
    """Unloading disconnects the display."""
    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()
    assert init_integration.state is ConfigEntryState.NOT_LOADED
    assert not display.client.connected
    assert hass.states.get("switch.shelly_wall_display_x2_relay_1").state == "unavailable"


async def test_unload_legacy(hass: HomeAssistant, init_legacy: MockConfigEntry, legacy_display: FakeDisplay) -> None:
    """A legacy display unloads too."""
    assert await hass.config_entries.async_unload(init_legacy.entry_id)
    assert not legacy_display.client.connected


async def test_remove_entry_revokes_token(
    hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay
) -> None:
    """Deleting the entry revokes its token on the display."""
    await hass.config_entries.async_remove(init_integration.entry_id)
    await hass.async_block_till_done()
    assert display.client.revoked
    assert display.client.token == TOKEN


async def test_remove_entry_display_unreachable(
    hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay
) -> None:
    """The entry is deleted even when the display cannot be told."""
    display.revoke_error = ShellyElevateIntegrationConnectionError("timeout")
    await hass.config_entries.async_remove(init_integration.entry_id)
    await hass.async_block_till_done()
    assert hass.config_entries.async_get_entry(init_integration.entry_id) is None


async def test_remove_legacy_entry(
    hass: HomeAssistant, init_legacy: MockConfigEntry, legacy_display: FakeDisplay
) -> None:
    """The legacy app has no token to revoke."""
    clients = len(legacy_display.clients)
    await hass.config_entries.async_remove(init_legacy.entry_id)
    assert len(legacy_display.clients) == clients


# --------------------------------------------------------------------------- migration


async def test_migrate_display_from_1_1(hass: HomeAssistant, display: FakeDisplay) -> None:
    """Displays added before 1.2 never get features turned on (the microphone)."""
    data = entry_data()
    del data[CONF_FEATURES_AUTO_ENABLED]
    entry = MockConfigEntry(domain=DOMAIN, version=1, minor_version=1, unique_id=DEVICE_ID, data=data, title=TITLE)
    display.settings["mediaEnabled"] = False
    await setup_entry(hass, entry)
    assert entry.state is ConfigEntryState.LOADED
    assert entry.minor_version == 2
    assert entry.data[CONF_FEATURES_AUTO_ENABLED] is True
    assert display.writes == []


async def test_migrate_panel_from_1_1(hass: HomeAssistant) -> None:
    """The panel entry only gets the new minor version."""
    entry = MockConfigEntry(domain=DOMAIN, version=1, minor_version=1, unique_id="_panel", data={CONF_PANEL: True})
    await setup_entry(hass, entry)
    assert entry.minor_version == 2
    assert entry.data == {CONF_PANEL: True}


async def test_migrate_from_future_version(hass: HomeAssistant, display: FakeDisplay) -> None:
    """An entry of a newer integration version is not touched."""
    entry = MockConfigEntry(domain=DOMAIN, version=2, minor_version=1, unique_id=DEVICE_ID, data=entry_data())
    await setup_entry(hass, entry)
    assert entry.state is ConfigEntryState.MIGRATION_ERROR
    assert await async_migrate_entry(hass, entry) is False
    assert entry.version == 2


# --------------------------------------------------------------------------- features turned on once


def _new_display_entry(**changes: Any) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=2,
        unique_id=DEVICE_ID,
        title=TITLE,
        data=entry_data(**{CONF_FEATURES_AUTO_ENABLED: False, **changes}),
    )


async def test_auto_enable_on_new_display(hass: HomeAssistant, display: FakeDisplay) -> None:
    """Media, the Bluetooth proxy and voice are turned on once on a new display."""
    for key in AUTO:
        display.settings[key] = False
    entry = await setup_entry(hass, _new_display_entry())
    assert entry.state is ConfigEntryState.LOADED
    assert display.writes == [dict.fromkeys(AUTO, True)]
    assert entry.data[CONF_FEATURES_AUTO_ENABLED] is True
    assert CONF_FEATURES_AUTO_HANDLED not in entry.data


async def test_auto_enable_only_once(hass: HomeAssistant, display: FakeDisplay) -> None:
    """A feature turned off later stays off."""
    for key in AUTO:
        display.settings[key] = False
    await setup_entry(hass, _new_display_entry(**{CONF_FEATURES_AUTO_ENABLED: True}))
    assert display.writes == []


async def test_auto_enable_already_on(hass: HomeAssistant, display: FakeDisplay) -> None:
    """Features that are on already are just marked as handled."""
    entry = await setup_entry(hass, _new_display_entry())
    assert display.writes == []
    assert entry.data[CONF_FEATURES_AUTO_ENABLED] is True


async def test_auto_enable_respects_profile(hass: HomeAssistant, display: FakeDisplay) -> None:
    """A feature the profile set when the display was added is not turned on."""
    for key in AUTO:
        display.settings[key] = False
    entry = await setup_entry(hass, _new_display_entry(**{CONF_FEATURES_AUTO_HANDLED: ["mediaEnabled"]}))
    assert display.writes == [{"bleScannerEnabled": True, "haVoiceEnabled": True}]
    assert entry.data[CONF_FEATURES_AUTO_ENABLED] is True


async def test_auto_enable_not_at_default(hass: HomeAssistant, display: FakeDisplay) -> None:
    """A setting whose app default is on was turned off on purpose: it stays off."""
    display.settings["mediaEnabled"] = False
    next(item for item in display.schema if item["key"] == "mediaEnabled")["default"] = True
    entry = await setup_entry(hass, _new_display_entry())
    assert display.writes == []
    assert entry.data[CONF_FEATURES_AUTO_ENABLED] is True


async def test_auto_enable_waits_for_app(hass: HomeAssistant, display: FakeDisplay) -> None:
    """A key an older app does not know yet stays pending until the app has it."""
    display.settings["mediaEnabled"] = False
    del display.settings["haVoiceEnabled"]
    display.schema = [item for item in display.schema if item["key"] != "haVoiceEnabled"]
    entry = await setup_entry(hass, _new_display_entry())
    assert display.writes == [{"mediaEnabled": True}]
    assert entry.data[CONF_FEATURES_AUTO_ENABLED] is False
    assert entry.data[CONF_FEATURES_AUTO_HANDLED] == ["bleScannerEnabled", "mediaEnabled"]


async def test_auto_enable_write_fails(hass: HomeAssistant, display: FakeDisplay) -> None:
    """A failed write is tried again on the next setup."""
    display.settings["mediaEnabled"] = False
    display.set_settings_error = ShellyElevateIntegrationConnectionError("reset")
    entry = await setup_entry(hass, _new_display_entry())
    assert entry.state is ConfigEntryState.LOADED
    assert entry.data[CONF_FEATURES_AUTO_ENABLED] is False
    assert "mediaEnabled" not in entry.data[CONF_FEATURES_AUTO_HANDLED]


async def test_auto_enable_reenables_restored_switch(
    hass: HomeAssistant, display: FakeDisplay, entity_registry: er.EntityRegistry
) -> None:
    """A switch an older version created disabled is enabled with its feature."""
    display.settings["mediaEnabled"] = False
    entry = _new_display_entry()
    entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        "switch",
        DOMAIN,
        f"{DEVICE_ID}_media_enabled",
        config_entry=entry,
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    entity_id = entity_registry.async_get_entity_id("switch", DOMAIN, f"{DEVICE_ID}_media_enabled")
    assert entity_registry.async_get(entity_id).disabled_by is None


async def test_auto_enable_skips_legacy(
    hass: HomeAssistant, legacy_display: FakeDisplay, legacy_config_entry: MockConfigEntry
) -> None:
    """The legacy app has none of these features."""
    legacy_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        legacy_config_entry, data={**legacy_config_entry.data, CONF_FEATURES_AUTO_ENABLED: False}
    )
    await hass.config_entries.async_setup(legacy_config_entry.entry_id)
    await hass.async_block_till_done()
    assert legacy_display.writes == []
    assert legacy_config_entry.data[CONF_FEATURES_AUTO_ENABLED] is False
