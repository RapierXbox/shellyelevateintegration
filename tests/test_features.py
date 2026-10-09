"""Entities follow the features switched on on the display (features.py)."""

from __future__ import annotations

from collections.abc import Generator
from datetime import timedelta
from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.shellyelevateintegration.api import ShellyElevateIntegrationCommandError
from custom_components.shellyelevateintegration.const import DOMAIN
from custom_components.shellyelevateintegration.features import (
    FEATURE_KEYS,
    FeatureWatcher,
    expected_entities,
)

from .common import PACKAGE, FakeDisplay
from .conftest import setup_entry
from .const import DEVICE_ID

WATCHERS: list[FeatureWatcher] = []


@pytest.fixture(autouse=True)
def record_watchers() -> Generator[list[FeatureWatcher]]:
    """Keep the watcher of each setup."""
    WATCHERS.clear()

    class Recorded(FeatureWatcher):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            WATCHERS.append(self)

    with patch(f"{PACKAGE}.FeatureWatcher", Recorded):
        yield WATCHERS


async def _after_cooldown(hass: HomeAssistant, seconds: float = 3) -> None:
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=seconds))
    await hass.async_block_till_done()


def _uid(hass: HomeAssistant, domain: str, key: str) -> str | None:
    return er.async_get(hass).async_get_entity_id(domain, DOMAIN, f"{DEVICE_ID}_{key}")


async def test_feature_toggle_reloads(
    hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay
) -> None:
    """Turning media off removes the media player after a reload."""
    assert _uid(hass, "media_player", "media_player")
    clients = len(display.clients)
    display.client.push({"type": "settings_changed", "changes": {"mediaEnabled": False}})
    await hass.async_block_till_done()
    assert len(display.clients) == clients  # collected for the cooldown first
    await _after_cooldown(hass)
    assert len(display.clients) == clients + 1
    assert init_integration.state is ConfigEntryState.LOADED
    assert _uid(hass, "media_player", "media_player") is None


@pytest.mark.parametrize(
    "changes",
    [
        {"automaticBrightness": False, "brightness": 100},
        {"screenSaver": False},
        {"voiceWakeEnabled": False, "voiceWakeModelName": "hey_jarvis"},
        {"publishSwipeEvents": False},
        {"buttonRelayEnabled": True},
    ],
)
async def test_side_effects_do_not_reload(
    hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay, changes: dict
) -> None:
    """Settings outside FEATURE_KEYS only make entities unavailable."""
    assert not FEATURE_KEYS & set(changes)
    clients = len(display.clients)
    display.client.push({"type": "settings_changed", "changes": changes})
    await _after_cooldown(hass)
    assert len(display.clients) == clients


async def test_capability_change_reloads(
    hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay
) -> None:
    """A changed capability (a dimmer attached) reloads."""
    clients = len(display.clients)
    display.client.info.capabilities.dimmer = True
    display.client.push({"type": "_info_changed"})
    await _after_cooldown(hass)
    assert len(display.clients) == clients + 1


async def test_info_changed_without_effect(
    hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay
) -> None:
    """A new app version alone changes nothing."""
    clients = len(display.clients)
    display.client.info.fw_version = "3.26160.0900"
    display.client.push({"type": "_info_changed"})
    await _after_cooldown(hass)
    assert len(display.clients) == clients
    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, DEVICE_ID), init_integration.entry_id)
    assert device.sw_version == "3.26160.0900"


async def test_check_waits_for_display(
    hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay
) -> None:
    """A check while the display is away runs again when it is back."""
    clients = len(display.clients)
    display.client.push({"type": "settings_changed", "changes": {"mediaEnabled": False}})
    display.client.set_available(False)
    await _after_cooldown(hass)
    assert len(display.clients) == clients
    display.client.set_available(True)
    await _after_cooldown(hass)
    assert len(display.clients) == clients + 1


