"""Constants for the Shelly Elevate integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "shellyelevateintegration"
MANUFACTURER: Final = "Shelly"

CONF_TOKEN: Final = "token"
CONF_DEVICE_ID: Final = "device_id"
CONF_LEGACY: Final = "legacy"
CONF_MAC: Final = "mac"
CONF_FINGERPRINT: Final = "cert_sha256"
"""SHA-256 of the display's TLS certificate, pinned at pairing (lowercase hex)."""

# Options
OPT_RELAYS_AS_LIGHTS: Final = "relays_as_lights"
OPT_UPDATE_CHANNEL: Final = "update_channel"
OPT_AUTO_BACKUP: Final = "auto_backup"
OPT_BACKUP_KEEP: Final = "backup_keep"
OPT_WATCHDOG: Final = "watchdog"
OPT_ADB: Final = "adb"
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
