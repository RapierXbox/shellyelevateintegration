"""Event entities and the event bus."""

from __future__ import annotations

from homeassistant.components.event import ATTR_EVENT_TYPE
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_capture_events

from custom_components.shellyelevateintegration.const import EVENT_SHELLY_ELEVATE

from .common import FakeDisplay, entity_id
from .conftest import setup_entry


async def test_input_and_swipe_events(
    hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay
) -> None:
    """Presses and swipes become events of their entities and of the event bus."""
    bus = async_capture_events(hass, EVENT_SHELLY_ELEVATE)
    input_event = entity_id(hass, "event", "input_0")
    swipe = entity_id(hass, "event", "swipe")
    assert hass.states.get(input_event).state == STATE_UNKNOWN

    display.client.push({"type": "event", "event": "input", "index": 0, "press": "double"})
    await hass.async_block_till_done()
    state = hass.states.get(input_event)
    assert state.attributes[ATTR_EVENT_TYPE] == "double"
    assert state.attributes["index"] == 0
    assert bus[0].data["entry_id"] == init_integration.entry_id
    assert bus[0].data["event"] == "input"

    display.client.push({"type": "event", "event": "swipe", "direction": "left", "fingers": 2})
    await hass.async_block_till_done()
    assert hass.states.get(swipe).attributes[ATTR_EVENT_TYPE] == "left_2"
    display.client.push({"type": "event", "event": "swipe", "direction": "up"})
    await hass.async_block_till_done()
    assert hass.states.get(swipe).attributes[ATTR_EVENT_TYPE] == "up"

    # not for these entities, or unknown types
    before = hass.states.get(swipe).last_changed
    for message in (
        {"type": "event", "event": "swipe", "direction": "sideways"},
        {"type": "event", "event": "input", "index": 3},
        {"type": "event", "event": "input", "press": "quadruple"},
        {"type": "event", "event": "button", "index": 0},
        {"type": "media_status", "status": {}},
    ):
        display.client.push(message)
    await hass.async_block_till_done()
    assert hass.states.get(swipe).last_changed == before
    assert hass.states.get(input_event).attributes[ATTR_EVENT_TYPE] == "double"
    # state changes do not touch events
    display.client.push_state({"relay.0": True})
    await hass.async_block_till_done()


async def test_swipe_unavailable_while_off(
    hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay
) -> None:
    """The swipe entity stays but is unavailable while the display does not publish swipes."""
    swipe = entity_id(hass, "event", "swipe")
    display.client.push({"type": "settings_changed", "changes": {"publishSwipeEvents": False}})
    await hass.async_block_till_done()
    assert hass.states.get(swipe).state == STATE_UNAVAILABLE
    display.client.push({"type": "settings_changed", "changes": {"publishSwipeEvents": True}})
    await hass.async_block_till_done()
    assert hass.states.get(swipe).state == STATE_UNKNOWN
    display.client.set_available(False)
    await hass.async_block_till_done()
    assert hass.states.get(swipe).state == STATE_UNAVAILABLE


async def test_xl_buttons(hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry) -> None:
    """The XL has four buttons and a power button."""
    display.info["codename"] = "BLAKE"
    display.info["capabilities"] |= {"buttons": 4, "power_button": True}
    await setup_entry(hass, mock_config_entry)
    button_3 = entity_id(hass, "event", "button_2")
    power = entity_id(hass, "event", "power_button")
    display.client.push({"type": "event", "event": "button", "index": 2, "press": "long"})
    display.client.push({"type": "event", "event": "power_button"})
    await hass.async_block_till_done()
    assert hass.states.get(button_3).attributes[ATTR_EVENT_TYPE] == "long"
    assert hass.states.get(power).attributes[ATTR_EVENT_TYPE] == "single"


async def test_legacy_has_no_events(hass: HomeAssistant, init_legacy: MockConfigEntry) -> None:
    """The legacy app only publishes events over MQTT."""
    entries = er.async_entries_for_config_entry(er.async_get(hass), init_legacy.entry_id)
    assert "event" not in {entry.domain for entry in entries}
