"""Buttons, the notify entity and the screenshot image."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.button import SERVICE_PRESS
from homeassistant.components.image import async_get_image
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.shellyelevateintegration.adb.manager import PermissionGrant
from custom_components.shellyelevateintegration.api import ShellyElevateIntegrationCommandError

from .common import PNG, FakeDisplay, entity_id
from .conftest import setup_entry

pytestmark = pytest.mark.usefixtures("entity_registry_enabled_by_default")


async def _press(hass: HomeAssistant, key: str) -> None:
    await hass.services.async_call(
        "button", SERVICE_PRESS, {ATTR_ENTITY_ID: entity_id(hass, "button", key)}, blocking=True
    )


@pytest.mark.parametrize(
    ("key", "action"),
    [
        ("reboot", "device.reboot"),
        ("restart_app", "app.restart"),
        ("reload_dashboard", "webview.reload"),
        ("wake", "screen.wake"),
        ("sleep", "screen.sleep"),
    ],
)
async def test_command_buttons(
    hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay, key: str, action: str
) -> None:
    """Each button runs its command."""
    await _press(hass, key)
    assert display.commands == [(action, {})]


async def test_backup_button(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    """The backup button stores a manual backup."""
    await _press(hass, "backup_settings")
    backups = init_integration.runtime_data.backups.list()
    assert backups[0]["reason"] == "manual"


async def test_screenshot(hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay) -> None:
    """The screenshot button updates the image."""
    image = entity_id(hass, "image", "screenshot")
    assert hass.states.get(image).state == STATE_UNKNOWN
    await _press(hass, "take_screenshot")
    assert hass.states.get(image).state != STATE_UNKNOWN
    assert (await async_get_image(hass, image)).content == PNG


async def test_image_takes_first_screenshot(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    """Opening the image takes a screenshot when there is none yet."""
    image = await async_get_image(hass, entity_id(hass, "image", "screenshot"))
    assert image.content == PNG
    assert image.content_type == "image/png"


async def test_screenshot_falls_back_to_adb(
    hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay
) -> None:
    """When the app cannot take one, ADB takes the screenshot."""
    display.screenshot_error = ShellyElevateIntegrationCommandError("500")
    adb = MagicMock(async_screenshot=AsyncMock(return_value=b"adb-png"))
    init_integration.runtime_data.adb = adb
    image = await async_get_image(hass, entity_id(hass, "image", "screenshot"))
    assert image.content == b"adb-png"


async def test_screenshot_unsupported(
    hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay
) -> None:
    """Without the app and without ADB there is no screenshot."""
    display.screenshot = None
    with pytest.raises(HomeAssistantError):
        await _press(hass, "take_screenshot")
    with pytest.raises(HomeAssistantError):
        await async_get_image(hass, entity_id(hass, "image", "screenshot"))


async def test_no_screenshot_without_capability(
    hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry
) -> None:
    """No screenshot entities without the capability and without ADB."""
    display.info["capabilities"]["screenshot"] = False
    await setup_entry(hass, mock_config_entry)
    registry = er.async_get(hass)
    assert registry.async_get_entity_id("image", "shellyelevateintegration", "shellyelevate-4a2f_screenshot") is None
    assert (
        registry.async_get_entity_id("button", "shellyelevateintegration", "shellyelevate-4a2f_take_screenshot") is None
    )
    # the press handler copes with a missing image entity
    from custom_components.shellyelevateintegration.button import _screenshot

    await _screenshot(mock_config_entry.runtime_data)


async def test_grant_permissions_button(
    hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry
) -> None:
    """With ADB the grant button exists and reports what is still missing."""
    adb = MagicMock()
    adb.async_grant_permissions = AsyncMock(
        return_value=PermissionGrant(granted=["RECORD_AUDIO"], missing=[], failed=[], restarted=True)
    )
    adb.async_missing_permissions = AsyncMock(return_value=[])
    mock_config_entry.add_to_hass(hass)

    async def _adb(*args, **kwargs):
        return adb

    from unittest.mock import patch

    with patch("custom_components.shellyelevateintegration.adb.manager.async_get_adb_manager", side_effect=_adb):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    await _press(hass, "grant_permissions")
    adb.async_grant_permissions.assert_awaited()

    adb.async_grant_permissions.return_value = PermissionGrant(
        granted=[], missing=["BLUETOOTH_SCAN"], failed=["perm_bt_scan"], restarted=False
    )
    with pytest.raises(HomeAssistantError) as err:
        await _press(hass, "grant_permissions")
    assert err.value.translation_key == "permissions_still_missing"


async def test_notify(hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay) -> None:
    """Messages are shown on the display."""
    notify = entity_id(hass, "notify", "notify")
    await hass.services.async_call(
        "notify", "send_message", {ATTR_ENTITY_ID: notify, "message": "Door open", "title": "Alarm"}, blocking=True
    )
    await hass.services.async_call("notify", "send_message", {ATTR_ENTITY_ID: notify, "message": "Hi"}, blocking=True)
    assert display.commands == [
        ("ui.notify", {"message": "Door open", "title": "Alarm"}),
        ("ui.notify", {"message": "Hi"}),
    ]
