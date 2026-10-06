"""Binary sensors."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .device import ShellyElevateIntegrationConfigEntry, ShellyElevateIntegrationDevice
from .entity import (
    ShellyElevateIntegrationEntity,
    ShellyElevateIntegrationEntityDescription,
    build_entities,
    has_state,
    indexed_name,
)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ShellyElevateIntegrationBinarySensorDescription(
    ShellyElevateIntegrationEntityDescription, BinarySensorEntityDescription
):
    """Binary sensor description."""


BINARY_SENSORS: tuple[ShellyElevateIntegrationBinarySensorDescription, ...] = (
    ShellyElevateIntegrationBinarySensorDescription(
        key="presence",
        device_class=BinarySensorDeviceClass.OCCUPANCY,
        state_keys=("presence",),
        supported_fn=lambda d: d.info.capabilities.proximity and "presence" in d.state,
    ),
    ShellyElevateIntegrationBinarySensorDescription(
        key="screen_on",
        translation_key="screen_on",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        state_keys=("screen.on",),
        supported_fn=lambda d: not d.legacy and "screen.on" in d.state,
    ),
    ShellyElevateIntegrationBinarySensorDescription(
        key="voice_muted",
        translation_key="voice_muted",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        state_keys=("voice.muted",),
        supported_fn=has_state("voice.muted"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ShellyElevateIntegrationConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Set up binary sensors."""
    device = entry.runtime_data
    inputs = device.info.capabilities.inputs
    input_descriptions = [
        ShellyElevateIntegrationBinarySensorDescription(
            key=f"input_{idx}",
            device_class=BinarySensorDeviceClass.POWER,
            state_keys=(f"input.{idx}",),
            **indexed_name("input", idx, inputs),
        )
        for idx in range(inputs)
    ]
    async_add_entities(
        build_entities(device, (*BINARY_SENSORS, *input_descriptions), ShellyElevateIntegrationBinarySensor)
    )


class ShellyElevateIntegrationBinarySensor(ShellyElevateIntegrationEntity, BinarySensorEntity):
    """Binary sensor backed by one state key."""

    def __init__(
        self, device: ShellyElevateIntegrationDevice, description: ShellyElevateIntegrationBinarySensorDescription
    ) -> None:
        """Initialize."""
        super().__init__(device, description)
        assert description.state_keys
        self._state_key = description.state_keys[0]

    @property
    def is_on(self) -> bool | None:
        """Current state."""
        value = self.device.state.get(self._state_key)
        return None if value is None else bool(value)
