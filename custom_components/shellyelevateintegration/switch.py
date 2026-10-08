"""Switches: relays, night mode and boolean settings."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import Capabilities
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
    key: str,
    setting: str,
    *,
    config: bool = True,
    enabled: bool = True,
    cap: Callable[[Capabilities], bool] | None = None,
) -> ShellyElevateIntegrationSwitchDescription:
    return ShellyElevateIntegrationSwitchDescription(
        key=key,
        translation_key=key,
        setting_key=setting,
        entity_category=EntityCategory.CONFIG if config else None,
        entity_registry_enabled_default=enabled,
        state_keys=(),
        supported_fn=_supported(setting, cap),
    )


def _supported(
    setting: str, cap: Callable[[Capabilities], bool] | None
) -> Callable[[ShellyElevateIntegrationDevice], bool]:
    """The display knows the setting and has the hardware it needs."""
    known = has_setting(setting)

    def _check(device: ShellyElevateIntegrationDevice) -> bool:
        # legacy capabilities are guessed from the model table so they do not rule anything out
        return known(device) and (cap is None or device.legacy or cap(device.info.capabilities))

    return _check


SETTING_SWITCHES: tuple[ShellyElevateIntegrationSwitchDescription, ...] = (
    _setting_switch("screensaver", "screenSaver"),
    _setting_switch("auto_brightness", "automaticBrightness"),
    _setting_switch("wake_on_proximity", "wakeOnProximity", cap=lambda caps: caps.proximity),
    _setting_switch("touch_to_wake", "touchToWake"),
    # voice and the bluetooth proxy run through this integration (the app's own satellite
    # and ESPHome proxy were removed)
    _setting_switch("voice_assistant", "haVoiceEnabled"),
    _setting_switch("voice_mute", "voiceAssistantMuted", config=False),
    _setting_switch("wake_word", "voiceWakeEnabled", enabled=False),
    _setting_switch("bluetooth_proxy", "bleScannerEnabled"),
    _setting_switch("media_enabled", "mediaEnabled"),
    _setting_switch(
        "buttons_switch_relays",
        "buttonRelayEnabled",
        enabled=False,
        cap=lambda caps: caps.buttons >= 1 and caps.relays >= 1,
    ),
    _setting_switch("switch_on_swipe", "switchOnSwipe", enabled=False, cap=lambda caps: caps.relays >= 1),
    _setting_switch("legacy_mqtt", "mqttEnabled", enabled=False),
    # v1 displays only: on a legacy display this server is the connection itself
    replace(
        _setting_switch("legacy_http_api", "httpServer", enabled=False),
        supported_fn=lambda device: not device.legacy and "httpServer" in device.settings,
    ),
)

NIGHT_MODE = ShellyElevateIntegrationSwitchDescription(
    key="night_mode",
    translation_key="night_mode",
    state_keys=("night_mode",),
    supported_fn=has_state("night_mode"),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ShellyElevateIntegrationConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Set up switches."""
    device = entry.runtime_data
    entities: list[SwitchEntity] = []
    if not entry.options.get(OPT_RELAYS_AS_LIGHTS, False):
        relays = device.info.capabilities.relays
        entities += [ShellyElevateIntegrationRelaySwitch(device, idx, relays) for idx in range(relays)]
    entities += build_entities(device, [NIGHT_MODE], ShellyElevateIntegrationNightModeSwitch)
    entities += build_entities(device, SETTING_SWITCHES, ShellyElevateIntegrationSettingSwitch)
    async_add_entities(entities)


class ShellyElevateIntegrationRelaySwitch(ShellyElevateIntegrationRelayEntity, SwitchEntity):
    """A relay (unless the "relays as lights" option is set)."""

    _attr_device_class = SwitchDeviceClass.OUTLET
    description_cls = ShellyElevateIntegrationSwitchDescription


class ShellyElevateIntegrationNightModeSwitch(ShellyElevateIntegrationEntity, SwitchEntity):
    """Night mode."""

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

    @property
    def is_on(self) -> bool | None:
        """Current setting value."""
        value = self.setting
        return None if value is None else bool(value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on."""
        await self.async_set_setting(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off."""
        await self.async_set_setting(False)
