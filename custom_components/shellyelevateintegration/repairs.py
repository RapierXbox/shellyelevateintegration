"""Repair issues and fix flows."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.repairs import RepairsFlow, RepairsFlowResult
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN, OPT_ADB, OPT_UPDATE_CHANNEL, UPDATE_CHANNEL_STABLE

if TYPE_CHECKING:
    # ha 2026.9+ aliases voluptuous to probatio at runtime
    import probatio as vol

    from .device import ShellyElevateIntegrationConfigEntry, ShellyElevateIntegrationDevice
else:
    import voluptuous as vol

ISSUE_LEGACY_APP = "legacy_app"
ISSUE_DUPLICATES = "duplicate_devices"
ISSUE_LEGACY_HTTP = "legacy_http_api"
ISSUE_APP_DOWN = "app_unreachable"
ISSUE_PERMISSIONS = "permissions_missing"

LEGACY_HTTP_KEY = "httpServer"
"""The app's switch for its unauthenticated HTTP API on port 8080."""


def _issue_id(kind: str, entry_id: str) -> str:
    return f"{kind}_{entry_id}"


@callback
def _async_update_issue(
    hass: HomeAssistant,
    kind: str,
    device: ShellyElevateIntegrationDevice,
    active: bool,
    *,
    fixable: bool = True,
    severity: ir.IssueSeverity = ir.IssueSeverity.WARNING,
    learn_more_url: str | None = None,
    placeholders: dict[str, str] | None = None,
) -> None:
    """Create or delete the issue `kind` of a display; fixable issues get a fix flow."""
    entry_id = device.entry.entry_id
    issue_id = _issue_id(kind, entry_id)
    if not active:
        ir.async_delete_issue(hass, DOMAIN, issue_id)
        return
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=fixable,
        severity=severity,
        translation_key=kind,
        translation_placeholders={"name": device.entry.title, **(placeholders or {})},
        learn_more_url=learn_more_url,
        data={"entry_id": entry_id, "fix": kind} if fixable else None,
    )


@callback
def async_check_issues(hass: HomeAssistant, device: ShellyElevateIntegrationDevice) -> None:
    """(Re)evaluate the setting-based issues of a display."""
    _async_update_issue(
        hass,
        ISSUE_LEGACY_APP,
        device,
        device.legacy,
        fixable=False,
        learn_more_url="https://github.com/RapierXbox/ShellyElevate/releases",
    )
    if device.legacy:
        return
    settings = device.settings
    _async_update_issue(hass, ISSUE_DUPLICATES, device, bool(_duplicate_fix(settings)))
    _async_update_issue(hass, ISSUE_LEGACY_HTTP, device, bool(settings.get(LEGACY_HTTP_KEY)))


def _duplicate_fix(settings: dict[str, Any]) -> dict[str, Any]:
    """Settings that would remove the second device; empty when there is none."""
    changes = {}
    # discovery only creates a device while MQTT itself is on
    if settings.get("mqttEnabled") and settings.get("mqttHomeAssistantDiscovery"):
        changes["mqttHomeAssistantDiscovery"] = False
    # the app ESPHome proxy (older app versions only) adds an ESPHome device
    # the fix moves the display to the proxy that runs through this integration
    if settings.get("bluetoothProxyEnabled"):
        changes["bluetoothProxyEnabled"] = False
        if "bleScannerEnabled" in settings:
            changes["bleScannerEnabled"] = True
    return changes


@callback
def async_set_app_down(hass: HomeAssistant, device: ShellyElevateIntegrationDevice, down: bool) -> None:
    """App does not answer but ADB does: offer a restart / reinstall."""
    _async_update_issue(hass, ISSUE_APP_DOWN, device, down, severity=ir.IssueSeverity.ERROR)


@callback
def async_set_permissions_missing(
    hass: HomeAssistant, device: ShellyElevateIntegrationDevice, problems: list[str] | None
) -> None:
    """The display reports missing permissions that could not be granted automatically."""
    _async_update_issue(
        hass,
        ISSUE_PERMISSIONS,
        device,
        bool(problems),
        placeholders={"problems": ", ".join(problems or ())},
    )


