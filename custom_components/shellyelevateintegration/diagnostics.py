"""Diagnostics."""

from __future__ import annotations

import re
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .api import ShellyElevateIntegrationError
from .const import CONF_MAC, CONF_TOKEN, is_panel_entry
from .device import ShellyElevateIntegrationConfigEntry
from .settings.schema import ALWAYS_SECRET, secret_keys

TO_REDACT = {
    CONF_TOKEN,
    CONF_HOST,
    CONF_MAC,
    "mac",
    "webviewUrl",
    "webview.url",
    "mqttBroker",
    "mqttUsername",
    *ALWAYS_SECRET,
}
LOG_LINES = 300

REDACTED = "**REDACTED**"

# order matters: urls before addresses and key value pairs inside them
_LOG_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # any url since paths and queries can carry tokens or private hosts
    (re.compile(r"\b[a-zA-Z][a-zA-Z0-9+.-]*://[^\s\"'<>]+"), REDACTED),
    (re.compile(r"(?i)\b(bearer|basic)\s+[a-z0-9._~+/=-]+"), rf"\1 {REDACTED}"),
    # json web tokens such as home assistant access tokens
    (re.compile(r"\beyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]*"), REDACTED),
    (
        re.compile(
            r"(?i)\b((?:access_|auth_|api_)?token|password|passwd|pwd|secret|api_?key|psk|ssid|client_id)"
            r"(\"?\s*[:=]\s*\"?)[^\s\",;&]+"
        ),
        rf"\1\2{REDACTED}",
    ),
    (re.compile(r"\b[0-9a-fA-F]{2}(?:[:-][0-9a-fA-F]{2}){5}\b"), REDACTED),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), REDACTED),
    (re.compile(r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b"), REDACTED),
    (re.compile(r"(?i)\bfe80::[0-9a-f:]+(?:%\w+)?"), REDACTED),
]


def redact_log_line(line: str) -> str:
    """A log line without addresses, urls, tokens and passwords."""
    for pattern, replacement in _LOG_PATTERNS:
        line = pattern.sub(replacement, line)
    return line


def _redact_log(text: str) -> list[str]:
    return [redact_log_line(line) for line in text.splitlines()[-LOG_LINES:]]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ShellyElevateIntegrationConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a display."""
    if is_panel_entry(entry):
        return {"panel": True}
    device = entry.runtime_data
    # the schema of the display marks more settings as secret than the fixed list
    to_redact = TO_REDACT | secret_keys(device.schema)
    data: dict[str, Any] = {
        "entry": {"data": async_redact_data(dict(entry.data), TO_REDACT), "options": dict(entry.options)},
        "info": async_redact_data(device.info.as_dict(), TO_REDACT),
        "available": device.available,
        "legacy": device.legacy,
        "state": async_redact_data(dict(device.state), to_redact),
        "media": {k: getattr(device.client.media, k) for k in ("state", "volume", "muted", "repeat", "announcing")},
        "settings": async_redact_data(dict(device.settings), to_redact),
        "backups": len(device.backups.list()) if device.backups else 0,
        "adb_enabled": device.adb is not None,
    }
    try:
        if (logs := await device.client.get_logs(LOG_LINES)) is not None:
            data["app_log"] = _redact_log(logs)
    except ShellyElevateIntegrationError as err:
        data["app_log_error"] = redact_log_line(str(err))
    if device.adb is not None:
        try:
            data["logcat"] = _redact_log(await device.adb.async_logcat(LOG_LINES))
        except HomeAssistantError as err:
            data["logcat_error"] = redact_log_line(str(err))
    return data
