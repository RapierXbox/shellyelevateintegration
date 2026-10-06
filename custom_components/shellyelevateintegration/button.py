"""Buttons."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .device import ShellyElevateIntegrationConfigEntry, ShellyElevateIntegrationDevice
from .entity import ShellyElevateIntegrationEntity, ShellyElevateIntegrationEntityDescription, build_entities

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class ShellyElevateIntegrationButtonDescription(ShellyElevateIntegrationEntityDescription, ButtonEntityDescription):
    """Button description."""

    press_fn: Callable[[ShellyElevateIntegrationDevice], Awaitable[Any]]


async def _backup(device: ShellyElevateIntegrationDevice) -> None:
    assert device.backups is not None
    await device.backups.async_backup()


async def _screenshot(device: ShellyElevateIntegrationDevice) -> None:
    if device.screenshot_entity is not None:
        await device.screenshot_entity.async_capture()


BUTTONS: tuple[ShellyElevateIntegrationButtonDescription, ...] = (
    ShellyElevateIntegrationButtonDescription(
        key="reboot",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda d: d.async_command("device.reboot"),
    ),
    ShellyElevateIntegrationButtonDescription(
        key="restart_app",
        translation_key="restart_app",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda d: d.async_command("app.restart"),
        supported_fn=lambda d: not d.legacy,
    ),
    ShellyElevateIntegrationButtonDescription(
        key="reload_dashboard",
        translation_key="reload_dashboard",
        press_fn=lambda d: d.async_command("webview.reload"),
    ),
    ShellyElevateIntegrationButtonDescription(
        key="wake",
        translation_key="wake",
        press_fn=lambda d: d.async_command("screen.wake"),
    ),
    ShellyElevateIntegrationButtonDescription(
        key="sleep",
        translation_key="sleep",
        press_fn=lambda d: d.async_command("screen.sleep"),
    ),
    ShellyElevateIntegrationButtonDescription(
        key="take_screenshot",
        translation_key="take_screenshot",
        entity_category=EntityCategory.DIAGNOSTIC,
        press_fn=_screenshot,
        supported_fn=lambda d: d.info.capabilities.screenshot or d.adb is not None,
    ),
    ShellyElevateIntegrationButtonDescription(
        key="backup_settings",
        translation_key="backup_settings",
        entity_category=EntityCategory.CONFIG,
        press_fn=_backup,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ShellyElevateIntegrationConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Set up buttons."""
    async_add_entities(build_entities(entry.runtime_data, BUTTONS, ShellyElevateIntegrationButton))


class ShellyElevateIntegrationButton(ShellyElevateIntegrationEntity, ButtonEntity):
    """A button that runs a display action."""

    entity_description: ShellyElevateIntegrationButtonDescription

    async def async_press(self) -> None:
        """Run the action."""
        await self.entity_description.press_fn(self.device)
