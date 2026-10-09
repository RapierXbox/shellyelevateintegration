"""Switches: relays, night mode and boolean settings."""

from __future__ import annotations

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.shellyelevateintegration.api import ShellyElevateIntegrationCommandError
from custom_components.shellyelevateintegration.const import OPT_RELAYS_AS_LIGHTS

from .common import FakeDisplay, entity_id
from .conftest import setup_entry
from .const import LEGACY_DEVICE_ID

pytestmark = pytest.mark.usefixtures("entity_registry_enabled_by_default")


async def _call(hass: HomeAssistant, service: str, target: str) -> None:
    await hass.services.async_call(SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: target}, blocking=True)


async def test_relays(hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay) -> None:
    """Relays follow the display and switch it."""
    relay_1 = entity_id(hass, SWITCH_DOMAIN, "relay_0")
    relay_2 = entity_id(hass, SWITCH_DOMAIN, "relay_1")
    assert hass.states.get(relay_1).state == STATE_OFF
    assert hass.states.get(relay_2).state == STATE_ON
    assert hass.states.get(relay_1).attributes["device_class"] == "outlet"

    await _call(hass, SERVICE_TURN_ON, relay_1)
    await _call(hass, SERVICE_TURN_OFF, relay_2)
    assert display.commands == [("relay.set", {"index": 0, "on": True}), ("relay.set", {"index": 1, "on": False})]

    display.client.push_state({"relay.0": True})
    await hass.async_block_till_done()
    assert hass.states.get(relay_1).state == STATE_ON


async def test_relay_command_error(
    hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay
) -> None:
    """A rejected command is an error of the action."""
    display.command_errors["relay.set"] = ShellyElevateIntegrationCommandError("busy")
    with pytest.raises(HomeAssistantError) as err:
        await _call(hass, SERVICE_TURN_ON, entity_id(hass, SWITCH_DOMAIN, "relay_0"))
    assert err.value.translation_key == "command_failed"


async def test_night_mode(hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay) -> None:
    """Night mode is a command."""
    night = entity_id(hass, SWITCH_DOMAIN, "night_mode")
    assert hass.states.get(night).state == STATE_OFF
    await _call(hass, SERVICE_TURN_ON, night)
    await _call(hass, SERVICE_TURN_OFF, night)
    assert display.commands == [("night_mode.set", {"on": True}), ("night_mode.set", {"on": False})]


async def test_setting_switch(hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay) -> None:
    """A boolean setting is written and read back."""
    saver = entity_id(hass, SWITCH_DOMAIN, "screensaver")
    assert hass.states.get(saver).state == STATE_ON
    await _call(hass, SERVICE_TURN_OFF, saver)
    assert display.writes == [{"screenSaver": False}]
    assert hass.states.get(saver).state == STATE_OFF
    await _call(hass, SERVICE_TURN_ON, saver)
    assert display.writes[-1] == {"screenSaver": True}


async def test_dependent_setting_unavailable(
    hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay
) -> None:
    """Without the screensaver, wake on proximity cannot take effect: unavailable, not removed."""
    wake = entity_id(hass, SWITCH_DOMAIN, "wake_on_proximity")
    assert hass.states.get(wake).state == STATE_ON
    display.client.push({"type": "settings_changed", "changes": {"screenSaver": False}})
    await hass.async_block_till_done()
    assert hass.states.get(wake).state == STATE_UNAVAILABLE
    assert init_integration.state is ConfigEntryState.LOADED


async def test_setting_switch_unknown_value(
    hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry
) -> None:
    """A setting without a value is unknown."""
    display.settings["touchToWake"] = None
    await setup_entry(hass, mock_config_entry)
    assert hass.states.get(entity_id(hass, SWITCH_DOMAIN, "touch_to_wake")).state == "unknown"


async def test_relays_as_lights(hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry) -> None:
    """With the option the relays are lights, not switches."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, options={OPT_RELAYS_AS_LIGHTS: True})
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    assert registry.async_get_entity_id(SWITCH_DOMAIN, "shellyelevateintegration", "shellyelevate-4a2f_relay_0") is None
    light = entity_id(hass, "light", "relay_0")
    assert hass.states.get(light).state == STATE_OFF
    await hass.services.async_call("light", SERVICE_TURN_ON, {ATTR_ENTITY_ID: light}, blocking=True)
    assert display.commands[-1] == ("relay.set", {"index": 0, "on": True})


async def test_legacy_switches(hass: HomeAssistant, init_legacy: MockConfigEntry, legacy_display: FakeDisplay) -> None:
    """Legacy displays report booleans as strings; the legacy HTTP API switch does not exist there."""
    media = entity_id(hass, SWITCH_DOMAIN, "media_enabled", LEGACY_DEVICE_ID)
    assert hass.states.get(media).state == STATE_ON
    registry = er.async_get(hass)
    assert (
        registry.async_get_entity_id(SWITCH_DOMAIN, "shellyelevateintegration", f"{LEGACY_DEVICE_ID}_legacy_http_api")
        is None
    )
    legacy_display.client.push({"type": "settings_changed", "changes": {"mediaEnabled": "off"}})
    await hass.async_block_till_done()
    assert hass.states.get(media).state in (STATE_OFF, STATE_UNAVAILABLE)
