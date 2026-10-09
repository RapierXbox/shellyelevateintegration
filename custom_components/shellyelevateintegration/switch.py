"""Switches: relays, night mode and boolean settings."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.components.switch.const import SwitchDeviceClass
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import OPT_RELAYS_AS_LIGHTS
from .device import ShellyElevateIntegrationConfigEntry, ShellyElevateIntegrationDevice
from .entity import (
    ShellyElevateIntegrationEntity,
    ShellyElevateIntegrationEntityDescription,
    ShellyElevateIntegrationRelayEntity,
    build_entities,
    has_setting,
    has_state,
)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ShellyElevateIntegrationSwitchDescription(ShellyElevateIntegrationEntityDescription, SwitchEntityDescription):
    """Switch description."""


def _setting_switch(
    key: str, setting: str, *, config: bool = True, enabled: bool = True
) -> ShellyElevateIntegrationSwitchDescription:
    return ShellyElevateIntegrationSwitchDescription(
        key=key,
        translation_key=key,
        setting_key=setting,
        entity_category=EntityCategory.CONFIG if config else None,
        entity_registry_enabled_default=enabled,
        state_keys=(),
        supported_fn=has_setting(setting),
    )


# each one exists while its feature is on and is unavailable while its setting cannot take effect
SETTING_SWITCHES: tuple[ShellyElevateIntegrationSwitchDescription, ...] = (
    _setting_switch("screensaver", "screenSaver"),
    _setting_switch("auto_brightness", "automaticBrightness"),
    _setting_switch("wake_on_proximity", "wakeOnProximity"),
    _setting_switch("touch_to_wake", "touchToWake"),
    # voice and the bluetooth proxy run through this integration (the app's own satellite
    # and ESPHome proxy were removed)
    _setting_switch("voice_assistant", "haVoiceEnabled"),
    _setting_switch("voice_mute", "voiceAssistantMuted", config=False),
    _setting_switch("wake_word", "voiceWakeEnabled", enabled=False),
    _setting_switch("bluetooth_proxy", "bleScannerEnabled"),
    _setting_switch("media_enabled", "mediaEnabled"),
    _setting_switch("buttons_switch_relays", "buttonRelayEnabled", enabled=False),
    _setting_switch("switch_on_swipe", "switchOnSwipe", enabled=False),
    _setting_switch("legacy_mqtt", "mqttEnabled", enabled=False),
    # v1 displays only: on a legacy display this server is the connection itself
    replace(
        _setting_switch("legacy_http_api", "httpServer", enabled=False),
        supported_fn=lambda device: not device.legacy and device.setting_exists("httpServer"),
    ),
)

NIGHT_MODE = ShellyElevateIntegrationSwitchDescription(
    key="night_mode",
    translation_key="night_mode",
    state_keys=("night_mode",),
    supported_fn=has_state("night_mode"),
)


def create_entities(device: ShellyElevateIntegrationDevice) -> list[SwitchEntity]:
    """Switches the display should have now."""
    entities: list[SwitchEntity] = []
    if not device.entry.options.get(OPT_RELAYS_AS_LIGHTS, False):
        relays = device.info.capabilities.relays
        entities += [ShellyElevateIntegrationRelaySwitch(device, idx, relays) for idx in range(relays)]
    entities += build_entities(device, [NIGHT_MODE], ShellyElevateIntegrationNightModeSwitch)
    entities += build_entities(device, SETTING_SWITCHES, ShellyElevateIntegrationSettingSwitch)
    return entities


async def async_setup_entry(
    hass: HomeAssistant, entry: ShellyElevateIntegrationConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Set up switches."""
    async_add_entities(create_entities(entry.runtime_data))


class ShellyElevateIntegrationRelaySwitch(ShellyElevateIntegrationRelayEntity, SwitchEntity):
    """A relay (unless the "relays as lights" option is set)."""

    entity_description: ShellyElevateIntegrationSwitchDescription

    _attr_device_class = SwitchDeviceClass.OUTLET
    description_cls = ShellyElevateIntegrationSwitchDescription


class ShellyElevateIntegrationNightModeSwitch(ShellyElevateIntegrationEntity, SwitchEntity):
    """Night mode."""

    entity_description: ShellyElevateIntegrationSwitchDescription

    @property
    def is_on(self) -> bool | None:
        """Whether night mode is on."""
        return self.device.state.get("night_mode")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on."""
        await self.device.async_command("night_mode.set", on=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off."""
        await self.device.async_command("night_mode.set", on=False)


class ShellyElevateIntegrationSettingSwitch(ShellyElevateIntegrationEntity, SwitchEntity):
    """A boolean display setting."""

    entity_description: ShellyElevateIntegrationSwitchDescription

    @property
    def is_on(self) -> bool | None:
        """Current setting value."""
        value = self.setting
        # legacy displays may store booleans as strings
        if isinstance(value, str):
            return value.strip().lower() in ("true", "1", "on")
        return None if value is None else bool(value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on."""
        await self.async_set_setting(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off."""
        await self.async_set_setting(False)
