"""Constants for the Shelly Elevate integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

DOMAIN: Final = "shellyelevateintegration"
MANUFACTURER: Final = "Shelly"

CONF_TOKEN: Final = "token"
CONF_DEVICE_ID: Final = "device_id"
CONF_LEGACY: Final = "legacy"
CONF_MAC: Final = "mac"
CONF_FINGERPRINT: Final = "cert_sha256"
CONF_PANEL: Final = "panel"
"""Marks the entry that only provides the sidebar panel (no display yet)."""
PANEL_UNIQUE_ID: Final = "_panel"
"""SHA-256 of the display's TLS certificate, pinned at pairing (lowercase hex)."""
CONF_FEATURES_AUTO_ENABLED: Final = "features_auto_enabled"
"""False on a new display until media, the Bluetooth proxy and voice were turned on once.

Later user choices stand. Entries from before this flag existed are migrated to True.
"""
CONF_FEATURES_AUTO_HANDLED: Final = "features_auto_handled"
"""Feature keys already handled while CONF_FEATURES_AUTO_ENABLED is still False.

A key a profile or the installer set when the display was added counts as handled from the start.
"""
CONF_HA_LOGIN_TOKEN: Final = "ha_login_token_id"
"""Id of the Home Assistant refresh token the display logs its dashboard in with (see ha_login.py)."""
AUTO_FEATURES: Final = frozenset({"mediaEnabled", "bleScannerEnabled", "haVoiceEnabled"})
"""Settings turned on once on a newly added display (see CONF_FEATURES_AUTO_ENABLED)."""

# Options
OPT_RELAYS_AS_LIGHTS: Final = "relays_as_lights"
OPT_UPDATE_CHANNEL: Final = "update_channel"
OPT_AUTO_BACKUP: Final = "auto_backup"
OPT_BACKUP_KEEP: Final = "backup_keep"
OPT_WATCHDOG: Final = "watchdog"
OPT_ADB: Final = "adb"
OPT_HA_LOGIN: Final = "ha_login"
"""Keep the dashboard of the display logged into Home Assistant (on by default)."""
OPT_HA_LOGIN_USER: Final = "ha_login_user"
"""User the dashboard logs in as; unset uses the default of the panel."""
OPT_THERMOSTAT: Final = "thermostat"
OPT_THERMOSTAT_RELAY: Final = "thermostat_relay"
OPT_THERMOSTAT_SENSOR: Final = "thermostat_sensor"
OPT_THERMOSTAT_MODE: Final = "thermostat_mode"
OPT_THERMOSTAT_TOLERANCE: Final = "thermostat_tolerance"
OPT_THERMOSTAT_MIN_CYCLE: Final = "thermostat_min_cycle"
OPT_THERMOSTAT_MIN_TEMP: Final = "thermostat_min_temp"
OPT_THERMOSTAT_MAX_TEMP: Final = "thermostat_max_temp"

DEFAULT_THERMOSTAT_TOLERANCE: Final = 0.3
DEFAULT_THERMOSTAT_MIN_TEMP: Final = 5.0
DEFAULT_THERMOSTAT_MAX_TEMP: Final = 30.0

DEFAULT_BACKUP_KEEP: Final = 10

UPDATE_CHANNEL_STABLE: Final = "stable"
UPDATE_CHANNEL_BETA: Final = "beta"

# GitHub repository of the ShellyElevate app (releases and APKs)
APP_REPO: Final = "RapierXbox/ShellyElevate"

# Fired on the event bus for every event the display reports (buttons, swipes, ...)
EVENT_SHELLY_ELEVATE: Final = "shellyelevateintegration_event"

SIGNAL_SETTINGS_CHANGED: Final = "shellyelevateintegration_settings_changed_{}"
"""Dispatcher signal with the changed settings of one entry (format with the entry id); survives reloads."""


def is_panel_entry(entry: ConfigEntry) -> bool:
    """Whether `entry` is the panel-only entry rather than a display."""
    return bool(entry.data.get(CONF_PANEL))
