"""Repair issues and their fix flows."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from custom_components.shellyelevateintegration.adb.manager import PermissionGrant
from custom_components.shellyelevateintegration.api import ShellyElevateIntegrationCommandError
from custom_components.shellyelevateintegration.const import DOMAIN, OPT_ADB, OPT_UPDATE_CHANNEL
from custom_components.shellyelevateintegration.repairs import async_set_app_down

from .common import PACKAGE, FakeDisplay
from .conftest import make_adb, setup_entry

FIX = "/api/repairs/issues/fix"


@pytest.fixture
async def repairs(hass: HomeAssistant, hass_client: ClientSessionGenerator):
    """Start and continue fix flows over the HTTP API like the frontend."""
    assert await async_setup_component(hass, "repairs", {})
    client = await hass_client()

    async def start(issue_id: str) -> dict[str, Any]:
        resp = await client.post(FIX, json={"handler": DOMAIN, "issue_id": issue_id})
        assert resp.status == 200, await resp.text()
        return await resp.json()

    async def step(flow_id: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        resp = await client.post(f"{FIX}/{flow_id}", json=data or {})
        assert resp.status == 200, await resp.text()
        return await resp.json()

    return start, step


def _issue(hass: HomeAssistant, kind: str, entry: MockConfigEntry) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(DOMAIN, f"{kind}_{entry.entry_id}")


async def test_legacy_app_issue(hass: HomeAssistant, init_legacy: MockConfigEntry) -> None:
    """The legacy app gets an (unfixable) issue suggesting the update."""
    issue = _issue(hass, "legacy_app", init_legacy)
    assert issue is not None
    assert not issue.is_fixable
    assert issue.learn_more_url == "https://github.com/RapierXbox/ShellyElevate/releases"


async def test_legacy_http_fix(
    hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry, repairs
) -> None:
    """The unauthenticated HTTP API is switched off by the fix."""
    start, step = repairs
    display.settings["httpServer"] = True
    await setup_entry(hass, mock_config_entry)
    assert _issue(hass, "legacy_http_api", mock_config_entry) is not None
    result = await start(f"legacy_http_api_{mock_config_entry.entry_id}")
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {"name": mock_config_entry.title}
    result = await step(result["flow_id"])
    assert result["type"] == "create_entry"
    assert display.writes == [{"httpServer": False}]
    assert _issue(hass, "legacy_http_api", mock_config_entry) is None


async def test_duplicate_devices_fix(
    hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry, repairs
) -> None:
    """MQTT discovery and the old ESPHome proxy add second devices; the fix turns them off."""
    start, step = repairs
    display.settings |= {"mqttEnabled": True, "mqttHomeAssistantDiscovery": True, "bluetoothProxyEnabled": True}
    display.schema.append({"key": "bluetoothProxyEnabled", "type": "bool", "default": False})
    await setup_entry(hass, mock_config_entry)
    result = await start(f"duplicate_devices_{mock_config_entry.entry_id}")
    result = await step(result["flow_id"])
    assert result["type"] == "create_entry"
    assert display.writes == [
        {"mqttHomeAssistantDiscovery": False, "bluetoothProxyEnabled": False, "bleScannerEnabled": True}
    ]
    assert _issue(hass, "duplicate_devices", mock_config_entry) is None


async def test_issue_rechecked_on_settings_change(
    hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay
) -> None:
    """A change on the display itself raises or clears the issues."""
    display.client.push({"type": "settings_changed", "changes": {"httpServer": True}})
    await hass.async_block_till_done()
    assert _issue(hass, "legacy_http_api", init_integration) is not None
    display.client.push({"type": "settings_changed", "changes": {"httpServer": False}})
    await hass.async_block_till_done()
    assert _issue(hass, "legacy_http_api", init_integration) is None


async def test_fix_fails(
    hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry, repairs
) -> None:
    """A display that does not take the fix aborts the flow."""
    start, step = repairs
    display.settings["httpServer"] = True
    await setup_entry(hass, mock_config_entry)
    display.set_settings_error = ShellyElevateIntegrationCommandError("refused")
    result = await start(f"legacy_http_api_{mock_config_entry.entry_id}")
    result = await step(result["flow_id"])
    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"


@pytest.mark.parametrize(
    ("reinstall", "method"),
    [(False, "async_restart_app"), (True, "async_install_app")],
)
async def test_app_down_fix(
    hass: HomeAssistant,
    display: FakeDisplay,
    adb: MagicMock,
    mock_config_entry: MockConfigEntry,
    repairs,
    reinstall: bool,
    method: str,
) -> None:
    """The app does not answer but ADB does: restart or reinstall it."""
    start, step = repairs
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, options={OPT_UPDATE_CHANNEL: "beta"})
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    async_set_app_down(hass, mock_config_entry.runtime_data, True)
    issue = _issue(hass, "app_unreachable", mock_config_entry)
    assert issue.severity is ir.IssueSeverity.ERROR
    result = await start(f"app_unreachable_{mock_config_entry.entry_id}")
    assert result["step_id"] == "confirm"
    result = await step(result["flow_id"], {"reinstall": reinstall})
    assert result["type"] == "create_entry"
    getattr(adb, method).assert_awaited_once()
    if reinstall:
        assert adb.async_install_app.await_args.kwargs == {"channel": "beta"}


async def test_app_down_without_adb(hass: HomeAssistant, init_integration: MockConfigEntry, repairs) -> None:
    """Without ADB there is nothing the fix can do."""
    start, step = repairs
    async_set_app_down(hass, init_integration.runtime_data, True)
    result = await start(f"app_unreachable_{init_integration.entry_id}")
    result = await step(result["flow_id"], {"reinstall": False})
    assert result["type"] == "abort"
    assert result["reason"] == "no_adb"


async def test_fix_for_unloaded_display(
    hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay, repairs
) -> None:
    """Fix flows of an unloaded display abort."""
    start, _step = repairs
    display.client.push({"type": "settings_changed", "changes": {"httpServer": True}})
    display.client.push_state({"voice.error": "microphone permission missing"})
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(init_integration.entry_id)
    for kind in ("legacy_http_api", "permissions_missing"):
        result = await start(f"{kind}_{init_integration.entry_id}")
        assert result["type"] == "abort"
        assert result["reason"] == "not_loaded"


# --------------------------------------------------------------------------- permissions


@pytest.fixture
async def mic_missing(hass: HomeAssistant, display: FakeDisplay) -> FakeDisplay:
    """The display reports the microphone permission missing."""
    display.state["voice.error"] = "microphone permission missing"
    return display


async def test_permissions_fix_with_adb(
    hass: HomeAssistant, mic_missing: FakeDisplay, adb: MagicMock, mock_config_entry: MockConfigEntry, repairs
) -> None:
    """With ADB the fix grants the permissions."""
    start, step = repairs
    adb.async_grant_permissions.return_value = PermissionGrant(
        granted=[], missing=["RECORD_AUDIO"], failed=[], restarted=False
    )
    await setup_entry(hass, mock_config_entry)
    assert _issue(hass, "permissions_missing", mock_config_entry) is not None

    result = await start(f"permissions_missing_{mock_config_entry.entry_id}")
    assert result["step_id"] == "permissions"
    assert result["description_placeholders"]["problems"] == "microphone permission missing"
    result = await step(result["flow_id"])
    assert result["type"] == "abort"
    assert result["reason"] == "still_missing"

    adb.async_grant_permissions.side_effect = HomeAssistantError("adb gone")
    result = await start(f"permissions_missing_{mock_config_entry.entry_id}")
    result = await step(result["flow_id"])
    assert result["reason"] == "cannot_connect"

    adb.async_grant_permissions.side_effect = None
    adb.async_grant_permissions.return_value = PermissionGrant(
        granted=["RECORD_AUDIO"], missing=[], failed=[], restarted=True
    )
    result = await start(f"permissions_missing_{mock_config_entry.entry_id}")
    result = await step(result["flow_id"])
    assert result["type"] == "create_entry"
    assert _issue(hass, "permissions_missing", mock_config_entry) is None


async def test_permissions_fix_enables_adb(
    hass: HomeAssistant, mic_missing: FakeDisplay, mock_config_entry: MockConfigEntry, repairs
) -> None:
    """Without ADB the fix explains how to turn it on and then uses it."""
    start, step = repairs
    await setup_entry(hass, mock_config_entry)
    probe = make_adb()
    probe.async_is_reachable = AsyncMock(return_value=False)
    with patch(f"{PACKAGE}.adb.manager.async_create_adb_manager", AsyncMock(return_value=probe)):
        result = await start(f"permissions_missing_{mock_config_entry.entry_id}")
        assert result["step_id"] == "enable_adb"
        assert result["description_placeholders"]["host"] == "192.168.1.50"
        result = await step(result["flow_id"])
    assert result["type"] == "abort"
    assert result["reason"] == "adb_unreachable"

    adb = make_adb()
    adb.async_grant_permissions.return_value = PermissionGrant(
        granted=["RECORD_AUDIO"], missing=[], failed=[], restarted=True
    )
    probe.async_is_reachable = AsyncMock(return_value=True)
    with (
        patch(f"{PACKAGE}.adb.manager.async_create_adb_manager", AsyncMock(return_value=probe)),
        patch(f"{PACKAGE}.adb.manager.async_get_adb_manager", AsyncMock(return_value=adb)),
    ):
        result = await start(f"permissions_missing_{mock_config_entry.entry_id}")
        result = await step(result["flow_id"])
        assert result["type"] == "create_entry"
        await hass.async_block_till_done()
    assert mock_config_entry.options[OPT_ADB] is True
    adb.async_grant_permissions.assert_awaited()


async def test_permissions_fix_adb_turned_on_meanwhile(
    hass: HomeAssistant, mic_missing: FakeDisplay, mock_config_entry: MockConfigEntry, repairs
) -> None:
    """ADB enabled while the explanation was shown: the grant runs right away."""
    start, step = repairs
    await setup_entry(hass, mock_config_entry)
    result = await start(f"permissions_missing_{mock_config_entry.entry_id}")
    assert result["step_id"] == "enable_adb"
    adb = make_adb()
    mock_config_entry.runtime_data.adb = adb
    with patch(f"{PACKAGE}.adb.manager.async_create_adb_manager", AsyncMock(return_value=adb)):
        result = await step(result["flow_id"])
    assert result["type"] == "create_entry"


async def test_permissions_fix_without_guard(
    hass: HomeAssistant, mic_missing: FakeDisplay, adb: MagicMock, mock_config_entry: MockConfigEntry, repairs
) -> None:
    """A display without the permission guard cannot be fixed."""
    start, step = repairs
    adb.async_grant_permissions.return_value = PermissionGrant(
        granted=[], missing=["RECORD_AUDIO"], failed=[], restarted=False
    )
    await setup_entry(hass, mock_config_entry)
    mock_config_entry.runtime_data.permissions = None
    result = await start(f"permissions_missing_{mock_config_entry.entry_id}")
    assert result["description_placeholders"]["problems"] == "microphone permission missing"
    result = await step(result["flow_id"])
    assert result["reason"] == "not_loaded"


async def test_enable_adb_step_for_unloaded_display(
    hass: HomeAssistant, mic_missing: FakeDisplay, mock_config_entry: MockConfigEntry, repairs
) -> None:
    """The display was unloaded while the explanation was shown."""
    start, step = repairs
    await setup_entry(hass, mock_config_entry)
    result = await start(f"permissions_missing_{mock_config_entry.entry_id}")
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    result = await step(result["flow_id"])
    assert result["reason"] == "not_loaded"
