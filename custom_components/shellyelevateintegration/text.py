"""Text entities backed by display settings."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.text import TextEntity, TextEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .device import ShellyElevateIntegrationConfigEntry, ShellyElevateIntegrationDevice
from .entity import (
    ShellyElevateIntegrationEntity,
    ShellyElevateIntegrationEntityDescription,
    build_entities,
    has_setting,
)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ShellyElevateIntegrationTextDescription(ShellyElevateIntegrationEntityDescription, TextEntityDescription):
    """Text description."""


TEXTS: tuple[ShellyElevateIntegrationTextDescription, ...] = (
    ShellyElevateIntegrationTextDescription(
        key="dashboard_url",
        translation_key="dashboard_url",
        setting_key="webviewUrl",
        entity_category=EntityCategory.CONFIG,
        native_max=2048,
        state_keys=(),
        supported_fn=has_setting("webviewUrl"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ShellyElevateIntegrationConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Set up texts."""
    async_add_entities(create_entities(entry.runtime_data))


def create_entities(device: ShellyElevateIntegrationDevice) -> list[TextEntity]:
    """Texts the display should have now."""
    return build_entities(device, TEXTS, ShellyElevateIntegrationSettingText)


class ShellyElevateIntegrationSettingText(ShellyElevateIntegrationEntity, TextEntity):
    """A string display setting."""

    @property
    def native_value(self) -> str | None:
        """Current setting value."""
        value = self.setting
        return None if value is None else str(value)

    async def async_set_value(self, value: str) -> None:
        """Write the setting."""
        await self.async_set_setting(value)
