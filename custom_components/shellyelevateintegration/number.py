"""Number entities backed by display settings."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import SettingDef
from .device import ShellyElevateIntegrationConfigEntry, ShellyElevateIntegrationDevice
from .entity import (
    ShellyElevateIntegrationEntity,
    ShellyElevateIntegrationEntityDescription,
    build_entities,
    has_setting,
)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ShellyElevateIntegrationNumberDescription(ShellyElevateIntegrationEntityDescription, NumberEntityDescription):
    """Number description."""

    # Write the value as float instead of int (the display schema overrides it).
    is_float: bool = False


def _num(
    key: str,
    setting: str,
    minimum: float,
    maximum: float,
    step: float = 1,
    unit: str | None = None,
    *,
    enabled: bool = True,
    is_float: bool = False,
    mode: NumberMode = NumberMode.AUTO,
) -> ShellyElevateIntegrationNumberDescription:
    return ShellyElevateIntegrationNumberDescription(
        key=key,
        translation_key=key,
        setting_key=setting,
        native_min_value=minimum,
        native_max_value=maximum,
        native_step=step,
        native_unit_of_measurement=unit,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=enabled,
        mode=mode,
        is_float=is_float,
        state_keys=(),
        supported_fn=has_setting(setting),
    )


# ranges are those of protocol v1 and only apply when the display sends no schema
NUMBERS: tuple[ShellyElevateIntegrationNumberDescription, ...] = (
    _num("screensaver_delay", "screenSaverDelay", 5, 86400, 5, UnitOfTime.SECONDS, mode=NumberMode.BOX),
    _num("min_brightness", "minBrightness", 0, 255),
    _num("screensaver_brightness", "screenSaverMinBrightness", 0, 255, enabled=False),
    _num(
        "proximity_keep_awake",
        "proximityKeepAwakeSeconds",
        0,
        86400,
        5,
        UnitOfTime.SECONDS,
        enabled=False,
        mode=NumberMode.BOX,
    ),
    # 0..100 on v1 and a 0..1 float on the legacy app (from its schema)
    _num("wake_word_sensitivity", "voiceWakeSensitivity", 0, 100, 1, enabled=False),
    _num("voice_max_record", "voiceAssistantMaxRecordSeconds", 1, 60, 1, UnitOfTime.SECONDS, enabled=False),
)


def create_entities(device: ShellyElevateIntegrationDevice) -> list[NumberEntity]:
    """Numbers the display should have now (ranges from the schema fetched at setup)."""
    schema = {item.key: item for item in device.schema or []}
    return build_entities(
        device,
        NUMBERS,
        lambda dev, desc: ShellyElevateIntegrationSettingNumber(dev, desc, schema.get(desc.setting_key or "")),
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ShellyElevateIntegrationConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Set up numbers."""
    await entry.runtime_data.async_get_schema()
    async_add_entities(create_entities(entry.runtime_data))


class ShellyElevateIntegrationSettingNumber(ShellyElevateIntegrationEntity, NumberEntity):
    """A numeric display setting."""

    entity_description: ShellyElevateIntegrationNumberDescription

    def __init__(
        self,
        device: ShellyElevateIntegrationDevice,
        description: ShellyElevateIntegrationNumberDescription,
        definition: SettingDef | None = None,
    ) -> None:
        """Initialize; range and type come from the display schema when it has the setting."""
        super().__init__(device, description)
        self._is_float = description.is_float
        if definition is None:
            return
        if definition.min is not None:
            self._attr_native_min_value = definition.min
        if definition.max is not None:
            self._attr_native_max_value = definition.max
        if definition.step is not None:
            self._attr_native_step = definition.step
        if definition.type in ("int", "float"):
            self._is_float = definition.type == "float"

    @property
    def native_value(self) -> float | None:
        """Current setting value."""
        value = self.setting
        return None if value is None else float(value)

    async def async_set_native_value(self, value: float) -> None:
        """Write the setting."""
        await self.async_set_setting(value if self._is_float else round(value))
