"""Websocket API of the panel."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.shellyelevateintegration.api import ShellyElevateIntegrationCommandError
from custom_components.shellyelevateintegration.const import DOMAIN
from custom_components.shellyelevateintegration.settings.profiles import async_get_profile_manager

from .common import FakeDisplay
from .conftest import setup_entry
from .const import DEVICE_ID, HOST, OTHER_DEVICE_ID

WS = "custom_components.shellyelevateintegration.websocket"


@pytest.fixture
async def ws(hass: HomeAssistant, hass_ws_client: WebSocketGenerator):
    """Send a command and return its result (or error)."""
    client = await hass_ws_client(hass)

    async def send(command: str, **data: Any) -> dict[str, Any]:
        await client.send_json_auto_id({"type": f"{DOMAIN}/{command}", **data})
        return await client.receive_json()

    send.client = client  # type: ignore[attr-defined]
    return send


async def test_devices(
    hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay, ws, panel_entry: MockConfigEntry
) -> None:
    """Loaded and not loaded displays are listed, the panel entry is not."""
    panel_entry.add_to_hass(hass)
    broken = MockConfigEntry(domain=DOMAIN, unique_id="broken", title="Broken", data={"host": "10.0.0.9"})
    broken.add_to_hass(hass)
    result = await ws("devices")
    assert result["success"]
    devices = result["result"]["devices"]
    assert devices[0]["display_id"] == DEVICE_ID
    assert devices[0]["model"] == "Wall Display X2"
    assert devices[0]["host"] == HOST
    assert devices[0]["capabilities"]["relays"] == 2
    assert devices[1] == {"entry_id": broken.entry_id, "name": "Broken", "available": False, "state": "not_loaded"}


async def test_settings_get(hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay, ws) -> None:
    """Settings with the schema of the display, undescribed keys and the keys this integration manages."""
    display.settings["customKey"] = [1, 2]
    display.settings["bluetoothProxyEnabled"] = False
    result = (await ws("settings/get", entry_id=init_integration.entry_id))["result"]
    assert result["settings"]["screenSaverDelay"] == 45
    keys = {item["key"] for item in result["schema"]}
    assert "screenSaverDelay" in keys
    assert {"key": "customKey", "type": "string_list", "category": "other", "label": "customKey"} in result["schema"]
    assert "bluetoothProxyEnabled" not in keys
    assert "mqttPassword" in result["secret"]
    assert "mqttDeviceId" in result["per_device"]
    assert result["legacy"] is False
    assert "microphone" in result["known_caps"]
    assert result["managed"] == {
        "integrationApiEnabled": "Turning it off disconnects this display from Home Assistant",
        "voiceWakeEnabled": "Set by the wake word of the Assist satellite in Home Assistant",
        "voiceWakeModelName": "Set by the wake word of the Assist satellite in Home Assistant",
    }


async def test_settings_get_without_schema(
    hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry, ws
) -> None:
    """Without the schema the rules of the app are used; values of any type are listed."""
    display.schema_error = ShellyElevateIntegrationCommandError("unsupported")
    display.settings |= {"anInt": 1, "aFloat": 1.5, "aBool": True, "aString": "x"}
    await setup_entry(hass, mock_config_entry)
    result = (await ws("settings/get", entry_id=mock_config_entry.entry_id))["result"]
    types = {item["key"]: item["type"] for item in result["schema"]}
    assert types["screenSaverDelay"] == "int"
    assert (types["anInt"], types["aFloat"], types["aBool"], types["aString"]) == ("int", "float", "bool", "string")


async def test_settings_get_legacy(hass: HomeAssistant, init_legacy: MockConfigEntry, ws) -> None:
    """Legacy displays compare values loosely and keep their MQTT id."""
    result = (await ws("settings/get", entry_id=init_legacy.entry_id))["result"]
    assert result["legacy"] is True
    assert set(result["managed"]) == {"mqttDeviceId", "httpServer"}


async def test_settings_set_and_subscribe(
    hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay, ws
) -> None:
    """Writes report ignored keys; subscribers see every change."""
    sub = await ws("settings/subscribe", entry_id=init_integration.entry_id)
    assert sub["success"]
    await ws.client.send_json_auto_id(
        {
            "type": f"{DOMAIN}/settings/set",
            "entry_id": init_integration.entry_id,
            "changes": {"screenSaverDelay": 60, "nope": 1},
        }
    )
    messages = [await ws.client.receive_json() for _ in range(2)]
    result = next(msg for msg in messages if msg["type"] == "result")
    event = next(msg for msg in messages if msg["type"] == "event")
    assert result["result"]["ignored"] == ["nope"]
    assert event["event"] == {"changes": {"screenSaverDelay": 60}}

    display.client.push({"type": "settings_changed", "changes": {"touchToWake": False}})
    event = await ws.client.receive_json()
    assert event["event"] == {"changes": {"touchToWake": False}}
    display.client.push({"type": "settings_changed", "changes": {}})
    await hass.async_block_till_done()

    result = await ws("settings/subscribe", entry_id="nope")
    assert result["error"]["code"] == "not_found"


async def test_not_loaded(hass: HomeAssistant, init_integration: MockConfigEntry, ws) -> None:
    """Commands for unknown or unloaded displays fail."""
    result = await ws("settings/get", entry_id="nope")
    assert result["error"]["code"] == "failed"
    assert await hass.config_entries.async_unload(init_integration.entry_id)
    result = await ws("settings/set", entry_id=init_integration.entry_id, changes={})
    assert not result["success"]


async def test_export_and_copy(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    display: FakeDisplay,
    second_display: tuple[FakeDisplay, MockConfigEntry],
    ws,
) -> None:
    """Export and copy between displays."""
    other, other_entry = second_display
    result = (await ws("settings/export", entry_id=init_integration.entry_id))["result"]
    assert "mqttPassword" not in result["settings"]
    result = (
        await ws(
            "settings/copy", source=init_integration.entry_id, targets=[other_entry.entry_id], keys=["screenSaverDelay"]
        )
    )["result"]
    assert result["errors"] == {}
    assert other.writes == [{"screenSaverDelay": 45}]


async def test_command(hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay, ws) -> None:
    """Fleet commands report per display."""
    display.command_results["screen.wake"] = {"woke": True}
    result = (await ws("command", entry_ids=[init_integration.entry_id, "nope"], action="screen.wake"))["result"]
    assert result["results"][init_integration.entry_id] == {"ok": True, "data": {"woke": True}}
    assert result["results"]["nope"]["ok"] is False


async def test_backups(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    display: FakeDisplay,
    second_display: tuple[FakeDisplay, MockConfigEntry],
    ws,
) -> None:
    """List, create, compare, restore (also from another display) and delete backups."""
    entry_id = init_integration.entry_id
    created = (await ws("backups/create", entry_id=entry_id, name="Mine"))["result"]["backup"]
    assert created["name"] == "Mine"
    listed = (await ws("backups/list", entry_id=entry_id))["result"]["backups"]
    assert listed[DEVICE_ID][0]["id"] == created["id"]
    everything = (await ws("backups/list"))["result"]["backups"]
    assert set(everything) == {DEVICE_ID, OTHER_DEVICE_ID}

    display.settings["screenSaverDelay"] = 10
    diff = (await ws("backups/diff", entry_id=entry_id, backup_id=created["id"]))["result"]["diff"]
    assert diff == [{"key": "screenSaverDelay", "current": 10, "new": 45}]
    other_diff = (await ws("backups/diff", entry_id=entry_id, source_device_id=OTHER_DEVICE_ID))["result"]["diff"]
    assert {"key": "screenSaverDelay", "current": 10, "new": 300} in other_diff
    assert all(item["key"] != "mqttDeviceId" for item in other_diff)

    changes = (await ws("backups/restore", entry_id=entry_id, backup_id=created["id"]))["result"]["changes"]
    assert changes == [{"key": "screenSaverDelay", "current": 10, "new": 45}]
    changes = (
        await ws("backups/restore", entry_id=entry_id, source_device_id=OTHER_DEVICE_ID, keys=["screenSaverDelay"])
    )["result"]["changes"]
    assert changes == [{"key": "screenSaverDelay", "current": 45, "new": 300}]

    assert (await ws("backups/delete", device_id=DEVICE_ID, backup_id=created["id"]))["success"]
    result = await ws("backups/delete", device_id=DEVICE_ID, backup_id=created["id"])
    assert result["error"]["code"] == "failed"


async def test_profiles(hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay, ws) -> None:
    """Profiles: save, list, default, apply (dry run) and delete."""
    entry_id = init_integration.entry_id
    saved = (await ws("profiles/save", name="Hall", settings={"screenSaverDelay": 90}))["result"]["profile_id"]
    from_display = (
        await ws("profiles/save", name="Copy", from_entry_id=entry_id, keys=["touchToWake"], make_default=False)
    )["result"]["profile_id"]
    manager = await async_get_profile_manager(hass)
    assert manager.profiles[from_display]["settings"] == {"touchToWake": True}
    listed = (await ws("profiles/list"))["result"]
    assert [p["name"] for p in listed["profiles"]] == ["Copy", "Hall"]
    assert listed["default"] == saved

    assert (await ws("profiles/set_default", profile_id=from_display))["success"]
    assert manager.default_profile_id == from_display
    assert (await ws("profiles/set_default", profile_id=None))["success"]
    assert manager.default_profile_id is None

    dry = (await ws("profiles/apply", profile_id=saved, entry_ids=[entry_id, "nope"], dry_run=True))["result"]
    assert dry["results"][entry_id] == [{"key": "screenSaverDelay", "current": 45, "new": 90}]
    assert "nope" in dry["errors"]
    assert display.writes == []
    applied = (await ws("profiles/apply", profile_id=saved, entry_ids=[entry_id]))["result"]
    assert applied["results"][entry_id] == [{"key": "screenSaverDelay", "current": 45, "new": 90}]
    assert display.writes == [{"screenSaverDelay": 90}]
    assert (await ws("profiles/apply", profile_id="nope", entry_ids=[entry_id]))["error"]["code"] == "failed"

    assert (await ws("profiles/delete", profile_id=saved))["success"]
    assert (await ws("profiles/delete", profile_id=saved))["error"]["code"] == "failed"


async def test_installer_info(hass: HomeAssistant, ws) -> None:
    """The install wizard gets releases, profiles and the dashboard URL."""
    assert await async_setup_component(hass, DOMAIN, {})
    result = (await ws("installer/info"))["result"]
    assert [r["version"] for r in result["releases"]] == ["3.26170.1000", "3.26160.0900"]
    assert result["profiles"] == []
    assert result["dashboard_url"] == "http://10.10.10.10:8123"
    with patch(f"{WS}.async_get_releases", side_effect=HomeAssistantError):
        assert (await ws("installer/info"))["result"]["releases"] == []


async def _subscribe(ws, command: str, events: int, **data: Any) -> list[dict[str, Any]]:
    """Start a subscription; returns its events (the result may come before or after them)."""
    await ws.client.send_json_auto_id({"type": f"{DOMAIN}/{command}", **data})
    messages = [await ws.client.receive_json() for _ in range(events + 1)]
    assert [msg["success"] for msg in messages if msg["type"] == "result"] == [True]
    return [msg["event"] for msg in messages if msg["type"] == "event"]


async def test_provision(hass: HomeAssistant, init_integration: MockConfigEntry, ws) -> None:
    """Provisioning streams its progress."""

    async def provision(hass: HomeAssistant, options: Any, progress: Any) -> dict[str, Any]:
        assert options.host == "10.0.0.5"
        assert options.channel == "beta"
        progress("adb_connect", {"status": "done"})
        return {"entry_id": "x"}

    with patch(f"{WS}.async_provision", provision):
        assert await _subscribe(ws, "installer/provision", 2, host="10.0.0.5", channel="beta") == [
            {"type": "step", "step": "adb_connect", "status": "done"},
            {"type": "done", "entry_id": "x"},
        ]
    with patch(f"{WS}.async_provision", AsyncMock(side_effect=RuntimeError("adb refused"))):
        assert await _subscribe(ws, "installer/provision", 1, host="10.0.0.5") == [
            {"type": "error", "error": "adb refused"}
        ]


async def test_revert(hass: HomeAssistant, init_integration: MockConfigEntry, ws) -> None:
    """Check and run a revert."""
    with patch(f"{WS}.async_revert_check", AsyncMock(return_value={"warnings": []})):
        assert (await ws("revert/check", host=HOST))["result"] == {"warnings": []}

    async def revert(hass: HomeAssistant, options: Any, progress: Any) -> dict[str, Any]:
        assert options.remove_wiki_launcher is False
        progress("stop_app", {"status": "done"})
        return {"remaining": []}

    with patch(f"{WS}.async_revert", revert):
        assert await _subscribe(ws, "revert/run", 2, host=HOST, remove_wiki_launcher=False) == [
            {"type": "step", "step": "stop_app", "status": "done"},
            {"type": "done", "remaining": []},
        ]
    with patch(f"{WS}.async_revert", AsyncMock(side_effect=RuntimeError("gone"))):
        assert await _subscribe(ws, "revert/run", 1, host=HOST) == [{"type": "error", "error": "gone"}]
    await asyncio.sleep(0)
