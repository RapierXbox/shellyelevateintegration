"""Number entities backed by display settings."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .device import ShellyElevateIntegrationConfigEntry
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

    # Write the value as float instead of int.
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


NUMBERS: tuple[ShellyElevateIntegrationNumberDescription, ...] = (
    _num("screensaver_delay", "screenSaverDelay", 5, 3600, 5, UnitOfTime.SECONDS, mode=NumberMode.BOX),
    _num("min_brightness", "minBrightness", 0, 255),
    _num("screensaver_brightness", "screenSaverMinBrightness", 0, 255, enabled=False),
    _num(
        "proximity_keep_awake",
        "proximityKeepAwakeSeconds",
        0,
        3600,
        5,
        UnitOfTime.SECONDS,
        enabled=False,
        mode=NumberMode.BOX,
    ),
    _num("wake_word_sensitivity", "voiceWakeSensitivity", 0, 1, 0.05, enabled=False, is_float=True),
    _num("voice_max_record", "voiceAssistantMaxRecordSeconds", 1, 60, 1, UnitOfTime.SECONDS, enabled=False),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ShellyElevateIntegrationConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Set up numbers."""
    async_add_entities(build_entities(entry.runtime_data, NUMBERS, ShellyElevateIntegrationSettingNumber))


class ShellyElevateIntegrationSettingNumber(ShellyElevateIntegrationEntity, NumberEntity):
    """A numeric display setting."""

    entity_description: ShellyElevateIntegrationNumberDescription

    @property
    def native_value(self) -> float | None:
        """Current setting value."""
        value = self.setting
        return None if value is None else float(value)

    async def async_set_native_value(self, value: float) -> None:
        """Write the setting."""
        await self.async_set_setting(value if self.entity_description.is_float else int(value))
