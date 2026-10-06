"""Select entities."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
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
class ShellyElevateIntegrationSelectDescription(ShellyElevateIntegrationEntityDescription, SelectEntityDescription):
    """Select backed by an integer enum setting."""

    # option -> raw setting value
    values: dict[str, int]


def _setting_select(
    key: str, setting: str, values: dict[str, int], *, enabled: bool = True
) -> ShellyElevateIntegrationSelectDescription:
    return ShellyElevateIntegrationSelectDescription(
        key=key,
        translation_key=key,
        setting_key=setting,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=enabled,
        values=values,
        options=list(values),
        state_keys=(),
        supported_fn=has_setting(setting),
    )


SELECTS: tuple[ShellyElevateIntegrationSelectDescription, ...] = (
    _setting_select("screensaver_type", "screenSaverId", {"off": 0, "clock": 1, "clock_date": 2, "always_on": 3}),
    _setting_select(
        "sleep_optimization", "sleepOptimizationLevel", {"off": 0, "balanced": 1, "aggressive": 2}, enabled=False
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ShellyElevateIntegrationConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Set up selects."""
    device = entry.runtime_data
    entities: list[SelectEntity] = build_entities(device, SELECTS, ShellyElevateIntegrationSettingSelect)
    if device.voice_enabled:
        # Imported lazily: it pulls in assist_pipeline, which is only set up for voice displays.
        from .voice import async_get_voice_selects

        entities += async_get_voice_selects(hass, device)
    async_add_entities(entities)


class ShellyElevateIntegrationSettingSelect(ShellyElevateIntegrationEntity, SelectEntity):
    """An enum display setting."""

    entity_description: ShellyElevateIntegrationSelectDescription

    @property
    def current_option(self) -> str | None:
        """Option matching the current setting value."""
        value = self.setting
        return next((option for option, raw in self.entity_description.values.items() if raw == value), None)

    async def async_select_option(self, option: str) -> None:
        """Write the setting."""
        await self.async_set_setting(self.entity_description.values[option])