class SettingsFixFlow(RepairsFlow):
    """Apply settings that resolve an issue."""

    def __init__(self, entry_id: str, fix: str) -> None:
        """Initialize."""
        self.entry_id = entry_id
        self.fix = fix

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> RepairsFlowResult:
        """Start the fix flow."""
        if self.fix == ISSUE_PERMISSIONS:
            return await self.async_step_permissions()
        return await self.async_step_confirm()

    def _device(self) -> ShellyElevateIntegrationDevice | None:
        entry: ShellyElevateIntegrationConfigEntry | None = self.hass.config_entries.async_get_entry(self.entry_id)
        if entry is None or entry.state is not ConfigEntryState.LOADED:
            return None
        return entry.runtime_data

    async def async_step_permissions(self, user_input: dict[str, Any] | None = None) -> RepairsFlowResult:
        """Grant the missing permissions over ADB (or explain how to enable ADB first)."""
        if (device := self._device()) is None:
            return self.async_abort(reason="not_loaded")
        if device.adb is None:
            return await self.async_step_enable_adb()
        if user_input is None:
            return self.async_show_form(
                step_id="permissions", description_placeholders=_permission_placeholders(device)
            )
        return await self._async_grant(device)

    async def async_step_enable_adb(self, user_input: dict[str, Any] | None = None) -> RepairsFlowResult:
        """ADB is off for this display: explain how to turn it on, then try it."""
        if (device := self._device()) is None:
            return self.async_abort(reason="not_loaded")
        if user_input is None:
            return self.async_show_form(
                step_id="enable_adb",
                description_placeholders={**_permission_placeholders(device), "host": device.client.host},
            )
        from .adb.manager import async_create_adb_manager

        adb = await async_create_adb_manager(self.hass, device.client.host)
        # the display may ask to allow debugging for the key of home assistant
        if not await adb.async_is_reachable(auth_timeout=60):
            return self.async_abort(reason="adb_unreachable", description_placeholders={"host": device.client.host})
        if device.adb is not None:
            return await self._async_grant(device)
        # adb works so use it from now on (updates and later grants)
        from .adb.manager import async_get_adb_manager

        entry = device.entry
        self.hass.config_entries.async_update_entry(entry, options={**entry.options, OPT_ADB: True})
        device.adb = await async_get_adb_manager(self.hass, device)
        try:
            return await self._async_grant(device)
        finally:
            # the screenshot image and the grant permissions button only exist with adb
            self.hass.config_entries.async_schedule_reload(entry.entry_id)

    async def _async_grant(self, device: ShellyElevateIntegrationDevice) -> RepairsFlowResult:
        if device.permissions is None:
            return self.async_abort(reason="not_loaded")
        try:
            result = await device.permissions.async_grant()
        except HomeAssistantError as err:
            return self.async_abort(reason="cannot_connect", description_placeholders={"error": str(err)})
        if result.missing:
            return self.async_abort(
                reason="still_missing", description_placeholders={"missing": ", ".join(result.missing)}
            )
        # the app restarts and reports the state again which clears the issue
        async_set_permissions_missing(self.hass, device, None)
        return self.async_create_entry(data={})

    async def async_step_confirm(self, user_input: dict[str, Any] | None = None) -> RepairsFlowResult:
        """Confirm and apply."""
        entry: ShellyElevateIntegrationConfigEntry | None = self.hass.config_entries.async_get_entry(self.entry_id)
        if entry is None or entry.state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="not_loaded")
        device = entry.runtime_data
        if user_input is not None:
            try:
                if self.fix == ISSUE_DUPLICATES:
                    if changes := _duplicate_fix(device.settings):
                        await device.async_set_settings(changes)
                elif self.fix == ISSUE_LEGACY_HTTP:
                    await device.async_set_settings({LEGACY_HTTP_KEY: False})
                elif self.fix == ISSUE_APP_DOWN:
                    if device.adb is None:
                        return self.async_abort(reason="no_adb")
                    if user_input.get("reinstall"):
                        # reads the android version itself for the permission steps
                        await device.adb.async_install_app(
                            channel=entry.options.get(OPT_UPDATE_CHANNEL, UPDATE_CHANNEL_STABLE)
                        )
                    else:
                        await device.adb.async_restart_app()
            except HomeAssistantError:
                async_check_issues(self.hass, device)
                return self.async_abort(reason="cannot_connect")
            async_check_issues(self.hass, device)
            return self.async_create_entry(data={})
        schema = vol.Schema({vol.Optional("reinstall", default=False): bool}) if self.fix == ISSUE_APP_DOWN else None
        return self.async_show_form(
            step_id="confirm", data_schema=schema, description_placeholders={"name": entry.title}
        )


def _permission_placeholders(device: ShellyElevateIntegrationDevice) -> dict[str, str]:
    from .permissions import permission_problems

    # the guard also knows what only the adb check finds
    guard = device.permissions
    problems = guard.problems() if guard is not None else permission_problems(device.state)
    return {"name": device.entry.title, "problems": ", ".join(problems) or "-"}


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, str | int | float | None] | None
) -> RepairsFlow:
    """Create a fix flow."""
    assert data is not None
    return SettingsFixFlow(str(data["entry_id"]), str(data["fix"]))
