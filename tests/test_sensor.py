"""Sensors and binary sensors."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .common import FakeDisplay, entity_id
from .conftest import setup_entry
from .const import LEGACY_DEVICE_ID

pytestmark = pytest.mark.usefixtures("entity_registry_enabled_by_default")


async def test_sensors(hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay) -> None:
    """Sensors show the state of the display."""
    expected = {
        "temperature": "21.4",
        "humidity": "45.2",
        "lux": "120.5",
        "proximity": "3.2",
        "screen_brightness": "78",
        "wifi_rssi": "-55",
        "cpu_temperature": "48.3",
        "memory_free": "512",
        "voice_state": "idle",
    }
    for key, value in expected.items():
        assert hass.states.get(entity_id(hass, "sensor", key)).state == value, key

    display.client.push_state({"temperature": 22.0, "screen.brightness": None})
    await hass.async_block_till_done()
    assert hass.states.get(entity_id(hass, "sensor", "temperature")).state == "22.0"
    assert hass.states.get(entity_id(hass, "sensor", "screen_brightness")).state == STATE_UNKNOWN


async def test_uptime_sensor(
    hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay, freezer: FrozenDateTimeFactory
) -> None:
    """The start time only moves on a restart."""
    started = entity_id(hass, "sensor", "app_started")
    first = hass.states.get(started).state
    assert dt_util.parse_datetime(first) is not None

    freezer.tick(timedelta(seconds=30))
    display.client.push_state({"uptime": 3630, "temperature": 21.0})
    await hass.async_block_till_done()
    assert hass.states.get(started).state == first

    display.client.push_state({"uptime": 10})
    await hass.async_block_till_done()
    assert hass.states.get(started).state != first

    display.client.push_state({"uptime": None})
    await hass.async_block_till_done()
    assert hass.states.get(started).state == STATE_UNKNOWN


async def test_binary_sensors(hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay) -> None:
    """Presence, inputs, screen and microphone."""
    presence = entity_id(hass, "binary_sensor", "presence")
    assert hass.states.get(presence).state == STATE_OFF
    assert hass.states.get(entity_id(hass, "binary_sensor", "input_0")).state == STATE_OFF
    assert hass.states.get(entity_id(hass, "binary_sensor", "screen_on")).state == STATE_ON
    assert hass.states.get(entity_id(hass, "binary_sensor", "voice_muted")).state == STATE_OFF

    display.client.push_state({"presence": True, "input.0": None})
    await hass.async_block_till_done()
    assert hass.states.get(presence).state == STATE_ON
    assert hass.states.get(entity_id(hass, "binary_sensor", "input_0")).state == STATE_UNKNOWN


async def test_legacy_sensors(hass: HomeAssistant, init_legacy: MockConfigEntry, legacy_display: FakeDisplay) -> None:
    """The legacy client only has the keys it polls."""
    registry = er.async_get(hass)
    assert entity_id(hass, "sensor", "temperature", LEGACY_DEVICE_ID)
    assert entity_id(hass, "sensor", "screen_brightness", LEGACY_DEVICE_ID)
    assert registry.async_get_entity_id("sensor", "shellyelevateintegration", f"{LEGACY_DEVICE_ID}_voice_state") is None
    assert (
        registry.async_get_entity_id("binary_sensor", "shellyelevateintegration", f"{LEGACY_DEVICE_ID}_screen_on")
        is None
    )


async def test_display_without_sensors(
    hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry
) -> None:
    """The XL has no temperature or humidity sensor."""
    display.info["capabilities"] |= {"temperature": False, "humidity": False}
    await setup_entry(hass, mock_config_entry)
    registry = er.async_get(hass)
    assert registry.async_get_entity_id("sensor", "shellyelevateintegration", "shellyelevate-4a2f_temperature") is None
