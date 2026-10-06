"""Base entities for Shelly Elevate."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.entity import Entity, EntityDescription

from .device import ShellyElevateIntegrationDevice


@dataclass(frozen=True, kw_only=True)
class ShellyElevateIntegrationEntityDescription(EntityDescription):
    """Common description fields."""

    # Created only when this returns True for the display's capabilities.
    supported_fn: Callable[[ShellyElevateIntegrationDevice], bool] = lambda _device: True
    # State keys this entity depends on; None = update on every change.
    state_keys: tuple[str, ...] | None = None
    # Setting key this entity reads/writes (settings-backed entities).
    setting_key: str | None = None


def has_cap(name: str) -> Callable[[ShellyElevateIntegrationDevice], bool]:
    """Return a supported_fn checking a capability flag."""

    def _check(device: ShellyElevateIntegrationDevice) -> bool:
        return bool(getattr(device.info.capabilities, name, False))

    return _check


def has_setting(key: str) -> Callable[[ShellyElevateIntegrationDevice], bool]:
    """Return a supported_fn checking that the display knows a setting."""

    def _check(device: ShellyElevateIntegrationDevice) -> bool:
        return key in device.settings

    return _check


def has_state(key: str) -> Callable[[ShellyElevateIntegrationDevice], bool]:
    """Return a supported_fn checking that the display reports a state key."""

    def _check(device: ShellyElevateIntegrationDevice) -> bool:
        return key in device.state

    return _check


def indexed_name(translation_key: str, index: int, count: int) -> dict[str, Any]:
    """Name fields for the n-th relay/input: "Relay 2", or just "Relay" if there is only one."""
    return {
        "translation_key": translation_key if count > 1 else f"{translation_key}_single",
        "translation_placeholders": {"index": str(index + 1)},
    }


class ShellyElevateIntegrationEntity(Entity):
    """Base class: one display = one device."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    entity_description: ShellyElevateIntegrationEntityDescription

    def __init__(
        self,
        device: ShellyElevateIntegrationDevice,
        description: ShellyElevateIntegrationEntityDescription,
        unique_suffix: str | None = None,
    ) -> None:
        """Initialize."""
        self.device = device
        self.entity_description = description
        self._attr_unique_id = f"{device.device_id}_{unique_suffix or description.key}"
        self._attr_device_info = device.device_info

    @property
    def available(self) -> bool:
        """Entity is available while the display is reachable."""
        return self.device.available

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates."""
        self.async_on_remove(self.device.async_add_state_listener(self._handle_state))
        self.async_on_remove(self.device.async_add_availability_listener(self.async_write_ha_state))
        if self.entity_description.setting_key is not None:
            self.async_on_remove(self.device.async_add_message_listener(self._handle_settings_message))

    @callback
    def _handle_state(self, changes: dict[str, Any]) -> None:
        keys = self.entity_description.state_keys
        if keys is None or not changes or any(key in changes for key in keys):
            self.async_write_ha_state()

    @callback
    def _handle_settings_message(self, message: dict[str, Any]) -> None:
        if message.get("type") == "settings_changed" and self.entity_description.setting_key in (
            message.get("changes") or {}
        ):
            self.async_write_ha_state()

    @property
    def setting(self) -> Any:
        """Current value of the backing setting."""
        return self.device.settings.get(self.entity_description.setting_key or "")

    async def async_set_setting(self, value: Any) -> None:
        """Write the backing setting."""
        assert self.entity_description.setting_key is not None
        await self.device.async_set_settings({self.entity_description.setting_key: value})
        self.async_write_ha_state()


def _relay_exists(device: ShellyElevateIntegrationDevice, index: int) -> bool:
    """False for relays that only exist with an optional power base."""
    optional_from = device.info.capabilities.optional_relays_from
    return optional_from is None or index < optional_from


class ShellyElevateIntegrationRelayEntity(ShellyElevateIntegrationEntity):
    """A relay; subclasses combine it with the switch or the light platform."""

    description_cls: type[ShellyElevateIntegrationEntityDescription]

    def __init__(self, device: ShellyElevateIntegrationDevice, index: int, count: int) -> None:
        """Initialize."""
        super().__init__(
            device,
            self.description_cls(
                key=f"relay_{index}",
                state_keys=(f"relay.{index}",),
                entity_registry_enabled_default=_relay_exists(device, index),
                **indexed_name("relay", index, count),
            ),
        )
        self._index = index

    @property
    def is_on(self) -> bool | None:
        """Relay state."""
        return self.device.state.get(f"relay.{self._index}")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Close the relay."""
        await self.device.async_command("relay.set", index=self._index, on=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Open the relay."""
        await self.device.async_command("relay.set", index=self._index, on=False)


def build_entities[D: ShellyElevateIntegrationEntityDescription, E: Entity](
    device: ShellyElevateIntegrationDevice,
    descriptions: Iterable[D],
    factory: Callable[[ShellyElevateIntegrationDevice, D], E],
) -> list[E]:
    """Create entities for all descriptions the display supports."""
    return [factory(device, desc) for desc in descriptions if desc.supported_fn(device)]
