"""Diagnostics."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from custom_components.shellyelevateintegration.api import ShellyElevateIntegrationConnectionError
from custom_components.shellyelevateintegration.diagnostics import (
    REDACTED,
    async_get_config_entry_diagnostics,
    redact_log_line,
)

from .common import FakeDisplay
from .conftest import setup_entry
from .const import FINGERPRINT, HOST, MAC, TOKEN

APP_LOG = "\n".join(
    [
        f"I/Api: client connected from {HOST}",
        "D/WebView: loading http://homeassistant.local:8123/lovelace/0?auth_callback=1&code=abc",
        "D/Mqtt: password=hunter2 user=display",
        'D/Json: {"token": "secret-token-value"}',
        "D/Http: Authorization: Bearer abc.def.ghi",
        "D/Ha: eyJhbGciOiJIUzI1NiJ9.eyJpc3MiOiIxMjMifQ.c2lnbmF0dXJl",
        f"D/Ble: scan from {MAC}",
        "D/Net: 2001:0db8:0000:0000:0000:ff00:0042:8329 and fe80::1c2b:3cff:fe4d:5e6f%wlan0",
        "I/App: started",
    ]
)


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    display: FakeDisplay,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Secrets, addresses and the token never end up in diagnostics."""
    display.logs = APP_LOG
    await setup_entry(hass, mock_config_entry)
    data = await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
    entry_data = data["entry"]["data"]
    assert entry_data["token"] == REDACTED
    assert entry_data["host"] == REDACTED
    assert entry_data["mac"] == REDACTED
    assert entry_data["cert_sha256"] == FINGERPRINT
    assert data["info"]["mac"] == REDACTED
    assert data["info"]["capabilities"]["relays"] == 2
    assert data["available"] is True
    assert data["legacy"] is False
    assert data["state"]["webview.url"] == REDACTED
    assert data["state"]["temperature"] == 21.4
    settings = data["settings"]
    for key in ("mqttPassword", "mqttBroker", "mqttUsername", "webviewUrl"):
        assert settings[key] == REDACTED, key
    assert settings["screenSaverDelay"] == 45
    assert data["media"]["state"] == "idle"
    assert data["backups"] == 1
    assert data["adb_enabled"] is False
    log = "\n".join(data["app_log"])
    for secret in (
        HOST,
        "homeassistant.local",
        "hunter2",
        "secret-token-value",
        "abc.def.ghi",
        "eyJhbGci",
        MAC,
        "2001:0db8",
        "fe80::1c2b",
    ):
        assert secret not in log, secret
    assert "I/App: started" in log
    assert TOKEN not in str(data)


async def test_diagnostics_schema_secrets(
    hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry
) -> None:
    """Settings the display marks as secret are redacted too."""
    display.settings["haToken"] = "abc"
    display.schema.append({"key": "haToken", "type": "string", "secret": True})
    await setup_entry(hass, mock_config_entry)
    data = await async_get_config_entry_diagnostics(hass, mock_config_entry)
    assert data["settings"]["haToken"] == REDACTED


async def test_diagnostics_log_errors(
    hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry
) -> None:
    """Unreadable logs are reported (without addresses); logcat comes over ADB."""
    display.logs_error = ShellyElevateIntegrationConnectionError(f"GET /api/v1/logs failed on {HOST}")
    await setup_entry(hass, mock_config_entry)
    device = mock_config_entry.runtime_data
    device.adb = MagicMock()
    device.adb.async_logcat = MagicMock(side_effect=HomeAssistantError(f"cannot connect to {HOST}:5555"))
    data = await async_get_config_entry_diagnostics(hass, mock_config_entry)
    assert HOST not in data["app_log_error"]
    assert HOST not in data["logcat_error"]
    assert data["adb_enabled"] is True


async def test_diagnostics_logcat(
    hass: HomeAssistant, display: FakeDisplay, adb: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Logcat lines are redacted like the app log; an app without logs has none."""
    display.logs = None
    await setup_entry(hass, mock_config_entry)
    data = await async_get_config_entry_diagnostics(hass, mock_config_entry)
    assert "app_log" not in data
    assert data["logcat"] == [f"I/ActivityManager: Start proc 1234 for {REDACTED}"]


async def test_panel_diagnostics(hass: HomeAssistant, panel_entry: MockConfigEntry) -> None:
    """The panel entry has nothing to report."""
    await setup_entry(hass, panel_entry)
    assert await async_get_config_entry_diagnostics(hass, panel_entry) == {"panel": True}


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("token=abc123 next", f"token={REDACTED} next"),
        ('"api_key": "k-1"', f'"api_key": "{REDACTED}"'),
        ("Basic dXNlcjpwYXNz", f"Basic {REDACTED}"),
        ("ssid=MyWifi;", f"ssid={REDACTED};"),
        ("nothing to hide", "nothing to hide"),
    ],
)
def test_redact_log_line(line: str, expected: str) -> None:
    """Key value pairs and auth headers are redacted."""
    assert redact_log_line(line) == expected
