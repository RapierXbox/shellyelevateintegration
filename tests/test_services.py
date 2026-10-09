"""Actions (services)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.shellyelevateintegration.api import ShellyElevateIntegrationConnectionError
from custom_components.shellyelevateintegration.const import DOMAIN
from custom_components.shellyelevateintegration.revert import RevertOptions
from custom_components.shellyelevateintegration.settings.profiles import async_get_profile_manager

from .common import FakeDisplay
from .conftest import RELEASES
from .const import DEVICE_ID, HOST, OTHER_DEVICE_ID


def _device_id(hass: HomeAssistant, entry: MockConfigEntry, identifier: str = DEVICE_ID) -> str:
    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, identifier), entry.entry_id)
    assert device is not None
    return device.id


async def _call(hass: HomeAssistant, service: str, data: dict[str, Any], *, response: bool = True) -> Any:
    return await hass.services.async_call(DOMAIN, service, data, blocking=True, return_response=response)


async def test_backup_and_restore(hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay) -> None:
    """A manual backup is restored later; only changed keys are written."""
    device_id = _device_id(hass, init_integration)
    result = await _call(hass, "backup_settings", {ATTR_DEVICE_ID: device_id, "name": "Before party"})
    backup = result["backups"][0]
    assert backup["device_id"] == device_id

    display.settings["screenSaverDelay"] = 600
    result = await _call(hass, "restore_settings", {ATTR_DEVICE_ID: device_id, "backup_id": backup["backup_id"]})
    assert result["changes"] == [{"key": "screenSaverDelay", "current": 600, "new": 45}]
    assert display.writes == [{"screenSaverDelay": 45}]

    result = await _call(hass, "restore_settings", {ATTR_DEVICE_ID: device_id, "keys": ["webviewUrl"]})
    assert result["changes"] == []


async def test_profiles(hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay) -> None:
    """Save a profile from a display, then apply it by name."""
    device_id = _device_id(hass, init_integration)
    result = await _call(
        hass,
        "save_profile",
        {
            ATTR_DEVICE_ID: device_id,
            "name": "Kitchen",
            "keys": ["screenSaverDelay", "mqttDeviceId"],
            "make_default": True,
        },
    )
    profile_id = result["profile_id"]
    manager = await async_get_profile_manager(hass)
    assert manager.profiles[profile_id]["settings"] == {"screenSaverDelay": 45}
    assert manager.default_profile_id == profile_id
    # the same name replaces the profile
    result = await _call(hass, "save_profile", {ATTR_DEVICE_ID: device_id, "name": "kitchen"})
    assert result["profile_id"] == profile_id

    await manager.async_save_profile("Hall", {"screenSaverDelay": 90}, profile_id="hall")
    result = await _call(hass, "apply_profile", {ATTR_DEVICE_ID: device_id, "profile": "HALL"})
    assert result["results"][device_id] == [{"key": "screenSaverDelay", "current": 45, "new": 90}]
    assert display.writes == [{"screenSaverDelay": 90}]
    result = await _call(hass, "apply_profile", {ATTR_DEVICE_ID: [device_id], "profile": "hall"})
    assert result["results"][device_id] == []
    with pytest.raises(HomeAssistantError):
        await _call(hass, "apply_profile", {ATTR_DEVICE_ID: device_id, "profile": "nope"})


async def test_copy_settings(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    display: FakeDisplay,
    second_display: tuple[FakeDisplay, MockConfigEntry],
) -> None:
    """Portable settings are copied; per-device keys never."""
    other, other_entry = second_display
    source = _device_id(hass, init_integration)
    target = _device_id(hass, other_entry, OTHER_DEVICE_ID)
    result = await _call(
        hass,
        "copy_settings",
        {"source_device_id": source, ATTR_DEVICE_ID: [target, source], "keys": ["screenSaverDelay", "mqttDeviceId"]},
    )
    assert result["errors"] == {}
    assert result["results"][target] == [{"key": "screenSaverDelay", "current": 300, "new": 45}]
    assert other.writes == [{"screenSaverDelay": 45}]

    other.settings_error = ShellyElevateIntegrationConnectionError("timeout")
    result = await _call(hass, "copy_settings", {"source_device_id": source, ATTR_DEVICE_ID: target})
    assert target in result["errors"]


async def test_export_import(hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay) -> None:
    """Export without secrets and import it back as a backup (optionally applied)."""
    device_id = _device_id(hass, init_integration)
    export = await _call(hass, "export_settings", {ATTR_DEVICE_ID: device_id})
    assert export["format"] == "shellyelevateintegration.settings/1"
    assert export["device"]["id"] == DEVICE_ID
    assert "mqttPassword" not in export["settings"]
    full = await _call(hass, "export_settings", {ATTR_DEVICE_ID: device_id, "include_secrets": True})
    assert full["settings"]["mqttPassword"] == "hunter2"

    export["settings"]["screenSaverDelay"] = 999
    result = await _call(hass, "import_settings", {ATTR_DEVICE_ID: device_id, "settings": export, "name": "Imported"})
    assert result["changes"] == []
    backups = init_integration.runtime_data.backups.list()
    assert backups[0]["id"] == result["backup_id"]
    assert backups[0]["name"] == "Imported"
    assert "mqttDeviceId" not in backups[0]["settings"]

    result = await _call(
        hass, "import_settings", {ATTR_DEVICE_ID: device_id, "settings": {"screenSaverDelay": 120}, "apply": True}
    )
    assert result["changes"] == [{"key": "screenSaverDelay", "current": 45, "new": 120}]

    with pytest.raises(ServiceValidationError):
        await _call(hass, "import_settings", {ATTR_DEVICE_ID: device_id, "settings": {"settings": []}})


async def test_get_and_set_settings(
    hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay
) -> None:
    """Read (secrets redacted) and write settings."""
    device_id = _device_id(hass, init_integration)
    result = await _call(hass, "get_settings", {ATTR_DEVICE_ID: device_id})
    assert result["settings"]["mqttPassword"] == "**REDACTED**"
    assert result["settings"]["screenSaverDelay"] == 45
    await _call(
        hass, "set_settings", {ATTR_DEVICE_ID: [device_id], "settings": {"screenSaverDelay": 60}}, response=False
    )
    assert display.writes == [{"screenSaverDelay": 60}]


async def test_navigate_and_message(
    hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay
) -> None:
    """Navigation needs a path or a URL; messages go to the screen."""
    device_id = _device_id(hass, init_integration)
    await _call(hass, "navigate", {ATTR_DEVICE_ID: device_id, "path": "/lovelace/cameras"}, response=False)
    await _call(hass, "navigate", {ATTR_DEVICE_ID: device_id, "url": "http://example.com/"}, response=False)
    for data in ({}, {"path": "/a", "url": "http://example.com/"}):
        with pytest.raises(ServiceValidationError):
            await _call(hass, "navigate", {ATTR_DEVICE_ID: device_id, **data}, response=False)
    await _call(
        hass,
        "show_message",
        {ATTR_DEVICE_ID: device_id, "message": "Pizza", "title": "Door", "duration": 10, "level": "alert"},
        response=False,
    )
    assert display.commands == [
        ("webview.navigate", {"path": "/lovelace/cameras"}),
        ("webview.navigate", {"url": "http://example.com/"}),
        ("ui.notify", {"message": "Pizza", "title": "Door", "duration": 10.0, "level": "alert"}),
    ]


async def test_adb_actions_without_adb(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    """ADB actions need ADB."""
    device_id = _device_id(hass, init_integration)
    for service, data in (("adb_shell", {"command": "id"}), ("install_app", {})):
        with pytest.raises(ServiceValidationError) as err:
            await _call(hass, service, {ATTR_DEVICE_ID: device_id, **data})
        assert err.value.translation_key == "adb_disabled"


async def test_adb_actions(
    hass: HomeAssistant, display: FakeDisplay, adb: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Shell commands and app installs over ADB."""
    from .conftest import setup_entry

    await setup_entry(hass, mock_config_entry)
    device_id = _device_id(hass, mock_config_entry)
    assert await _call(hass, "adb_shell", {ATTR_DEVICE_ID: device_id, "command": "id"}) == {"output": "ok"}
    adb.async_shell.assert_awaited_with("id", timeout=60)

    result = await _call(hass, "install_app", {ATTR_DEVICE_ID: device_id})
    assert result == {"version": RELEASES[1].version}
    assert adb.async_install_app.await_args.args == (None, "stable")
    await _call(hass, "install_app", {ATTR_DEVICE_ID: device_id, "version": RELEASES[0].version})
    assert adb.async_install_app.await_args.args[0] == RELEASES[0]
    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "install_app", {ATTR_DEVICE_ID: device_id, "version": "0.0.1"})
    assert err.value.translation_key == "version_not_found"


