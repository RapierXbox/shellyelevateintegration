"""Lights: the screen itself, the backplate dimmer and (optionally) relays."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.light import LightEntity, LightEntityDescription
from homeassistant.components.light.const import ATTR_BRIGHTNESS, ATTR_EFFECT, ColorMode, LightEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import OPT_RELAYS_AS_LIGHTS
from .device import ShellyElevateIntegrationConfigEntry, ShellyElevateIntegrationDevice
from .entity import (
    ShellyElevateIntegrationEntity,
    ShellyElevateIntegrationEntityDescription,
    ShellyElevateIntegrationRelayEntity,
)

PARALLEL_UPDATES = 0

EFFECT_AUTO = "auto_brightness"
EFFECT_MANUAL = "manual"


@dataclass(frozen=True, kw_only=True)
class ShellyElevateIntegrationLightDescription(ShellyElevateIntegrationEntityDescription, LightEntityDescription):
    """Light description."""


async def async_setup_entry(
    hass: HomeAssistant, entry: ShellyElevateIntegrationConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Set up lights."""
    async_add_entities(create_entities(entry.runtime_data))


def create_entities(device: ShellyElevateIntegrationDevice) -> list[LightEntity]:
    """Lights the display should have now."""
    caps = device.info.capabilities
    # every display reports screen.on (the legacy client optimistically)
    entities: list[LightEntity] = [ShellyElevateIntegrationScreenLight(device)]
    if caps.dimmer:
        entities.append(ShellyElevateIntegrationDimmerLight(device))
    if device.entry.options.get(OPT_RELAYS_AS_LIGHTS, False):
        entities += [ShellyElevateIntegrationRelayLight(device, idx, caps.relays) for idx in range(caps.relays)]
    return entities


class ShellyElevateIntegrationScreenLight(ShellyElevateIntegrationEntity, LightEntity):
    """The display backlight: on = awake, off = screensaver/sleep."""

    entity_description: ShellyElevateIntegrationLightDescription

    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_features = LightEntityFeature.EFFECT
    _attr_effect_list = [EFFECT_MANUAL, EFFECT_AUTO]

    def __init__(self, device: ShellyElevateIntegrationDevice) -> None:
        """Initialize."""
        super().__init__(
            device,
            ShellyElevateIntegrationLightDescription(
                key="screen",
                translation_key="screen",
                state_keys=("screen.on", "screen.brightness", "screen.auto_brightness"),
            ),
        )

    @property
    def is_on(self) -> bool | None:
        """Whether the screen is awake."""
        awake: bool | None = self.device.state.get("screen.on", True)
        return awake

    @property
    def brightness(self) -> int | None:
        """Brightness 0..255."""
        value = self.device.state.get("screen.brightness")
        return None if value is None else max(1, int(value))

    @property
    def effect(self) -> str | None:
        """Auto brightness on/off."""
        auto = self.device.state.get("screen.auto_brightness")
        if auto is None:
            return None
        return EFFECT_AUTO if auto else EFFECT_MANUAL

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Wake and/or set brightness."""
        if not self.device.state.get("screen.on", True) or not kwargs:
            await self.device.async_command("screen.wake")
        params: dict[str, Any] = {}
        if ATTR_BRIGHTNESS in kwargs:
            params["brightness"] = int(kwargs[ATTR_BRIGHTNESS])
            params["auto"] = False
        if ATTR_EFFECT in kwargs:
            params["auto"] = kwargs[ATTR_EFFECT] == EFFECT_AUTO
        if params:
            await self.device.async_command("screen.set", **params)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Screensaver / sleep."""
        await self.device.async_command("screen.sleep")


class ShellyElevateIntegrationDimmerLight(ShellyElevateIntegrationEntity, LightEntity):
    """Shelly dimmer backplate."""

    entity_description: ShellyElevateIntegrationLightDescription

    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS

    def __init__(self, device: ShellyElevateIntegrationDevice) -> None:
        """Initialize."""
        super().__init__(
            device,
            ShellyElevateIntegrationLightDescription(
                key="dimmer", translation_key="dimmer", state_keys=("dimmer.on", "dimmer.brightness")
            ),
        )

    @property
    def is_on(self) -> bool | None:
        """Whether the dimmer is on."""
        return self.device.state.get("dimmer.on")

    @property
    def brightness(self) -> int | None:
        """Brightness 0..255 (display uses 0..100)."""
        value = self.device.state.get("dimmer.brightness")
        return None if value is None else round(int(value) * 255 / 100)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on."""
        if ATTR_BRIGHTNESS in kwargs:
            await self.device.async_command(
                "dimmer.set", on=True, brightness=max(1, round(kwargs[ATTR_BRIGHTNESS] * 100 / 255))
            )
        else:
            await self.device.async_command("dimmer.set", on=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off."""
        await self.device.async_command("dimmer.set", on=False)


class ShellyElevateIntegrationRelayLight(ShellyElevateIntegrationRelayEntity, LightEntity):
    """A relay exposed as an on/off light ("relays as lights" option)."""

    entity_description: ShellyElevateIntegrationLightDescription

    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_color_mode = ColorMode.ONOFF
    description_cls = ShellyElevateIntegrationLightDescription
