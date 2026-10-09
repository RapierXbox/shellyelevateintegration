"""Revert a display to stock."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.shellyelevateintegration.adb.baseline import async_get_baseline_store
from custom_components.shellyelevateintegration.adb.manager import AdbError
from custom_components.shellyelevateintegration.adb.steps import Platform, parse_revert_check
from custom_components.shellyelevateintegration.api import ShellyElevateIntegrationCommandError
from custom_components.shellyelevateintegration.const import DOMAIN
from custom_components.shellyelevateintegration.revert import (
    RevertOptions,
    async_revert,
    async_revert_check,
    entry_for_host,
)

from .common import FakeDisplay
from .conftest import entry_data
from .const import HOST

REVERT = "custom_components.shellyelevateintegration.revert"
INSTALLED = parse_revert_check(
    "app=package:/data/app/x\nstock=package:/system/app/Stargate.apk\nstock_disabled=1\n"
    "stock_state=enabled=2\npriv_app=/system/priv-app/ShellyElevateV2\nwifi_by_app=1\n"
)
CLEAN = parse_revert_check("app=\nstock=package:/system/app/Stargate.apk\n")
ROOTED = Platform(sdk=30, serial="SER1", model="SAWD", root=True)
UNROOTED = Platform(sdk=27, serial="SER1", model="SAWD", root=False)


@pytest.fixture
def adb() -> Generator[MagicMock]:
    """ADB of a display running ShellyElevate."""
    manager = MagicMock()
    manager.async_revert_check = AsyncMock(side_effect=[(UNROOTED, INSTALLED), (UNROOTED, CLEAN)])
    manager.async_run_steps = AsyncMock(return_value={})
    manager.async_reboot = AsyncMock()
    manager.async_disable_adb = AsyncMock()
    with patch(f"{REVERT}.async_create_adb_manager", AsyncMock(return_value=manager)):
        yield manager


def _recorder() -> tuple[list[tuple[str, dict[str, Any]]], Any]:
    events: list[tuple[str, dict[str, Any]]] = []
    return events, lambda step, data: events.append((step, data))


async def test_check(hass: HomeAssistant, init_integration: MockConfigEntry, adb: MagicMock) -> None:
    """The check lists what a revert finds and warns about it."""
    result = await async_revert_check(hass, HOST)
    assert result["platform"] == {"sdk": 27, "model": "SAWD", "root": False}
    assert result["check"]["app_installed"] is True
    assert result["warnings"] == ["wifi_by_app", "stock_needs_root", "system_copy_needs_root", "no_baseline"]
    assert result["entry_id"] == init_integration.entry_id
    assert result["name"] == init_integration.title


async def test_check_unknown_host(hass: HomeAssistant, adb: MagicMock) -> None:
    """A host without an entry; stock values known; no stock app."""
    await (await async_get_baseline_store(hass)).async_capture("SER1", {"home": "x"})
    adb.async_revert_check.side_effect = [(ROOTED, parse_revert_check("app=package:/x\n"))]
    result = await async_revert_check(hass, "10.0.0.9")
    assert result["warnings"] == ["stock_missing"]
    assert result["entry_id"] is None


async def test_revert(
    hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay, adb: MagicMock
) -> None:
    """Revert, verify, remove the entry and reboot."""
    display.settings["mqttHomeAssistantDiscovery"] = True
    display.client.settings["mqttHomeAssistantDiscovery"] = True
    await (await async_get_baseline_store(hass)).async_capture("SER1", {"screen_brightness": "90"})
    events, progress = _recorder()
    result = await async_revert(hass, RevertOptions(host=HOST, accept_wifi_loss=True), progress)
    await hass.async_block_till_done()
    assert result == {
        "remaining": [],
        "entry_removed": True,
        "adb_disabled": False,
        "warnings": ["wifi_by_app", "stock_needs_root", "system_copy_needs_root"],
    }
    assert display.writes == [{"mqttHomeAssistantDiscovery": False}]
    commands = dict(adb.async_run_steps.await_args.args[0])
    assert commands["brightness"].endswith("90")
    assert (await async_get_baseline_store(hass)).get("SER1") is None
    assert hass.config_entries.async_get_entry(init_integration.entry_id) is None
    adb.async_reboot.assert_awaited_once()
    statuses = {step: data["status"] for step, data in events}
    assert statuses["mqtt_cleanup"] == "done"
    assert statuses["verify"] == "done"
    assert statuses["reboot"] == "done"


async def test_revert_refuses_wifi_loss(hass: HomeAssistant, adb: MagicMock) -> None:
    """Uninstalling deletes the app's Wi-Fi networks: only when accepted."""
    with pytest.raises(HomeAssistantError) as err:
        await async_revert(hass, RevertOptions(host=HOST), lambda *_: None)
    assert err.value.translation_key == "revert_wifi_by_app"


async def test_revert_adb_unreachable(hass: HomeAssistant, adb: MagicMock) -> None:
    """Without ADB nothing is changed."""
    adb.async_revert_check.side_effect = AdbError("refused")
    events, progress = _recorder()
    with pytest.raises(AdbError):
        await async_revert(hass, RevertOptions(host=HOST), progress)
    assert ("adb_connect", {"status": "failed", "error": "refused"}) in events


async def test_revert_partial(
    hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay, adb: MagicMock
) -> None:
    """What is left is reported; the entry stays while the app is installed; ADB can be turned off."""
    display.client.settings["mqttHomeAssistantDiscovery"] = True
    display.set_settings_error = ShellyElevateIntegrationCommandError("busy")
    adb.async_revert_check.side_effect = [(ROOTED, CLEAN), (ROOTED, INSTALLED)]
    events, progress = _recorder()
    result = await async_revert(hass, RevertOptions(host=HOST, disable_adb=True), progress)
    assert result["remaining"] == ["app", "system_copy", "stock_disabled"]
    assert result["entry_removed"] is False
    assert result["adb_disabled"] is True
    adb.async_disable_adb.assert_awaited_once_with(True, progress)
    adb.async_reboot.assert_not_awaited()
    statuses = {step: data["status"] for step, data in events}
    assert statuses["mqtt_cleanup"] == "failed"
    assert statuses["verify"] == "failed"
    assert hass.config_entries.async_get_entry(init_integration.entry_id) is not None


async def test_revert_without_reboot(hass: HomeAssistant, adb: MagicMock) -> None:
    """No reboot when not asked; a failed reboot is only reported."""
    adb.async_revert_check.side_effect = [(UNROOTED, CLEAN), (UNROOTED, CLEAN)]
    await async_revert(hass, RevertOptions(host=HOST, reboot=False), lambda *_: None)
    adb.async_reboot.assert_not_awaited()
    adb.async_revert_check.side_effect = [(UNROOTED, CLEAN), (UNROOTED, CLEAN)]
    adb.async_reboot.side_effect = AdbError("gone")
    events, progress = _recorder()
    await async_revert(hass, RevertOptions(host=HOST), progress)
    assert events[-1] == ("reboot", {"status": "failed", "error": "gone"})


async def test_entry_for_host(hass: HomeAssistant) -> None:
    """Only an unambiguous host finds its entry."""
    for unique_id in ("a", "b"):
        MockConfigEntry(domain=DOMAIN, unique_id=unique_id, data=entry_data()).add_to_hass(hass)
    assert entry_for_host(hass, HOST) is None
    assert entry_for_host(hass, "10.9.9.9") is None
