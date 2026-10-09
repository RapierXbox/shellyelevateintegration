"""Runtime object of a display: messages, availability and settings."""

from __future__ import annotations

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.shellyelevateintegration.api import ShellyElevateIntegrationConnectionError
from custom_components.shellyelevateintegration.const import DOMAIN

from .common import FakeDisplay
from .conftest import setup_entry
from .const import OTHER_DEVICE_ID


def _reauth(hass: HomeAssistant) -> bool:
    return any(
        flow["context"]["source"] == SOURCE_REAUTH
        for flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    )


async def test_auth_failed_starts_reauth(
    hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay
) -> None:
    """A rejected token on the push channel asks to pair again."""
    display.client.push({"type": "_auth_failed"})
    await hass.async_block_till_done()
    assert _reauth(hass)


async def test_incompatible_reloads(
    hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay
) -> None:
    """A display that switched protocol versions is reloaded (setup then reports it)."""
    clients = len(display.clients)
    display.client.push({"type": "_incompatible"})
    await hass.async_block_till_done()
    assert len(display.clients) == clients + 1


async def test_other_display_at_address(
    hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay
) -> None:
    """Another display answering after a reconnect fails the setup with a clear error."""
    display.client.set_available(False)
    display.client.info.device_id = OTHER_DEVICE_ID
    display.info["id"] = OTHER_DEVICE_ID
    display.client.set_available(True)
    await hass.async_block_till_done()
    assert init_integration.state is ConfigEntryState.SETUP_ERROR


async def test_listener_errors_isolated(
    hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay
) -> None:
    """One failing listener does not keep the others from updating."""
    device = init_integration.runtime_data
    received: list[object] = []

    def broken(*_args: object) -> None:
        raise RuntimeError("entity bug")

    device.async_add_state_listener(broken)
    device.async_add_state_listener(received.append)
    display.client.push_state({"relay.0": True})
    assert received == [{"relay.0": True}]
    # without a device registry entry there is nothing to refresh
    device.device_entry_id = None
    display.client.push({"type": "_info_changed"})


async def test_settings_helpers(hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay) -> None:
    """Settings writes, unknown keys and errors."""
    device = init_integration.runtime_data
    assert not device.setting_visible("doesNotExist")
    assert not device.setting_exists("doesNotExist")
    display.settings["custom"] = 1
    device.client.settings["custom"] = 1
    assert device.setting_visible("custom")  # no rules for it
    result = await device.async_set_settings({"unknownToApp": 1})
    assert result.ignored == ["unknownToApp"]
    assert display.writes == []

    display.set_settings_error = ShellyElevateIntegrationConnectionError("reset")
    with pytest.raises(HomeAssistantError) as err:
        await device.async_set_settings({"screenSaverDelay": 5})
    assert err.value.translation_key == "settings_failed"
    display.settings_error = ShellyElevateIntegrationConnectionError("reset")
    with pytest.raises(HomeAssistantError) as err:
        await device.async_refresh_settings()
    assert err.value.translation_key == "settings_read_failed"


async def test_legacy_rules(hass: HomeAssistant, init_legacy: MockConfigEntry, legacy_display: FakeDisplay) -> None:
    """The legacy app uses the built-in schema and plays media without the setting."""
    device = init_legacy.runtime_data
    assert device.known_caps >= {"relays", "speaker"}
    assert device.setting_visible("webviewUrl")
    assert device.media_active
    del device.client.settings["mediaEnabled"]
    assert device.media_active
    device._schema = None
    assert device.visibility().definition("liteMode") is not None
    assert not device.voice_active
    assert not device.bluetooth_active


async def test_fallback_rules_without_schema(
    hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry
) -> None:
    """Without a schema the rules of the current app apply."""
    from custom_components.shellyelevateintegration.api import ShellyElevateIntegrationCommandError

    display.schema_error = ShellyElevateIntegrationCommandError("unsupported")
    await setup_entry(hass, mock_config_entry)
    device = mock_config_entry.runtime_data
    assert device.schema is None
    assert device.visibility().definition("screenSaverDelay") is not None
    assert device.setting_visible("screenSaverDelay")