async def test_revert_display(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    """The revert action passes its options on."""
    revert = AsyncMock(return_value={"remaining": [], "entry_removed": False, "adb_disabled": False, "warnings": []})
    with patch("custom_components.shellyelevateintegration.services.async_revert", revert):
        result = await _call(
            hass, "revert_display", {ATTR_DEVICE_ID: _device_id(hass, init_integration), "reboot": False}
        )
    assert result["remaining"] == []
    options = revert.await_args.args[1]
    assert options == RevertOptions(
        host=HOST, remove_entry=True, reboot=False, disable_adb=False, accept_wifi_loss=False
    )
    revert.await_args.args[2]("step", {})


async def test_unknown_devices(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    """Devices that are unknown, of another integration or not loaded are refused."""
    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "get_settings", {ATTR_DEVICE_ID: "nope"})
    assert err.value.translation_key == "device_not_found"

    other_entry = MockConfigEntry(domain="other")
    other_entry.add_to_hass(hass)
    other = dr.async_get(hass).async_get_or_create(config_entry_id=other_entry.entry_id, identifiers={("other", "x")})
    with pytest.raises(ServiceValidationError):
        await _call(hass, "get_settings", {ATTR_DEVICE_ID: other.id})

    device_id = _device_id(hass, init_integration)
    assert await hass.config_entries.async_unload(init_integration.entry_id)
    with pytest.raises(HomeAssistantError) as err:
        await _call(hass, "get_settings", {ATTR_DEVICE_ID: device_id})
    assert err.value.translation_key == "device_not_loaded"
