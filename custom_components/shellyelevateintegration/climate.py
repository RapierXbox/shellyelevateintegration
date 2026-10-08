"""Thermostat: a relay of the display regulated on the display's (or any other) temperature sensor.

The control loop runs in Home Assistant (like the generic thermostat). The temperature comes from
the display's own sensor unless another temperature sensor is selected in the options.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ClimateEntity,
    ClimateEntityDescription,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later, async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import (
    DEFAULT_THERMOSTAT_MAX_TEMP,
    DEFAULT_THERMOSTAT_MIN_TEMP,
    DEFAULT_THERMOSTAT_TOLERANCE,
    OPT_THERMOSTAT,
    OPT_THERMOSTAT_MAX_TEMP,
    OPT_THERMOSTAT_MIN_CYCLE,
    OPT_THERMOSTAT_MIN_TEMP,
    OPT_THERMOSTAT_MODE,
    OPT_THERMOSTAT_RELAY,
    OPT_THERMOSTAT_SENSOR,
    OPT_THERMOSTAT_TOLERANCE,
)
from .device import ShellyElevateIntegrationConfigEntry, ShellyElevateIntegrationDevice
from .entity import ShellyElevateIntegrationEntity, ShellyElevateIntegrationEntityDescription

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0
DEFAULT_TARGET = 21.0


@dataclass(frozen=True, kw_only=True)
class ShellyElevateIntegrationClimateDescription(ShellyElevateIntegrationEntityDescription, ClimateEntityDescription):
    """Climate description."""


async def async_setup_entry(
    hass: HomeAssistant, entry: ShellyElevateIntegrationConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Set up the thermostat when it is enabled in the options."""
    device = entry.runtime_data
    relays = device.info.capabilities.relays
    relay = int(entry.options.get(OPT_THERMOSTAT_RELAY, 0))
    if entry.options.get(OPT_THERMOSTAT) and relays and relay >= relays:
        _LOGGER.warning("%s: thermostat relay %s does not exist", entry.title, relay + 1)
    async_add_entities(create_entities(device))


def create_entities(device: ShellyElevateIntegrationDevice) -> list[ClimateEntity]:
    """The thermostat if it is enabled, its relay exists and it has a temperature source."""
    options = device.entry.options
    caps = device.info.capabilities
    relay = int(options.get(OPT_THERMOSTAT_RELAY, 0))
    if not options.get(OPT_THERMOSTAT) or relay >= caps.relays:
        return []
    if not options.get(OPT_THERMOSTAT_SENSOR) and not caps.temperature:
        return []
    return [ShellyElevateIntegrationThermostat(device, relay, dict(options))]


