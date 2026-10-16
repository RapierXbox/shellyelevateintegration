"""Sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.const import (
    LIGHT_LUX,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfInformation,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .device import ShellyElevateIntegrationConfigEntry, ShellyElevateIntegrationDevice
from .entity import (
    ShellyElevateIntegrationEntity,
    ShellyElevateIntegrationEntityDescription,
    build_entities,
    has_cap,
    has_state,
)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ShellyElevateIntegrationSensorDescription(ShellyElevateIntegrationEntityDescription, SensorEntityDescription):
    """Sensor description."""

    # Computes the value; by default the value of the first state key is used.
    value_fn: Callable[[ShellyElevateIntegrationDevice], Any] | None = None
    # Extra state attributes.
    attrs_fn: Callable[[ShellyElevateIntegrationDevice], dict[str, Any]] | None = None


SENSORS: tuple[ShellyElevateIntegrationSensorDescription, ...] = (
    ShellyElevateIntegrationSensorDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        state_keys=("temperature",),
        supported_fn=has_cap("temperature"),
    ),
    ShellyElevateIntegrationSensorDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        state_keys=("humidity",),
        supported_fn=has_cap("humidity"),
    ),
    ShellyElevateIntegrationSensorDescription(
        key="lux",
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=LIGHT_LUX,
        suggested_display_precision=0,
        state_keys=("lux",),
        supported_fn=has_cap("lux"),
    ),
    ShellyElevateIntegrationSensorDescription(
        key="proximity",
        translation_key="proximity",
        state_class=SensorStateClass.MEASUREMENT,
        state_keys=("proximity",),
        entity_registry_enabled_default=False,
        supported_fn=has_cap("proximity"),
    ),
    ShellyElevateIntegrationSensorDescription(
        key="screen_brightness",
        translation_key="screen_brightness",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        state_keys=("screen.brightness",),
        value_fn=lambda d: (
            round(d.state["screen.brightness"] / 255 * 100) if d.state.get("screen.brightness") is not None else None
        ),
        supported_fn=has_state("screen.brightness"),
    ),
    ShellyElevateIntegrationSensorDescription(
        key="dimmer_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_keys=("dimmer.power",),
        supported_fn=has_cap("dimmer"),
    ),
    ShellyElevateIntegrationSensorDescription(
        key="wifi_rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        state_keys=("wifi.rssi",),
        supported_fn=has_state("wifi.rssi"),
    ),
    ShellyElevateIntegrationSensorDescription(
        key="cpu_temperature",
        translation_key="cpu_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        state_keys=("cpu.temperature",),
        supported_fn=has_state("cpu.temperature"),
    ),
    ShellyElevateIntegrationSensorDescription(
        key="memory_free",
        translation_key="memory_free",
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        state_keys=("memory.free",),
        supported_fn=has_state("memory.free"),
    ),
    ShellyElevateIntegrationSensorDescription(
        key="last_speaker",
        translation_key="last_speaker",
        state_keys=("speaker.last", "speaker.last_id", "speaker.person", "speaker.score", "speaker.at"),
        attrs_fn=lambda d: {
            "speaker_id": d.state.get("speaker.last_id"),
            "person": d.state.get("speaker.person"),
            "score": d.state.get("speaker.score"),
            "at": dt_util.utc_from_timestamp(at / 1000).isoformat()
            if isinstance(at := d.state.get("speaker.at"), int | float)
            else None,
        },
        supported_fn=lambda d: d.speaker_active,
    ),
    ShellyElevateIntegrationSensorDescription(
        key="speaker_confidence",
        translation_key="speaker_confidence",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_keys=("speaker.score",),
        value_fn=lambda d: None if d.state.get("speaker.score") is None else round(d.state["speaker.score"] * 100),
        supported_fn=lambda d: d.speaker_active,
    ),
    ShellyElevateIntegrationSensorDescription(
        key="voice_state",
        translation_key="voice_state",
        device_class=SensorDeviceClass.ENUM,
        options=["idle", "listening", "processing", "responding", "error", "disabled"],
        entity_category=EntityCategory.DIAGNOSTIC,
        state_keys=("voice.state",),
        supported_fn=lambda d: d.voice_active,
    ),
)


def create_entities(device: ShellyElevateIntegrationDevice) -> list[SensorEntity]:
    """Sensors the display should have now."""
    entities: list[SensorEntity] = build_entities(device, SENSORS, ShellyElevateIntegrationSensor)
    if has_state("uptime")(device):
        entities.append(ShellyElevateIntegrationUptimeSensor(device))
    return entities


async def async_setup_entry(
    hass: HomeAssistant, entry: ShellyElevateIntegrationConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Set up sensors."""
    async_add_entities(create_entities(entry.runtime_data))


class ShellyElevateIntegrationSensor(ShellyElevateIntegrationEntity, SensorEntity):
    """Sensor backed by display state."""

    entity_description: ShellyElevateIntegrationSensorDescription

    @property
    def native_value(self) -> Any:
        """Current value."""
        description = self.entity_description
        if description.value_fn is not None:
            return description.value_fn(self.device)
        assert description.state_keys
        return self.device.state.get(description.state_keys[0])

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Attributes of descriptions that have them."""
        attrs_fn = self.entity_description.attrs_fn
        return attrs_fn(self.device) if attrs_fn is not None else None


class ShellyElevateIntegrationUptimeSensor(ShellyElevateIntegrationEntity, SensorEntity):
    """Boot time derived from uptime (stable timestamp, no state churn)."""

    entity_description: ShellyElevateIntegrationSensorDescription

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, device: ShellyElevateIntegrationDevice) -> None:
        """Initialize."""
        super().__init__(
            device,
            ShellyElevateIntegrationSensorDescription(
                key="app_started", translation_key="app_started", state_keys=("uptime",)
            ),
        )
        self._started: datetime | None = None

    @property
    def native_value(self) -> datetime | None:
        """Start time; only moves when it shifts by more than a minute (i.e. a restart)."""
        uptime = self.device.state.get("uptime")
        if uptime is None:
            return None
        started = dt_util.utcnow() - timedelta(seconds=int(uptime))
        if self._started is None or abs((started - self._started).total_seconds()) > 60:
            self._started = started.replace(microsecond=0)
        return self._started
