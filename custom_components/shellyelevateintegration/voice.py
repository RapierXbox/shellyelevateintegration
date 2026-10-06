"""Voice helpers: Assist pipeline / VAD selects bound to the display device."""

from __future__ import annotations

from homeassistant.components.assist_pipeline import AssistPipelineSelect, VadSensitivitySelect
from homeassistant.components.select import SelectEntity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .device import ShellyElevateIntegrationDevice


def _prefix(device: ShellyElevateIntegrationDevice) -> str:
    """Unique id prefix of the Assist selects of a display."""
    return device.device_id


def pipeline_select_entity_id(hass: HomeAssistant, device: ShellyElevateIntegrationDevice) -> str | None:
    """Entity id of the pipeline select of a display."""
    return er.async_get(hass).async_get_entity_id(Platform.SELECT, DOMAIN, f"{_prefix(device)}-pipeline")


def vad_select_entity_id(hass: HomeAssistant, device: ShellyElevateIntegrationDevice) -> str | None:
    """Entity id of the VAD sensitivity select of a display."""
    return er.async_get(hass).async_get_entity_id(Platform.SELECT, DOMAIN, f"{_prefix(device)}-vad_sensitivity")


class _DisplayBoundSelect(SelectEntity):
    """Assist select attached to the display device and available while it is connected."""

    _attr_has_entity_name = True
    _device: ShellyElevateIntegrationDevice

    @property
    def available(self) -> bool:
        """Available while the display is connected."""
        return self._device.available

    async def async_added_to_hass(self) -> None:
        """Write the state when the display comes and goes."""
        await super().async_added_to_hass()
        self.async_on_remove(self._device.async_add_availability_listener(self.async_write_ha_state))


class ShellyElevateIntegrationPipelineSelect(_DisplayBoundSelect, AssistPipelineSelect):
    """Pipeline used by the display's Assist satellite."""

    def __init__(self, hass: HomeAssistant, device: ShellyElevateIntegrationDevice) -> None:
        """Initialize."""
        super().__init__(hass, DOMAIN, _prefix(device))
        self._device = device
        self._attr_device_info = device.device_info


class ShellyElevateIntegrationVadSelect(_DisplayBoundSelect, VadSensitivitySelect):
    """Silence detection sensitivity of the display's Assist satellite."""

    def __init__(self, hass: HomeAssistant, device: ShellyElevateIntegrationDevice) -> None:
        """Initialize."""
        super().__init__(hass, _prefix(device))
        self._device = device
        self._attr_device_info = device.device_info


def async_get_voice_selects(hass: HomeAssistant, device: ShellyElevateIntegrationDevice) -> list[SelectEntity]:
    """Selects created on the select platform when the display has a microphone."""
    return [ShellyElevateIntegrationPipelineSelect(hass, device), ShellyElevateIntegrationVadSelect(hass, device)]
