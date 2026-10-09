"""Event entities: physical buttons, wired inputs, power button, swipe gestures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.event import EventDeviceClass, EventEntity, EventEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api.visibility import condition_holds
from .device import ShellyElevateIntegrationConfigEntry, ShellyElevateIntegrationDevice
from .entity import ShellyElevateIntegrationEntity, ShellyElevateIntegrationEntityDescription, indexed_name

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ShellyElevateIntegrationEventDescription(ShellyElevateIntegrationEntityDescription, EventEntityDescription):
    """Event description."""


def _swipe_type(direction: str, fingers: int) -> str:
    """Event type of a swipe: "left" for one finger, "left_2" for two, ..."""
    return direction if fingers == 1 else f"{direction}_{fingers}"


SWIPE_SETTING = "publishSwipeEvents"

PRESS_TYPES = ["single", "double", "triple", "long"]
SWIPE_TYPES = [
    _swipe_type(direction, fingers) for fingers in (1, 2, 3, 4, 5) for direction in ("up", "down", "left", "right")
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ShellyElevateIntegrationConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Set up event entities."""
    async_add_entities(create_entities(entry.runtime_data))


def create_entities(device: ShellyElevateIntegrationDevice) -> list[EventEntity]:
    """Event entities the display should have now."""
    caps = device.info.capabilities
    if not caps.push:
        # The legacy app only publishes button/swipe events over MQTT.
        return []
    entities: list[EventEntity] = [
        ShellyElevateIntegrationButtonEvent(device, "button", idx) for idx in range(caps.buttons)
    ]
    entities += [ShellyElevateIntegrationButtonEvent(device, "input", idx, caps.inputs) for idx in range(caps.inputs)]
    if caps.power_button:
        entities.append(ShellyElevateIntegrationButtonEvent(device, "power_button", None))
    # publishSwipeEvents only makes it unavailable (see features.py)
    entities.append(ShellyElevateIntegrationSwipeEvent(device))
    return entities


class _ShellyElevateIntegrationEvent(ShellyElevateIntegrationEntity, EventEntity):
    """Base class: fires on matching `event` messages from the display."""

    entity_description: ShellyElevateIntegrationEventDescription

    async def async_added_to_hass(self) -> None:
        """Listen for display events."""
        await super().async_added_to_hass()
        self.async_on_remove(self.device.async_add_message_listener(self._on_message))

    @callback
    def _on_message(self, message: dict[str, Any]) -> None:
        if message.get("type") != "event":
            return
        if (event_type := self._match(message)) is not None:
            attrs = {k: v for k, v in message.items() if k not in ("type", "event")}
            self._trigger_event(event_type, attrs)
            self.async_write_ha_state()

    def _match(self, message: dict[str, Any]) -> str | None:
        """Event type for this entity, or None if the message is not for it."""
        raise NotImplementedError

    @callback
    def _handle_state(self, changes: dict[str, Any]) -> None:
        """Events do not depend on state."""


class ShellyElevateIntegrationButtonEvent(_ShellyElevateIntegrationEvent):
    """A physical button (XL), a wired input in button mode or the power button."""

    _attr_device_class = EventDeviceClass.BUTTON
    _attr_event_types = PRESS_TYPES

    def __init__(self, device: ShellyElevateIntegrationDevice, kind: str, index: int | None, count: int = 0) -> None:
        """Initialize."""
        if kind == "power_button":
            desc = ShellyElevateIntegrationEventDescription(key="power_button", translation_key="power_button")
        elif kind == "input":
            desc = ShellyElevateIntegrationEventDescription(
                key=f"input_{index}", **indexed_name("input", index or 0, count)
            )
        else:
            desc = ShellyElevateIntegrationEventDescription(
                key=f"button_{index}",
                translation_key="button",
                translation_placeholders={"index": str((index or 0) + 1)},
            )
        super().__init__(device, desc)
        self._kind = kind
        self._index = index

    def _match(self, message: dict[str, Any]) -> str | None:
        if message.get("event") != self._kind:
            return None
        if self._index is not None and message.get("index", 0) != self._index:
            return None
        press = message.get("press", "single")
        return press if press in PRESS_TYPES else None


class ShellyElevateIntegrationSwipeEvent(_ShellyElevateIntegrationEvent):
    """Swipe gestures on the screen."""

    _attr_event_types = SWIPE_TYPES

    def __init__(self, device: ShellyElevateIntegrationDevice) -> None:
        """Initialize."""
        super().__init__(device, ShellyElevateIntegrationEventDescription(key="swipe", translation_key="swipe"))

    @property
    def available(self) -> bool:
        """Unavailable while the display does not publish swipes."""
        if not super().available:
            return False
        value = self.device.settings.get(SWIPE_SETTING)
        return value is None or condition_holds({"eq": True}, value, loose=self.device.legacy)

    async def async_added_to_hass(self) -> None:
        """Follow the setting that turns swipe events on and off."""
        await super().async_added_to_hass()
        self.async_on_remove(self.device.async_add_message_listener(self._on_settings))

    @callback
    def _on_settings(self, message: dict[str, Any]) -> None:
        if message.get("type") == "settings_changed" and SWIPE_SETTING in (message.get("changes") or {}):
            self.async_write_ha_state()

    def _match(self, message: dict[str, Any]) -> str | None:
        if message.get("event") != "swipe":
            return None
        fingers = message.get("fingers")
        event_type = _swipe_type(str(message.get("direction")), fingers if isinstance(fingers, int) else 1)
        return event_type if event_type in SWIPE_TYPES else None
