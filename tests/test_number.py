"""Numbers, selects and texts backed by display settings."""

from __future__ import annotations

from homeassistant.components.number import ATTR_MAX, ATTR_MIN, ATTR_STEP, ATTR_VALUE, SERVICE_SET_VALUE
from homeassistant.components.select import ATTR_OPTION, SERVICE_SELECT_OPTION
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.shellyelevateintegration.api import ShellyElevateIntegrationCommandError

from .common import FakeDisplay, entity_id
from .conftest import setup_entry

pytestmark = pytest.mark.usefixtures("entity_registry_enabled_by_default")


async def test_number_from_schema(hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay) -> None:
    """Range and type come from the schema of the display."""
    delay = entity_id(hass, "number", "screensaver_delay")
    state = hass.states.get(delay)
    assert state.state == "45.0"
    assert (state.attributes[ATTR_MIN], state.attributes[ATTR_MAX], state.attributes[ATTR_STEP]) == (5, 86400, 5)
    await hass.services.async_call(
        "number", SERVICE_SET_VALUE, {ATTR_ENTITY_ID: delay, ATTR_VALUE: 120.4}, blocking=True
    )
    assert display.writes == [{"screenSaverDelay": 120}]
    assert hass.states.get(delay).state == "120.0"


async def test_number_float_setting(
    hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry
) -> None:
    """A float setting keeps its fraction."""
    item = next(item for item in display.schema if item["key"] == "voiceWakeSensitivity")
    item |= {"type": "float", "min": 0, "max": 1, "step": 0.05}
    display.settings["voiceWakeSensitivity"] = 0.5
    await setup_entry(hass, mock_config_entry)
    sensitivity = entity_id(hass, "number", "wake_word_sensitivity")
    await hass.services.async_call(
        "number", SERVICE_SET_VALUE, {ATTR_ENTITY_ID: sensitivity, ATTR_VALUE: 0.35}, blocking=True
    )
    assert display.writes == [{"voiceWakeSensitivity": 0.35}]


async def test_number_without_schema(
    hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry
) -> None:
    """Without a schema the ranges of protocol v1 apply."""
    display.schema_error = ShellyElevateIntegrationCommandError("unsupported")
    display.settings["minBrightness"] = None
    await setup_entry(hass, mock_config_entry)
    state = hass.states.get(entity_id(hass, "number", "screensaver_delay"))
    assert state.attributes[ATTR_MIN] == 5
    assert hass.states.get(entity_id(hass, "number", "min_brightness")).state == STATE_UNKNOWN


async def test_number_unavailable_while_hidden(
    hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay
) -> None:
    """The screensaver delay cannot take effect without the screensaver."""
    display.client.push({"type": "settings_changed", "changes": {"screenSaver": False}})
    await hass.async_block_till_done()
    assert hass.states.get(entity_id(hass, "number", "screensaver_delay")).state == STATE_UNAVAILABLE


async def test_select(hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay) -> None:
    """An enum setting is a select."""
    saver = entity_id(hass, "select", "screensaver_type")
    assert hass.states.get(saver).state == "off"
    await hass.services.async_call(
        "select", SERVICE_SELECT_OPTION, {ATTR_ENTITY_ID: saver, ATTR_OPTION: "clock_date"}, blocking=True
    )
    assert display.writes == [{"screenSaverId": 2}]
    assert hass.states.get(saver).state == "clock_date"
    display.client.push({"type": "settings_changed", "changes": {"screenSaverId": 9}})
    await hass.async_block_till_done()
    assert hass.states.get(saver).state == STATE_UNKNOWN


async def test_text(hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay) -> None:
    """The dashboard URL is a text."""
    url = entity_id(hass, "text", "dashboard_url")
    assert hass.states.get(url).state == "http://homeassistant.local:8123/lovelace/0"
    await hass.services.async_call(
        "text", "set_value", {ATTR_ENTITY_ID: url, "value": "http://ha.local:8123/kiosk"}, blocking=True
    )
    assert display.writes == [{"webviewUrl": "http://ha.local:8123/kiosk"}]


async def test_text_without_value(
    hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry
) -> None:
    """A missing value is unknown."""
    display.settings["webviewUrl"] = None
    await setup_entry(hass, mock_config_entry)
    assert hass.states.get(entity_id(hass, "text", "dashboard_url")).state == STATE_UNKNOWN
