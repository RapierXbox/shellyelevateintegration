"""App update entity."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.update import (
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    ATTR_RELEASE_URL,
    ATTR_VERSION,
    SERVICE_INSTALL,
    UpdateEntityFeature,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_SUPPORTED_FEATURES, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.shellyelevateintegration.adb.apk import _CACHE
from custom_components.shellyelevateintegration.const import OPT_UPDATE_CHANNEL

from .common import FakeDisplay, entity_id
from .conftest import RELEASES, setup_entry

UPDATE = "custom_components.shellyelevateintegration.update"
STABLE = RELEASES[1]
BETA = RELEASES[0]


def _entity(hass: HomeAssistant):
    return hass.data["entity_components"]["update"].get_entity(entity_id(hass, "update", "app_update"))


async def _install(hass: HomeAssistant, version: str | None = None) -> None:
    data = {ATTR_ENTITY_ID: entity_id(hass, "update", "app_update")}
    if version is not None:
        data[ATTR_VERSION] = version
    await hass.services.async_call("update", SERVICE_INSTALL, data, blocking=True)


async def _wait_for_command(display: FakeDisplay, action: str) -> None:
    for _ in range(100):
        if any(command == action for command, _params in display.commands):
            return
        await asyncio.sleep(0)
    raise AssertionError(f"{action} was not sent")


async def test_update_available(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    """The latest stable release is offered."""
    state = hass.states.get(entity_id(hass, "update", "app_update"))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "3.26150.1200"
    assert state.attributes[ATTR_LATEST_VERSION] == STABLE.version
    assert state.attributes[ATTR_RELEASE_URL] == STABLE.url
    features = state.attributes[ATTR_SUPPORTED_FEATURES]
    assert features & UpdateEntityFeature.INSTALL
    assert features & UpdateEntityFeature.SPECIFIC_VERSION
    assert await _entity(hass).async_release_notes() == "Fixes"
    assert _entity(hass).version_is_newer("3.26160.0900", "v3.26150.1200")


async def test_beta_channel(hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry) -> None:
    """The beta channel includes pre-releases."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, options={OPT_UPDATE_CHANNEL: "beta"})
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id(hass, "update", "app_update")).attributes[ATTR_LATEST_VERSION] == BETA.version


async def test_no_release_known(hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry) -> None:
    """Without a release the installed version counts as latest; GitHub errors are not fatal."""
    hass.data[_CACHE]["releases"] = []
    await setup_entry(hass, mock_config_entry)
    entity = _entity(hass)
    state = hass.states.get(entity.entity_id)
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_LATEST_VERSION] == "3.26150.1200"
    assert state.attributes[ATTR_RELEASE_URL] is None
    assert await entity.async_release_notes() is None
    with patch(f"{UPDATE}.async_latest_release", side_effect=HomeAssistantError("rate limited")):
        await entity.async_update()
    with pytest.raises(HomeAssistantError) as err:
        await entity.async_install(None, False)
    assert err.value.translation_key == "no_release"


async def test_self_update(hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay) -> None:
    """The app updates itself; the entity waits for the new version."""
    task = hass.async_create_task(_install(hass))
    await _wait_for_command(display, "app.update")
    assert display.commands[-1] == (
        "app.update",
        {"url": STABLE.apk_url, "version": STABLE.version, "sha256": STABLE.sha256},
    )
    assert hass.states.get(entity_id(hass, "update", "app_update")).attributes["in_progress"] is True
    # the app restarts with the new version
    display.client.set_available(False)
    await asyncio.sleep(0)
    display.client.info.fw_version = STABLE.version
    display.client.set_available(True)
    await task
    state = hass.states.get(entity_id(hass, "update", "app_update"))
    assert state.attributes["in_progress"] is False
    assert state.state == STATE_OFF
    reasons = [backup["reason"] for backup in init_integration.runtime_data.backups.list()]
    assert "before_update" in reasons


async def test_self_update_info_changed(
    hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay
) -> None:
    """A hello with the new version also ends the wait (specific version, no checksum)."""
    task = hass.async_create_task(_install(hass, BETA.version))
    await _wait_for_command(display, "app.update")
    assert display.commands[-1] == ("app.update", {"url": BETA.apk_url, "version": BETA.version})
    display.client.info.fw_version = BETA.version
    display.client.push({"type": "_info_changed"})
    await task


async def test_self_update_failed(hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay) -> None:
    """The app reports that its update failed."""
    task = hass.async_create_task(_install(hass))
    await _wait_for_command(display, "app.update")
    display.client.push({"type": "event", "event": "app_update", "status": "downloading"})
    display.client.push({"type": "event", "event": "app_update", "status": "failed", "reason": "checksum"})
    with pytest.raises(HomeAssistantError) as err:
        await task
    assert err.value.translation_key == "app_update_failed"
    assert err.value.translation_placeholders == {"reason": "checksum"}


async def test_self_update_old_version(
    hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay
) -> None:
    """The app came back with the old version."""
    task = hass.async_create_task(_install(hass))
    await _wait_for_command(display, "app.update")
    display.client.push({"type": "_info_changed"})
    with pytest.raises(HomeAssistantError) as err:
        await task
    assert "3.26150.1200" in err.value.translation_placeholders["reason"]


async def test_self_update_timeout(
    hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay
) -> None:
    """No answer from the app at all."""
    with patch(f"{UPDATE}.SELF_UPDATE_TIMEOUT", 0.01), pytest.raises(HomeAssistantError) as err:
        await _install(hass)
    assert err.value.translation_key == "app_update_timeout"


async def test_self_update_not_back(
    hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay
) -> None:
    """The app went away for the update and never came back."""
    with patch(f"{UPDATE}.RESTART_TIMEOUT", 0.05):
        task = hass.async_create_task(_install(hass))
        await _wait_for_command(display, "app.update")
        display.client.set_available(False)
        with pytest.raises(HomeAssistantError) as err:
            await task
    assert "did not come back" in err.value.translation_placeholders["reason"]


async def test_version_not_found(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    """An unknown version cannot be installed."""
    with pytest.raises(HomeAssistantError) as err:
        await _install(hass, "1.0.0")
    assert err.value.translation_key == "version_not_found"


async def test_install_over_adb(hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry) -> None:
    """Without self update ADB installs; the entity stays available while the app is down."""
    display.info["capabilities"]["self_update"] = False
    await setup_entry(hass, mock_config_entry)
    device = mock_config_entry.runtime_data
    entity = _entity(hass)
    assert not entity.supported_features & UpdateEntityFeature.INSTALL
    with pytest.raises(HomeAssistantError) as err:
        await entity.async_install(None, False)
    assert err.value.translation_key == "no_install_method"

    device.adb = MagicMock(async_install_app=AsyncMock())
    device.permissions = MagicMock()
    display.client.set_available(False)
    await hass.async_block_till_done()
    assert hass.states.get(entity.entity_id).state != STATE_UNAVAILABLE
    assert entity.supported_features & UpdateEntityFeature.INSTALL
    await _install(hass)
    device.adb.async_install_app.assert_awaited_once_with(STABLE, post_install=False)
    device.permissions.async_after_update.assert_called_once()