async def test_check_waits_for_schema(
    hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry
) -> None:
    """Without the schema of the display nothing is decided; stale entities are kept until it is read."""
    mock_config_entry.add_to_hass(hass)
    registry = er.async_get(hass)
    obsolete = registry.async_get_or_create("switch", DOMAIN, f"{DEVICE_ID}_obsolete", config_entry=mock_config_entry)
    display.schema_error = ShellyElevateIntegrationCommandError("timeout")
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert registry.async_get(obsolete.entity_id) is not None  # fallback rules only

    display.client.push({"type": "settings_changed", "changes": {"touchToWake": False}})
    await _after_cooldown(hass)
    assert registry.async_get(obsolete.entity_id) is not None  # still no schema

    display.schema_error = None
    display.client.push({"type": "settings_changed", "changes": {"touchToWake": True}})
    await _after_cooldown(hass)
    await _after_cooldown(hass)
    assert registry.async_get(obsolete.entity_id) is None
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_stale_entities_and_devices_removed(
    hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry
) -> None:
    """Entities of features that are off and devices of an earlier pairing are removed after setup."""
    mock_config_entry.add_to_hass(hass)
    registry = er.async_get(hass)
    devices = dr.async_get(hass)
    old_device = devices.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id, identifiers={(DOMAIN, "old-pairing")}
    )
    old_entity = registry.async_get_or_create("sensor", DOMAIN, f"{DEVICE_ID}_gone", config_entry=mock_config_entry)
    kept_device = devices.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id, identifiers={(DOMAIN, "with-entity")}
    )
    other_entry = MockConfigEntry(domain="other")
    other_entry.add_to_hass(hass)
    registry.async_get_or_create("sensor", "other", "kept", config_entry=other_entry, device_id=kept_device.id)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert registry.async_get(old_entity.entity_id) is None
    assert devices.async_get(old_device.id) is None
    assert devices.async_get(kept_device.id) is not None


async def test_setting_changed_during_setup(
    hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry
) -> None:
    """A change while the platforms were set up is checked again afterwards."""
    original = FeatureWatcher.async_setup_done

    def setup_done(self: FeatureWatcher) -> None:
        # reported before the watcher is ready: compared once setup is done
        display.client.push({"type": "settings_changed", "changes": {"mediaEnabled": False}})
        display.client.settings["mediaEnabled"] = False
        original(self)

    clients_before = 0
    with patch.object(FeatureWatcher, "async_setup_done", setup_done):
        await setup_entry(hass, mock_config_entry)
        clients_before = len(display.clients)
    await _after_cooldown(hass)
    assert len(display.clients) == clients_before + 1


async def test_check_skipped_while_not_loaded(
    hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay
) -> None:
    """A check during a reload is postponed; a scheduled reload is not scheduled twice."""
    watcher = WATCHERS[-1]
    async with init_integration.setup_lock:
        await watcher._async_check()
    assert watcher._dirty
    watcher._reload_scheduled = True
    await watcher._async_check()
    await _after_cooldown(hass)
    watcher._reload_scheduled = False
    assert await hass.config_entries.async_unload(init_integration.entry_id)
    watcher._dirty = False
    await watcher._async_check()
    assert watcher._dirty


async def test_platform_modules_missing(
    hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry
) -> None:
    """Without the platform modules nothing is compared or removed."""
    with patch(f"{PACKAGE}.features.expected_entities", return_value=None):
        await setup_entry(hass, mock_config_entry)
        display.client.push({"type": "settings_changed", "changes": {"mediaEnabled": False}})
        clients = len(display.clients)
        await _after_cooldown(hass)
        assert len(display.clients) == clients


async def test_expected_entities_needs_platform_modules(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    """Without a loaded platform module the expected entities are unknown."""
    device = init_integration.runtime_data
    with patch.dict("sys.modules", {f"{PACKAGE}.sensor": None}):
        assert expected_entities(device, [Platform.SENSOR]) is None
    assert expected_entities(device, [Platform.NOTIFY]) == {("notify", f"{DEVICE_ID}_notify")}


async def test_bluetooth_setup_error(
    hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry
) -> None:
    """A display that cannot become a scanner keeps working."""
    with patch(
        "custom_components.shellyelevateintegration.bluetooth.async_setup_bluetooth", side_effect=RuntimeError("bad")
    ):
        await setup_entry(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert WATCHERS[-1]._bluetooth_unload is None
