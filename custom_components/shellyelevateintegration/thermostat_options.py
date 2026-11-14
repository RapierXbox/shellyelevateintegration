"""Thermostat options shared by the options flow and the panel."""

from __future__ import annotations

from typing import Any

from .const import (
    DEFAULT_THERMOSTAT_MAX_TEMP,
    DEFAULT_THERMOSTAT_MIN_TEMP,
    DEFAULT_THERMOSTAT_OVERRIDE_MINUTES,
    DEFAULT_THERMOSTAT_TOLERANCE,
    OPT_THERMOSTAT_MAX_TEMP,
    OPT_THERMOSTAT_MIN_CYCLE,
    OPT_THERMOSTAT_MIN_TEMP,
    OPT_THERMOSTAT_MODE,
    OPT_THERMOSTAT_OVERRIDE,
    OPT_THERMOSTAT_OVERRIDE_MINUTES,
    OPT_THERMOSTAT_RELAY,
    OPT_THERMOSTAT_SENSOR,
    OPT_THERMOSTAT_TOLERANCE,
    OVERRIDE_NEXT_SWITCH,
)

THERMOSTAT_DEFAULTS: dict[str, Any] = {
    OPT_THERMOSTAT_RELAY: "0",
    OPT_THERMOSTAT_MODE: "heat",
    OPT_THERMOSTAT_TOLERANCE: DEFAULT_THERMOSTAT_TOLERANCE,
    OPT_THERMOSTAT_MIN_CYCLE: 0,
    OPT_THERMOSTAT_MIN_TEMP: DEFAULT_THERMOSTAT_MIN_TEMP,
    OPT_THERMOSTAT_MAX_TEMP: DEFAULT_THERMOSTAT_MAX_TEMP,
    OPT_THERMOSTAT_OVERRIDE: OVERRIDE_NEXT_SWITCH,
    OPT_THERMOSTAT_OVERRIDE_MINUTES: DEFAULT_THERMOSTAT_OVERRIDE_MINUTES,
}


def thermostat_options_error(options: dict[str, Any], own_sensor: bool | None) -> tuple[str, str] | None:
    """(field, error key) when the thermostat options cannot work; own_sensor None = not known."""
    if float(options[OPT_THERMOSTAT_MIN_TEMP]) >= float(options[OPT_THERMOSTAT_MAX_TEMP]):
        return "base", "invalid_temp_range"
    if not options.get(OPT_THERMOSTAT_SENSOR) and own_sensor is False:
        # XL, X2i and X1i have no temperature sensor of their own
        return OPT_THERMOSTAT_SENSOR, "sensor_required"
    return None
