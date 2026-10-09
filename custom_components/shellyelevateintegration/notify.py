"""Notify entity: on-screen messages."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.notify import NotifyEntity, NotifyEntityDescription
from homeassistant.components.notify.const import NotifyEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .device import ShellyElevateIntegrationConfigEntry, ShellyElevateIntegrationDevice
from .entity import ShellyElevateIntegrationEntity, ShellyElevateIntegrationEntityDescription

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class ShellyElevateIntegrationNotifyDescription(ShellyElevateIntegrationEntityDescription, NotifyEntityDescription):
    """Notify description."""


async def async_setup_entry(
    hass: HomeAssistant, entry: ShellyElevateIntegrationConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Set up the notify entity."""
    async_add_entities(create_entities(entry.runtime_data))


def create_entities(device: ShellyElevateIntegrationDevice) -> list[NotifyEntity]:
    """The notify entity (every display can show a message)."""
    return [ShellyElevateIntegrationNotify(device)]


class ShellyElevateIntegrationNotify(ShellyElevateIntegrationEntity, NotifyEntity):
    """Shows a toast on the display."""

    entity_description: ShellyElevateIntegrationNotifyDescription

    _attr_supported_features = NotifyEntityFeature.TITLE

    def __init__(self, device: ShellyElevateIntegrationDevice) -> None:
        """Initialize."""
        super().__init__(
            device, ShellyElevateIntegrationNotifyDescription(key="notify", translation_key="notify", state_keys=())
        )

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Show the message."""
        params: dict[str, str] = {"message": message}
        if title:
            params["title"] = title
        await self.device.async_command("ui.notify", **params)
