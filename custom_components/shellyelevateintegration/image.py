"""Screenshot of what the display currently shows."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.components.image import ImageEntity, ImageEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import ShellyElevateIntegrationError
from .const import DOMAIN
from .device import ShellyElevateIntegrationConfigEntry, ShellyElevateIntegrationDevice
from .entity import ShellyElevateIntegrationEntity, ShellyElevateIntegrationEntityDescription

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class ShellyElevateIntegrationImageDescription(ShellyElevateIntegrationEntityDescription, ImageEntityDescription):
    """Image description."""


async def async_take_screenshot(device: ShellyElevateIntegrationDevice) -> bytes:
    """Take a screenshot via the app, falling back to ADB."""
    try:
        if device.info.capabilities.screenshot and (data := await device.client.screenshot()):
            return data
    except ShellyElevateIntegrationError as err:
        _LOGGER.debug("App screenshot failed: %s", err)
    if (adb := device.adb) is not None:
        return await adb.async_screenshot()
    raise HomeAssistantError(translation_domain=DOMAIN, translation_key="screenshot_unsupported")


async def async_setup_entry(
    hass: HomeAssistant, entry: ShellyElevateIntegrationConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Set up the screenshot image."""
    device = entry.runtime_data
    if device.info.capabilities.screenshot or device.adb is not None:
        async_add_entities([ShellyElevateIntegrationScreenshot(hass, device)])


class ShellyElevateIntegrationScreenshot(ShellyElevateIntegrationEntity, ImageEntity):
    """Last screenshot (taken with the Screenshot button or the screenshot action)."""

    _attr_content_type = "image/png"

    def __init__(self, hass: HomeAssistant, device: ShellyElevateIntegrationDevice) -> None:
        """Initialize."""
        ShellyElevateIntegrationEntity.__init__(
            self,
            device,
            ShellyElevateIntegrationImageDescription(key="screenshot", translation_key="screenshot", state_keys=()),
        )
        ImageEntity.__init__(self, hass)
        self._image: bytes | None = None

    async def async_added_to_hass(self) -> None:
        """Register as the screenshot target of the device."""
        await super().async_added_to_hass()
        self.device.screenshot_entity = self

        def _unregister() -> None:
            if self.device.screenshot_entity is self:
                self.device.screenshot_entity = None

        self.async_on_remove(_unregister)

    async def async_capture(self) -> bytes:
        """Take a new screenshot and publish it."""
        self._image = await async_take_screenshot(self.device)
        self._attr_image_last_updated = dt_util.utcnow()
        self.async_write_ha_state()
        return self._image

    async def async_image(self) -> bytes | None:
        """Return the last screenshot (taking one if there is none yet)."""
        if self._image is None and self.available:
            try:
                await self.async_capture()
            except HomeAssistantError:
                return None
        return self._image
