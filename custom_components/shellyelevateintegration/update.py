"""App update entity (GitHub releases; installs via the app itself or ADB)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .adb.apk import AppRelease, async_get_releases, async_latest_release, version_key
from .const import DOMAIN, OPT_UPDATE_CHANNEL, UPDATE_CHANNEL_STABLE
from .device import ShellyElevateIntegrationConfigEntry, ShellyElevateIntegrationDevice
from .entity import ShellyElevateIntegrationEntity, ShellyElevateIntegrationEntityDescription
from .settings.backups import REASON_BEFORE_UPDATE

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1
SCAN_INTERVAL = timedelta(hours=6)
SELF_UPDATE_TIMEOUT = 600
"""Seconds to wait for the app to restart or report a failed self update."""
RESTART_TIMEOUT = 180
"""Seconds to wait for the app to be back after it went away for the update."""


@dataclass(frozen=True, kw_only=True)
class ShellyElevateIntegrationUpdateDescription(ShellyElevateIntegrationEntityDescription, UpdateEntityDescription):
    """Update description."""


async def async_setup_entry(
    hass: HomeAssistant, entry: ShellyElevateIntegrationConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Set up the update entity."""
    async_add_entities(create_entities(entry.runtime_data), update_before_add=False)


def create_entities(device: ShellyElevateIntegrationDevice) -> list[UpdateEntity]:
    """The app update entity (always)."""
    return [ShellyElevateIntegrationAppUpdate(device)]


class ShellyElevateIntegrationAppUpdate(ShellyElevateIntegrationEntity, UpdateEntity):
    """ShellyElevate app version."""

    entity_description: ShellyElevateIntegrationUpdateDescription
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_should_poll = True
    _attr_title = "ShellyElevate"

    def __init__(self, device: ShellyElevateIntegrationDevice) -> None:
        """Initialize."""
        super().__init__(
            device,
            ShellyElevateIntegrationUpdateDescription(key="app_update", translation_key="app_update", state_keys=()),
        )
        self._release: AppRelease | None = None
        self._self_update: asyncio.Future[str | None] | None = None
        self._info_or_connection = asyncio.Event()

    @property
    def available(self) -> bool:
        """Available even when the app is down, as long as ADB can install."""
        return super().available or self.device.adb is not None

    @property
    def supported_features(self) -> UpdateEntityFeature:
        """Install only when there is a way to install."""
        features = UpdateEntityFeature.RELEASE_NOTES
        if self.device.info.capabilities.self_update or self.device.adb is not None:
            features |= UpdateEntityFeature.INSTALL | UpdateEntityFeature.SPECIFIC_VERSION
        return features

    @property
    def installed_version(self) -> str | None:
        """Running app version."""
        return self.device.info.fw_version

    @property
    def latest_version(self) -> str | None:
        """Latest release on the configured channel."""
        if self._release is None:
            return self.installed_version
        return self._release.version

    @property
    def release_url(self) -> str | None:
        """Release page."""
        return self._release.url if self._release else None

    def version_is_newer(self, latest_version: str, installed_version: str) -> bool:
        """Compare `3.YYDDD.HHMM` versions."""
        return version_key(latest_version) > version_key(installed_version)

    async def async_release_notes(self) -> str | None:
        """Release notes."""
        return self._release.notes if self._release else None

    async def async_added_to_hass(self) -> None:
        """Fetch the latest release once on startup."""
        await super().async_added_to_hass()
        self.async_on_remove(self.device.async_add_message_listener(self._on_message))
        self.async_on_remove(self.device.async_add_availability_listener(self._on_availability))
        self.hass.async_create_task(self.async_update_ha_state(force_refresh=True), eager_start=False)

    @callback
    def _on_message(self, message: dict[str, Any]) -> None:
        if message.get("type") == "event" and message.get("event") == "app_update":
            if message.get("status") == "failed":
                reason = str(message.get("reason") or "unknown")
                _LOGGER.warning("Updating the app on %s failed: %s", self.device.entry.title, reason)
                self._finish_self_update(reason)
        elif message.get("type") == "_info_changed":
            self._info_or_connection.set()
            self._finish_self_update(None)

    @callback
    def _on_availability(self) -> None:
        self._info_or_connection.set()
        if not self.device.available:
            # the app restarts to finish the update
            self._finish_self_update(None)

    @callback
    def _finish_self_update(self, error: str | None) -> None:
        if self._self_update is not None and not self._self_update.done():
            self._self_update.set_result(error)

    async def async_update(self) -> None:
        """Poll GitHub."""
        channel = self.device.entry.options.get(OPT_UPDATE_CHANNEL, UPDATE_CHANNEL_STABLE)
        try:
            self._release = await async_latest_release(self.hass, channel)
        except HomeAssistantError as err:
            _LOGGER.debug("Could not check for ShellyElevate updates: %s", err)

    async def async_install(self, version: str | None, backup: bool, **kwargs: Any) -> None:
        """Install the latest (or a specific) version."""
        release = self._release
        if version is not None:
            release = next((r for r in await async_get_releases(self.hass) if r.version == version), None)
            if release is None:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="version_not_found",
                    translation_placeholders={"version": version},
                )
        if release is None:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="no_release")
        if self.device.backups is not None and self.device.available:
            # Display settings are always snapshotted before an update (cheap and local).
            await self.device.client.get_settings()
            self.device.backups.snapshot(REASON_BEFORE_UPDATE)
        self._attr_in_progress = True
        self.async_write_ha_state()
        try:
            if self.device.info.capabilities.self_update and self.device.available:
                await self._async_self_update(release)
            elif self.device.adb is not None:
                await self.device.adb.async_install_app(release, post_install=False)
            else:
                raise HomeAssistantError(translation_domain=DOMAIN, translation_key="no_install_method")
            if self.device.permissions is not None:
                # a new version may need a permission the old one did not
                self.device.permissions.async_after_update()
        finally:
            self._attr_in_progress = False
            self.async_write_ha_state()

    async def _async_self_update(self, release: AppRelease) -> None:
        """Let the app update itself and wait until it runs the new version or reports a failure."""
        params: dict[str, Any] = {"url": release.apk_url, "version": release.version}
        if release.sha256 is not None:
            params["sha256"] = release.sha256
        self._self_update = done = self.hass.loop.create_future()
        try:
            await self.device.async_command("app.update", **params)
            async with asyncio.timeout(SELF_UPDATE_TIMEOUT):
                error = await done
        except TimeoutError as err:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="app_update_timeout") from err
        finally:
            self._self_update = None
        if error is not None:
            raise _update_failed(error)
        # a lost connection alone is no success: the app must come back with the new version
        if not await self._async_wait_until_back():
            raise _update_failed(f"the app did not come back within {RESTART_TIMEOUT} seconds")
        if version_key(self.device.info.fw_version) != version_key(release.version):
            raise _update_failed(f"the display still runs {self.device.info.fw_version}")

    async def _async_wait_until_back(self) -> bool:
        """Wait (bounded) until the display is connected again; False on timeout."""
        try:
            async with asyncio.timeout(RESTART_TIMEOUT):
                while not self.device.available:
                    self._info_or_connection.clear()
                    await self._info_or_connection.wait()
        except TimeoutError:
            return False
        return True


def _update_failed(reason: str) -> HomeAssistantError:
    return HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="app_update_failed",
        translation_placeholders={"reason": reason},
    )
