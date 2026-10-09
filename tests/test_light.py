"""Lights: the screen and the dimmer backplate."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_EFFECT, DOMAIN as LIGHT_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .common import FakeDisplay, entity_id
from .conftest import setup_entry


async def _turn(hass: HomeAssistant, service: str, target: str, **data: Any) -> None:
    await hass.services.async_call(LIGHT_DOMAIN, service, {ATTR_ENTITY_ID: target, **data}, blocking=True)


async def test_screen_light(hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay) -> None:
    """The screen is a light: awake, brightness and auto brightness as effect."""
    screen = entity_id(hass, LIGHT_DOMAIN, "screen")
    state = hass.states.get(screen)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 200
    assert state.attributes[ATTR_EFFECT] == "auto_brightness"

    await _turn(hass, SERVICE_TURN_ON, screen)
    assert display.commands[-1] == ("screen.wake", {})
    await _turn(hass, SERVICE_TURN_ON, screen, brightness=128)
    assert display.commands[-1] == ("screen.set", {"brightness": 128, "auto": False})
    await _turn(hass, SERVICE_TURN_ON, screen, effect="manual")
    assert display.commands[-1] == ("screen.set", {"auto": False})
    await _turn(hass, SERVICE_TURN_OFF, screen)
    assert display.commands[-1] == ("screen.sleep", {})

    display.client.push_state({"screen.on": False, "screen.brightness": 0, "screen.auto_brightness": False})
    await hass.async_block_till_done()
    state = hass.states.get(screen)
    assert state.state == STATE_OFF

    display.commands.clear()
    await _turn(hass, SERVICE_TURN_ON, screen, brightness=10, effect="auto_brightness")
    assert display.commands == [("screen.wake", {}), ("screen.set", {"brightness": 10, "auto": True})]


async def test_screen_light_unknown_values(
    hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry
) -> None:
    """Without brightness readings the light still works."""
    for key in ("screen.brightness", "screen.auto_brightness"):
        del display.state[key]
    await setup_entry(hass, mock_config_entry)
    state = hass.states.get(entity_id(hass, LIGHT_DOMAIN, "screen"))
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_BRIGHTNESS) is None
    assert state.attributes.get(ATTR_EFFECT) is None


@pytest.fixture
async def dimmer_display(hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry) -> FakeDisplay:
    """A display with the dimmer backplate."""
    display.info["capabilities"]["dimmer"] = True
    display.state |= {"dimmer.on": True, "dimmer.brightness": 40, "dimmer.power": 12.5}
    await setup_entry(hass, mock_config_entry)
    return display


async def test_dimmer(hass: HomeAssistant, dimmer_display: FakeDisplay) -> None:
    """The dimmer works in percent on the display."""
    dimmer = entity_id(hass, LIGHT_DOMAIN, "dimmer")
    state = hass.states.get(dimmer)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 102
    assert hass.states.get(entity_id(hass, "sensor", "dimmer_power")).state == "12.5"

    await _turn(hass, SERVICE_TURN_ON, dimmer, brightness=255)
    assert dimmer_display.commands[-1] == ("dimmer.set", {"on": True, "brightness": 100})
    await _turn(hass, SERVICE_TURN_ON, dimmer, brightness=1)
    assert dimmer_display.commands[-1] == ("dimmer.set", {"on": True, "brightness": 1})
    await _turn(hass, SERVICE_TURN_ON, dimmer)
    assert dimmer_display.commands[-1] == ("dimmer.set", {"on": True})
    await _turn(hass, SERVICE_TURN_OFF, dimmer)
    assert dimmer_display.commands[-1] == ("dimmer.set", {"on": False})

    dimmer_display.client.push_state({"dimmer.on": None, "dimmer.brightness": None})
    await hass.async_block_till_done()
    assert hass.states.get(dimmer).attributes.get(ATTR_BRIGHTNESS) is None
