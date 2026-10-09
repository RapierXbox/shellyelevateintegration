"""Missing app permissions are granted over ADB or reported as a repair issue."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import time
from unittest.mock import MagicMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.shellyelevateintegration.adb.manager import AdbError, PermissionGrant
from custom_components.shellyelevateintegration.const import DOMAIN
from custom_components.shellyelevateintegration.permissions import (
    AUTO_GRANT_INTERVAL,
    SETTLE_TIME,
    permission_problems,
)

from .common import FakeDisplay
from .conftest import setup_entry

MIC = "microphone permission missing"
BLE = "location is off"


def _issue(hass: HomeAssistant, entry: MockConfigEntry) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(DOMAIN, f"permissions_missing_{entry.entry_id}")


def _grant(missing: list[str] | None = None, granted: list[str] | None = None) -> PermissionGrant:
    return PermissionGrant(granted=granted or [], missing=missing or [], failed=[], restarted=bool(granted))


async def _settle() -> None:
    for _ in range(5):
        await asyncio.sleep(0)


def test_permission_problems() -> None:
    """Only reasons a grant can fix count."""
    assert permission_problems({"voice.error": MIC, "ble.error": BLE}) == [MIC, BLE]
    assert permission_problems({"voice.error": "no pipeline", "ble.error": "bluetooth permission denied"}) == [
        "bluetooth permission denied"
    ]
    assert permission_problems({"voice.error": None, "ble.error": 3}) == []


async def test_issue_without_adb(hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry) -> None:
    """Without ADB the user is told; the issue goes when the display stops reporting it."""
    display.state["voice.error"] = MIC
    await setup_entry(hass, mock_config_entry)
    issue = _issue(hass, mock_config_entry)
    assert issue is not None
    assert issue.translation_placeholders["problems"] == MIC
    display.client.push_state({"voice.error": None})
    await hass.async_block_till_done()
    assert _issue(hass, mock_config_entry) is None
    with pytest.raises(HomeAssistantError):
        await mock_config_entry.runtime_data.permissions.async_grant()


async def test_auto_grant(
    hass: HomeAssistant, display: FakeDisplay, adb: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """With ADB the permissions are granted; a problem still reported after the settle time is an issue."""
    adb.async_grant_permissions.return_value = _grant(granted=["RECORD_AUDIO"])
    display.state["voice.error"] = MIC
    await setup_entry(hass, mock_config_entry)
    await _settle()
    adb.async_grant_permissions.assert_awaited_once()
    assert _issue(hass, mock_config_entry) is None

    # the app restarted but still reports it: another grant would not help
    with patch(
        "custom_components.shellyelevateintegration.permissions.time.monotonic",
        return_value=time.monotonic() + SETTLE_TIME + 1,
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=SETTLE_TIME + 1))
        await hass.async_block_till_done()
    assert _issue(hass, mock_config_entry) is not None
    assert adb.async_grant_permissions.await_count == 1

    # within the interval the state changing again does not grant again
    display.client.push_state({"ble.error": BLE})
    await hass.async_block_till_done()
    assert adb.async_grant_permissions.await_count == 1
    with patch(
        "custom_components.shellyelevateintegration.permissions.time.monotonic",
        return_value=time.monotonic() + AUTO_GRANT_INTERVAL + 1,
    ):
        display.client.push_state({"ble.error": "location permission missing"})
        await _settle()
    assert adb.async_grant_permissions.await_count == 2


async def test_grant_refused(
    hass: HomeAssistant, display: FakeDisplay, adb: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """pm grant refused: only the user can help."""
    adb.async_grant_permissions.return_value = _grant(missing=["RECORD_AUDIO"])
    display.state["voice.error"] = MIC
    await setup_entry(hass, mock_config_entry)
    await _settle()
    assert _issue(hass, mock_config_entry) is not None


@pytest.mark.parametrize("error", [AdbError("adb refused"), HomeAssistantError("other")])
async def test_grant_fails(
    hass: HomeAssistant, display: FakeDisplay, adb: MagicMock, mock_config_entry: MockConfigEntry, error: Exception
) -> None:
    """A failed grant raises the issue."""
    adb.async_grant_permissions.side_effect = error
    display.state["ble.error"] = BLE
    await setup_entry(hass, mock_config_entry)
    await _settle()
    assert _issue(hass, mock_config_entry) is not None


async def test_adb_only_permission(
    hass: HomeAssistant, display: FakeDisplay, adb: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """WRITE_SECURE_SETTINGS is only found by the ADB check; a refused grant is an issue."""
    adb.async_missing_permissions.return_value = ["WRITE_SECURE_SETTINGS", "RECORD_AUDIO"]
    adb.async_grant_permissions.return_value = _grant(missing=["WRITE_SECURE_SETTINGS"])
    await setup_entry(hass, mock_config_entry)
    await _settle()
    adb.async_grant_permissions.assert_awaited_once()
    issue = _issue(hass, mock_config_entry)
    assert issue is not None
    assert issue.translation_placeholders["problems"] == "WRITE_SECURE_SETTINGS"
    assert mock_config_entry.runtime_data.permissions.problems() == ["WRITE_SECURE_SETTINGS"]

    # the check runs at most once an hour, also across reloads
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await _settle()
    assert adb.async_missing_permissions.await_count == 1


async def test_adb_check_fails(
    hass: HomeAssistant, display: FakeDisplay, adb: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """An unreachable ADB during the check changes nothing."""
    adb.async_missing_permissions.side_effect = AdbError("timeout")
    await setup_entry(hass, mock_config_entry)
    await _settle()
    adb.async_grant_permissions.assert_not_awaited()
    assert _issue(hass, mock_config_entry) is None


async def test_grant_after_app_update(
    hass: HomeAssistant, display: FakeDisplay, adb: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """A new app version may need more: grant once it is back."""
    adb.async_grant_permissions.return_value = _grant()
    await setup_entry(hass, mock_config_entry)
    await _settle()
    guard = mock_config_entry.runtime_data.permissions

    display.client.push({"type": "_info_changed"})  # same version
    await _settle()
    adb.async_grant_permissions.assert_not_awaited()

    display.client.info.fw_version = "3.26160.0900"
    display.client.push({"type": "_info_changed"})
    await _settle()
    assert adb.async_grant_permissions.await_count == 1

    display.client.set_available(False)
    guard.async_after_update()
    await _settle()
    assert adb.async_grant_permissions.await_count == 1
    display.client.set_available(True)
    await _settle()
    assert adb.async_grant_permissions.await_count == 2
    # nothing new starts while a grant runs
    release = asyncio.Event()

    async def slow_grant() -> PermissionGrant:
        await release.wait()
        return PermissionGrant(granted=[], missing=[], failed=["perm_bt_scan"], restarted=False)

    adb.async_grant_permissions.side_effect = slow_grant
    guard._start("again")
    guard._start("again")
    display.client.push_state({"voice.error": MIC})
    display.client.push({"type": "event", "event": "swipe"})
    release.set()
    await _settle()
    assert adb.async_grant_permissions.await_count == 3
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=SETTLE_TIME + 1))
    await hass.async_block_till_done()


async def test_after_update_without_adb(
    hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay
) -> None:
    """Without ADB nothing is granted after an update."""
    init_integration.runtime_data.permissions.async_after_update()
    assert init_integration.runtime_data.permissions._task is None
