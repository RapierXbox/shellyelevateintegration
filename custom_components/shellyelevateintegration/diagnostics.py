"""Diagnostics."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .api import ShellyElevateIntegrationError
from .const import CONF_MAC, CONF_TOKEN
from .device import ShellyElevateIntegrationConfigEntry
from .settings.schema import ALWAYS_SECRET

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


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ShellyElevateIntegrationConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a display."""
    device = entry.runtime_data
    data: dict[str, Any] = {
        "entry": {"data": async_redact_data(dict(entry.data), TO_REDACT), "options": dict(entry.options)},
        "info": async_redact_data(device.info.as_dict(), TO_REDACT),
        "available": device.available,
        "legacy": device.legacy,
        "state": async_redact_data(dict(device.state), TO_REDACT),
        "media": {k: getattr(device.client.media, k) for k in ("state", "volume", "muted", "repeat", "announcing")},
        "settings": async_redact_data(dict(device.settings), TO_REDACT),
        "backups": len(device.backups.list()) if device.backups else 0,
        "adb_enabled": device.adb is not None,
    }
    try:
        if (logs := await device.client.get_logs(LOG_LINES)) is not None:
            data["app_log"] = logs.splitlines()[-LOG_LINES:]
    except ShellyElevateIntegrationError as err:
        data["app_log_error"] = str(err)
    if device.adb is not None:
        try:
            data["logcat"] = (await device.adb.async_logcat(LOG_LINES)).splitlines()
        except HomeAssistantError as err:
            data["logcat_error"] = str(err)
    return data