class ShellyElevateIntegrationThermostat(ShellyElevateIntegrationEntity, ClimateEntity, RestoreEntity):
    """Switches a display relay to keep the target temperature."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, device: ShellyElevateIntegrationDevice, relay: int, options: dict[str, Any]) -> None:
        """Initialize."""
        super().__init__(
            device,
            ShellyElevateIntegrationClimateDescription(
                key="thermostat",
                translation_key="thermostat",
                state_keys=("temperature", "humidity", f"relay.{relay}"),
            ),
        )
        self._relay = relay
        self._relay_key = f"relay.{relay}"
        self._sensor: str | None = options.get(OPT_THERMOSTAT_SENSOR) or None
        self._active_mode = HVACMode.COOL if options.get(OPT_THERMOSTAT_MODE) == HVACMode.COOL else HVACMode.HEAT
        self._tolerance = float(options.get(OPT_THERMOSTAT_TOLERANCE, DEFAULT_THERMOSTAT_TOLERANCE))
        self._min_cycle = timedelta(seconds=float(options.get(OPT_THERMOSTAT_MIN_CYCLE, 0)))
        self._attr_min_temp = float(options.get(OPT_THERMOSTAT_MIN_TEMP, DEFAULT_THERMOSTAT_MIN_TEMP))
        self._attr_max_temp = float(options.get(OPT_THERMOSTAT_MAX_TEMP, DEFAULT_THERMOSTAT_MAX_TEMP))
        self._attr_hvac_modes = [HVACMode.OFF, self._active_mode]
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_target_temperature = DEFAULT_TARGET
        self._external_temp: float | None = None
        self._last_switch: datetime | None = None
        self._cancel_retry: Any = None

    # ---------------------------------------------------------------- lifecycle

    async def async_added_to_hass(self) -> None:
        """Restore target/mode and follow the temperature source."""
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            if last.state in self._attr_hvac_modes:
                self._attr_hvac_mode = HVACMode(last.state)
            if (target := last.attributes.get(ATTR_TEMPERATURE)) is not None:
                self._attr_target_temperature = float(target)
        if self._sensor is not None:
            self._external_temp = self._read_sensor()
            self.async_on_remove(async_track_state_change_event(self.hass, self._sensor, self._on_sensor))
        self.async_on_remove(self._cancel_pending_retry)
        self._control()

    @callback
    def _cancel_pending_retry(self) -> None:
        if self._cancel_retry is not None:
            self._cancel_retry()
            self._cancel_retry = None

    # ---------------------------------------------------------------- state

    @property
    def current_temperature(self) -> float | None:
        """Temperature of the selected source."""
        if self._sensor is not None:
            return self._external_temp
        value = self.device.state.get("temperature")
        return None if value is None else float(value)

    @property
    def current_humidity(self) -> float | None:
        """Humidity measured by the display."""
        value = self.device.state.get("humidity")
        return None if value is None else float(value)

    @property
    def hvac_action(self) -> HVACAction:
        """What the relay is doing."""
        if self._attr_hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        if not self._relay_on:
            return HVACAction.IDLE
        return HVACAction.COOLING if self._active_mode == HVACMode.COOL else HVACAction.HEATING

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Which sensor and relay are used."""
        return {"temperature_sensor": self._sensor or "display", "relay": self._relay + 1}

    @property
    def _relay_on(self) -> bool:
        return bool(self.device.state.get(self._relay_key))

    # ---------------------------------------------------------------- inputs

    def _read_sensor(self) -> float | None:
        assert self._sensor is not None
        state = self.hass.states.get(self._sensor)
        if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return None
        try:
            value = float(state.state)
        except ValueError:
            _LOGGER.warning("%s is not a number: %s", self._sensor, state.state)
            return None
        # The loop works in °C; a °F sensor (or HA on US units) must be converted.
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        if unit not in TemperatureConverter.VALID_UNITS:
            _LOGGER.warning("%s has no temperature unit (%s); ignoring it", self._sensor, unit)
            return None
        return TemperatureConverter.convert(value, unit, UnitOfTemperature.CELSIUS)

    @callback
    def _on_sensor(self, event: Event[EventStateChangedData]) -> None:
        self._external_temp = self._read_sensor()
        self._control()
        self.async_write_ha_state()

    @callback
    def _handle_state(self, changes: dict[str, Any]) -> None:
        if not changes or "temperature" in changes or self._relay_key in changes:
            self._control()
        super()._handle_state(changes)

    # ---------------------------------------------------------------- actions

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature (and optionally the mode)."""
        if (mode := kwargs.get(ATTR_HVAC_MODE)) is not None:
            self._set_mode(HVACMode(mode))
        if (target := kwargs.get(ATTR_TEMPERATURE)) is not None:
            self._attr_target_temperature = float(target)
        self._control(force=True)
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Turn regulation on or off (off also switches the relay off)."""
        self._set_mode(hvac_mode)
        self._control(force=True)
        self.async_write_ha_state()

    @callback
    def _set_mode(self, mode: HVACMode) -> None:
        """Change the mode; turning regulation off switches the relay off once."""
        previous, self._attr_hvac_mode = self._attr_hvac_mode, mode
        # Unconditionally: the state may not show yet that our last command switched it on.
        if mode == HVACMode.OFF and previous != HVACMode.OFF and self.device.available:
            self._switch(False)

    async def async_turn_on(self) -> None:
        """Start regulating."""
        await self.async_set_hvac_mode(self._active_mode)

    async def async_turn_off(self) -> None:
        """Stop regulating."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    # ---------------------------------------------------------------- control loop

    @callback
    def _control(self, *, force: bool = False) -> None:
        """Decide whether the relay should be on and switch it if needed."""
        if not self.device.available:
            return
        if self._attr_hvac_mode == HVACMode.OFF:
            # Off means hands off: the relay stays usable as a normal switch.
            return
        temp, target = self.current_temperature, self._attr_target_temperature
        if temp is None or target is None:
            return
        if self._active_mode == HVACMode.HEAT:
            want = True if temp <= target - self._tolerance else False if temp >= target + self._tolerance else None
        else:
            want = True if temp >= target + self._tolerance else False if temp <= target - self._tolerance else None
        if want is None or want == self._relay_on:
            return
        if not force and self._last_switch is not None and self._min_cycle:
            wait = (self._last_switch + self._min_cycle - dt_util.utcnow()).total_seconds()
            if wait > 0:
                # respect the minimum cycle time, then re-evaluate
                self._cancel_pending_retry()
                self._cancel_retry = async_call_later(self.hass, wait, self._retry)
                return
        self._switch(want)

    @callback
    def _retry(self, _now: datetime) -> None:
        self._cancel_retry = None
        self._control()

    @callback
    def _switch(self, on: bool) -> None:
        self._last_switch = dt_util.utcnow()

        async def _run() -> None:
            try:
                await self.device.async_command("relay.set", index=self._relay, on=on)
            except Exception:
                _LOGGER.warning("%s: could not switch relay %s", self.device.entry.title, self._relay + 1)

        self.device.entry.async_create_background_task(self.hass, _run(), f"thermostat relay {self._relay}")
