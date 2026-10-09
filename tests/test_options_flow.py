"""Options flow (and flows that need a loaded display)."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import SOURCE_ZEROCONF, ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.shellyelevateintegration.config_flow import ShellyElevateIntegrationConfigFlow
from custom_components.shellyelevateintegration.const import (
    CONF_PANEL,
    DOMAIN,
    OPT_ADB,
    OPT_AUTO_BACKUP,
    OPT_BACKUP_KEEP,
    OPT_RELAYS_AS_LIGHTS,
    OPT_THERMOSTAT,
    OPT_THERMOSTAT_MAX_TEMP,
    OPT_THERMOSTAT_MIN_CYCLE,
    OPT_THERMOSTAT_MIN_TEMP,
    OPT_THERMOSTAT_MODE,
    OPT_THERMOSTAT_RELAY,
    OPT_THERMOSTAT_SENSOR,
    OPT_THERMOSTAT_TOLERANCE,
    OPT_UPDATE_CHANNEL,
    OPT_WATCHDOG,
)

from .common import FakeDisplay
from .conftest import setup_entry
from .const import HOST
from .test_config_flow import ZEROCONF_INFO


@pytest.fixture
async def panel(hass: HomeAssistant) -> MockConfigEntry:
    """The panel-only entry the integration adds by itself."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    return next(entry for entry in hass.config_entries.async_entries(DOMAIN) if entry.data.get(CONF_PANEL))


async def test_zeroconf_known_display_connected(
    hass: HomeAssistant, init_integration: MockConfigEntry, flow_mocks: dict
) -> None:
    """A connected display is not moved by an announcement from elsewhere."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_INFO)
    assert result["reason"] == "already_configured"
    assert init_integration.data[CONF_HOST] == HOST
    flow_mocks["probe"].assert_not_awaited()


async def test_panel_entry_has_no_options(hass: HomeAssistant, panel: MockConfigEntry) -> None:
    """The panel entry shows no options cog and its options flow aborts (issue #1)."""
    assert ShellyElevateIntegrationConfigFlow.async_supports_options_flow(panel) is False
    assert panel.supports_options is False
    result = await hass.config_entries.options.async_init(panel.entry_id)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "panel_entry"


async def test_display_entry_has_options(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """A display entry has options."""
    mock_config_entry.add_to_hass(hass)
    assert ShellyElevateIntegrationConfigFlow.async_supports_options_flow(mock_config_entry) is True
    assert mock_config_entry.supports_options is True


GENERAL = {
    OPT_RELAYS_AS_LIGHTS: True,
    OPT_THERMOSTAT: False,
    OPT_AUTO_BACKUP: True,
    OPT_BACKUP_KEEP: 5,
    OPT_UPDATE_CHANNEL: "beta",
    OPT_ADB: False,
    OPT_WATCHDOG: False,
}
THERMOSTAT = {
    OPT_THERMOSTAT_RELAY: "1",
    OPT_THERMOSTAT_MODE: "heat",
    OPT_THERMOSTAT_TOLERANCE: 0.5,
    OPT_THERMOSTAT_MIN_CYCLE: 60,
    OPT_THERMOSTAT_MIN_TEMP: 10,
    OPT_THERMOSTAT_MAX_TEMP: 25,
}


def _default(result: dict[str, Any], key: str) -> Any:
    return next(item for item in result["data_schema"].schema if item == key).default()


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_not_loaded(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Options of a display that is not connected (no capabilities known)."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert _default(result, OPT_ADB) is False

    result = await hass.config_entries.options.async_configure(result["flow_id"], {**GENERAL, OPT_THERMOSTAT: True})
    assert result["step_id"] == "thermostat"
    assert len(_default(result, OPT_THERMOSTAT_RELAY) or "0") == 1
    result = await hass.config_entries.options.async_configure(result["flow_id"], THERMOSTAT)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert OPT_THERMOSTAT_SENSOR not in result["data"]


async def test_options_general_only(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    """Without the thermostat the general options are stored at once."""
    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    assert _default(result, OPT_ADB) is False  # adbWifiEnabled is off on the display
    result = await hass.config_entries.options.async_configure(result["flow_id"], GENERAL)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == GENERAL
    await hass.async_block_till_done()
    assert init_integration.options == GENERAL
    assert init_integration.state is ConfigEntryState.LOADED


async def test_options_thermostat(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    """The thermostat options follow and are validated."""
    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {**GENERAL, OPT_THERMOSTAT: True})
    assert result["step_id"] == "thermostat"
    relay_selector = next(item for item in result["data_schema"].schema if item == OPT_THERMOSTAT_RELAY)
    assert len(result["data_schema"].schema[relay_selector].config["options"]) == 2

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**THERMOSTAT, OPT_THERMOSTAT_MIN_TEMP: 25, OPT_THERMOSTAT_MAX_TEMP: 20}
    )
    assert result["errors"] == {"base": "invalid_temp_range"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**THERMOSTAT, OPT_THERMOSTAT_SENSOR: "sensor.living_room"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][OPT_THERMOSTAT_SENSOR] == "sensor.living_room"
    assert result["data"][OPT_THERMOSTAT] is True
    await hass.async_block_till_done()


async def test_options_thermostat_needs_sensor(
    hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry
) -> None:
    """A display without a temperature sensor needs another sensor."""
    display.info["capabilities"]["temperature"] = False
    await setup_entry(hass, mock_config_entry)
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {**GENERAL, OPT_THERMOSTAT: True})
    result = await hass.config_entries.options.async_configure(result["flow_id"], THERMOSTAT)
    assert result["errors"] == {OPT_THERMOSTAT_SENSOR: "sensor_required"}


async def test_options_thermostat_without_relays(
    hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry
) -> None:
    """The Wall Display D1 has no relay for a thermostat."""
    display.info["capabilities"] |= {"relays": 0, "inputs": 0, "optional_relays_from": None}
    await setup_entry(hass, mock_config_entry)
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {**GENERAL, OPT_THERMOSTAT: True})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {OPT_THERMOSTAT: "no_relays"}


@pytest.mark.usefixtures("adb")
async def test_options_adb_default_from_display(
    hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry
) -> None:
    """ADB defaults to the display's own ADB over Wi-Fi setting."""
    display.settings["adbWifiEnabled"] = True
    await setup_entry(hass, mock_config_entry)
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert _default(result, OPT_ADB) is True
