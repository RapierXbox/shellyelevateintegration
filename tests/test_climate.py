"""Thermostat."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.climate import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache,
)

from custom_components.shellyelevateintegration.api import ShellyElevateIntegrationCommandError
from custom_components.shellyelevateintegration.const import (
    OPT_THERMOSTAT,
    OPT_THERMOSTAT_MIN_CYCLE,
    OPT_THERMOSTAT_MODE,
    OPT_THERMOSTAT_RELAY,
    OPT_THERMOSTAT_SENSOR,
    OPT_THERMOSTAT_TOLERANCE,
)

from .common import FakeDisplay, entity_id

SENSOR = "sensor.living_room_temperature"


async def _setup(hass: HomeAssistant, entry: MockConfigEntry, **options: Any) -> str | None:
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        entry, options={OPT_THERMOSTAT: True, OPT_THERMOSTAT_RELAY: "0", OPT_THERMOSTAT_TOLERANCE: 0.3, **options}
    )
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return er.async_get(hass).async_get_entity_id(
        CLIMATE_DOMAIN, "shellyelevateintegration", "shellyelevate-4a2f_thermostat"
    )


async def _call(hass: HomeAssistant, service: str, climate: str, **data: Any) -> None:
    await hass.services.async_call(CLIMATE_DOMAIN, service, {ATTR_ENTITY_ID: climate, **data}, blocking=True)
    await hass.async_block_till_done()


def _relay_commands(display: FakeDisplay) -> list[bool]:
    return [params["on"] for action, params in display.commands if action == "relay.set"]


async def test_heating(hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry) -> None:
    """The relay heats until the target is reached."""
    climate = await _setup(hass, mock_config_entry)
    state = hass.states.get(climate)
    assert state.state == HVACMode.OFF
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 21.4
    assert state.attributes[ATTR_CURRENT_HUMIDITY] == 45.2
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.OFF
    assert state.attributes["temperature_sensor"] == "display"
    assert state.attributes["relay"] == 1

    await _call(hass, "set_temperature", climate, **{ATTR_TEMPERATURE: 23, ATTR_HVAC_MODE: HVACMode.HEAT})
    assert _relay_commands(display) == [True]
    assert hass.states.get(climate).attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE
    display.client.push_state({"relay.0": True})
    await hass.async_block_till_done()
    assert hass.states.get(climate).attributes[ATTR_HVAC_ACTION] == HVACAction.HEATING

    # inside the tolerance nothing happens
    display.client.push_state({"temperature": 23.1})
    await hass.async_block_till_done()
    assert _relay_commands(display) == [True]
    display.client.push_state({"temperature": 23.4})
    await hass.async_block_till_done()
    assert _relay_commands(display) == [True, False]

    await _call(hass, "turn_off", climate)
    assert _relay_commands(display) == [True, False, False]
    assert hass.states.get(climate).state == HVACMode.OFF
    # off means hands off
    display.client.push_state({"temperature": 15.0})
    await hass.async_block_till_done()
    assert len(_relay_commands(display)) == 3

    display.client.push_state({"relay.0": False})
    await hass.async_block_till_done()
    await _call(hass, "turn_on", climate)
    assert hass.states.get(climate).state == HVACMode.HEAT
    assert _relay_commands(display)[-1] is True


async def test_cooling(hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry) -> None:
    """In cool mode the relay runs above the target."""
    climate = await _setup(hass, mock_config_entry, **{OPT_THERMOSTAT_MODE: "cool"})
    assert hass.states.get(climate).attributes["hvac_modes"] == [HVACMode.OFF, HVACMode.COOL]
    await _call(hass, "set_temperature", climate, **{ATTR_TEMPERATURE: 20, ATTR_HVAC_MODE: HVACMode.COOL})
    assert _relay_commands(display) == [True]
    display.client.push_state({"relay.0": True, "temperature": 19.5})
    await hass.async_block_till_done()
    assert _relay_commands(display) == [True, False]
    display.client.push_state({"temperature": 25.0, "relay.0": True})
    await hass.async_block_till_done()
    assert hass.states.get(climate).attributes[ATTR_HVAC_ACTION] == HVACAction.COOLING


async def test_external_sensor(hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry) -> None:
    """Another temperature sensor can be the source, in any unit."""
    hass.states.async_set(SENSOR, "18.0", {ATTR_UNIT_OF_MEASUREMENT: "°C"})
    climate = await _setup(hass, mock_config_entry, **{OPT_THERMOSTAT_SENSOR: SENSOR})
    state = hass.states.get(climate)
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 18.0
    assert state.attributes["temperature_sensor"] == SENSOR

    hass.states.async_set(SENSOR, "77", {ATTR_UNIT_OF_MEASUREMENT: "°F"})
    await hass.async_block_till_done()
    assert hass.states.get(climate).attributes[ATTR_CURRENT_TEMPERATURE] == 25.0
    for value, attributes in (("warm", {ATTR_UNIT_OF_MEASUREMENT: "°C"}), ("20", {}), ("unavailable", {})):
        hass.states.async_set(SENSOR, value, attributes)
        await hass.async_block_till_done()
        assert hass.states.get(climate).attributes[ATTR_CURRENT_TEMPERATURE] is None
    await _call(hass, "set_hvac_mode", climate, **{ATTR_HVAC_MODE: HVACMode.HEAT})
    assert _relay_commands(display) == []
    # the display is away: the sensor still updates but nothing is switched
    display.client.set_available(False)
    hass.states.async_set(SENSOR, "10", {ATTR_UNIT_OF_MEASUREMENT: "°C"})
    await hass.async_block_till_done()
    assert _relay_commands(display) == []


async def test_min_cycle(
    hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """The relay does not switch again before the minimum cycle time."""
    climate = await _setup(hass, mock_config_entry, **{OPT_THERMOSTAT_MIN_CYCLE: 300})
    await _call(hass, "set_temperature", climate, **{ATTR_TEMPERATURE: 23, ATTR_HVAC_MODE: HVACMode.HEAT})
    display.client.push_state({"relay.0": True})
    await hass.async_block_till_done()
    display.client.push_state({"temperature": 24.0})
    await hass.async_block_till_done()
    display.client.push_state({"temperature": 24.5})  # a pending retry is replaced
    await hass.async_block_till_done()
    assert _relay_commands(display) == [True]
    freezer.tick(timedelta(seconds=301))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert _relay_commands(display) == [True, False]


async def test_unavailable_display(
    hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry
) -> None:
    """Nothing is switched while the display is away; a failing switch is only logged."""
    climate = await _setup(hass, mock_config_entry)
    display.command_errors["relay.set"] = ShellyElevateIntegrationCommandError("busy")
    await _call(hass, "set_temperature", climate, **{ATTR_TEMPERATURE: 25, ATTR_HVAC_MODE: HVACMode.HEAT})
    assert _relay_commands(display) == [True]
    display.client.set_available(False)
    await hass.async_block_till_done()
    await _call(hass, "set_temperature", climate, **{ATTR_TEMPERATURE: 26})
    await hass.services.async_call(
        CLIMATE_DOMAIN, "set_hvac_mode", {ATTR_ENTITY_ID: climate, ATTR_HVAC_MODE: HVACMode.OFF}, blocking=False
    )
    await hass.async_block_till_done()
    assert _relay_commands(display) == [True]


async def test_restore(hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry) -> None:
    """Mode and target survive a restart."""
    mock_restore_cache(
        hass, [State("climate.shelly_wall_display_x2_thermostat", HVACMode.HEAT, {ATTR_TEMPERATURE: 19.5})]
    )
    climate = await _setup(hass, mock_config_entry)
    state = hass.states.get(climate)
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_TEMPERATURE] == 19.5


@pytest.mark.parametrize(
    ("options", "capabilities"),
    [
        ({OPT_THERMOSTAT_RELAY: "3"}, {}),
        ({}, {"temperature": False}),
        ({OPT_THERMOSTAT: False}, {}),
    ],
)
async def test_no_thermostat(
    hass: HomeAssistant,
    display: FakeDisplay,
    mock_config_entry: MockConfigEntry,
    options: dict[str, Any],
    capabilities: dict[str, Any],
) -> None:
    """No thermostat without its relay, without a temperature source or when it is off."""
    display.info["capabilities"] |= capabilities
    assert await _setup(hass, mock_config_entry, **options) is None


async def test_humidity_unknown(hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry) -> None:
    """Missing readings are unknown."""
    del display.state["humidity"]
    del display.state["temperature"]
    climate = await _setup(hass, mock_config_entry)
    state = hass.states.get(climate)
    assert state.attributes.get(ATTR_CURRENT_HUMIDITY) is None
    assert state.attributes.get(ATTR_CURRENT_TEMPERATURE) is None
    await _call(hass, "set_hvac_mode", climate, **{ATTR_HVAC_MODE: HVACMode.HEAT})
    assert _relay_commands(display) == []
    assert entity_id(hass, CLIMATE_DOMAIN, "thermostat") == climate
