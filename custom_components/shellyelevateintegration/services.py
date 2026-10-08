"""Actions (services) of Shelly Elevate."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.service import async_register_admin_service
import voluptuous as vol

from .adb.apk import async_get_releases
from .const import DOMAIN, OPT_UPDATE_CHANNEL, UPDATE_CHANNEL_STABLE
from .device import ShellyElevateIntegrationDevice
from .revert import RevertOptions, async_revert
from .settings import schema as schema_util
from .settings.backups import REASON_BEFORE_PROFILE, BackupManager
from .settings.profiles import async_get_profile_manager

ATTR_NAME = "name"
ATTR_BACKUP_ID = "backup_id"
ATTR_KEYS = "keys"
ATTR_PROFILE = "profile"
ATTR_MAKE_DEFAULT = "make_default"
ATTR_SOURCE = "source_device_id"
ATTR_SETTINGS = "settings"
ATTR_INCLUDE_SECRETS = "include_secrets"
ATTR_APPLY = "apply"
ATTR_PATH = "path"
ATTR_URL = "url"
ATTR_MESSAGE = "message"
ATTR_TITLE = "title"
ATTR_DURATION = "duration"
ATTR_LEVEL = "level"
ATTR_COMMAND = "command"
ATTR_VERSION = "version"
ATTR_REBOOT = "reboot"
ATTR_DISABLE_ADB = "disable_adb"
ATTR_REMOVE = "remove_from_home_assistant"
ATTR_ACCEPT_WIFI = "accept_wifi_loss"

STRING_LIST = vol.All(cv.ensure_list, [cv.string])

SERVICE_BACKUP = "backup_settings"
SERVICE_RESTORE = "restore_settings"
SERVICE_APPLY_PROFILE = "apply_profile"
SERVICE_SAVE_PROFILE = "save_profile"
SERVICE_COPY = "copy_settings"
SERVICE_EXPORT = "export_settings"
SERVICE_IMPORT = "import_settings"
SERVICE_GET = "get_settings"
SERVICE_SET = "set_settings"
SERVICE_NAVIGATE = "navigate"
SERVICE_MESSAGE = "show_message"
SERVICE_ADB_SHELL = "adb_shell"
SERVICE_INSTALL_APP = "install_app"
SERVICE_REVERT = "revert_display"


def _get_device(hass: HomeAssistant, device_id: str) -> ShellyElevateIntegrationDevice:
    """Resolve a device registry id to a loaded display."""
    device_entry = dr.async_get(hass).async_get(device_id)
    if device_entry is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="device_not_found",
            translation_placeholders={"device": device_id},
        )
    entry_ids = (
        [device_entry.config_entry_id]
        if getattr(device_entry, "config_entry_id", None)
        else list(getattr(device_entry, "config_entries", ()))
    )
    for entry_id in entry_ids:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is not None and entry.domain == DOMAIN:
            if entry.state is not ConfigEntryState.LOADED:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="device_not_loaded",
                    translation_placeholders={"device": device_entry.name or device_id},
                )
            return entry.runtime_data
    raise ServiceValidationError(
        translation_domain=DOMAIN, translation_key="device_not_found", translation_placeholders={"device": device_id}
    )


def _devices(hass: HomeAssistant, call: ServiceCall) -> list[ShellyElevateIntegrationDevice]:
    return [_get_device(hass, device_id) for device_id in call.data[ATTR_DEVICE_ID]]


def _backups(device: ShellyElevateIntegrationDevice) -> BackupManager:
    assert device.backups is not None
    return device.backups


async def async_apply_profile(
    hass: HomeAssistant, device: ShellyElevateIntegrationDevice, profile: str
) -> list[dict[str, Any]]:
    """Apply a profile to a display; returns the applied changes."""
    manager = await async_get_profile_manager(hass)
    changes = await async_profile_diff(hass, device, manager.find(profile))
    if changes:
        _backups(device).snapshot(REASON_BEFORE_PROFILE)
        await device.async_set_settings({item["key"]: item["new"] for item in changes})
    return changes


async def async_profile_diff(
    hass: HomeAssistant, device: ShellyElevateIntegrationDevice, profile_id: str
) -> list[dict[str, Any]]:
    """What applying a profile would change on a display."""
    manager = await async_get_profile_manager(hass)
    await device.async_refresh_settings()
    target = manager.settings_for_device(profile_id, await device.async_get_schema(), await device.async_known_keys())
    return schema_util.diff(device.settings, target)


async def async_copy_settings(
    source: ShellyElevateIntegrationDevice, targets: list[ShellyElevateIntegrationDevice], keys: list[str] | None
) -> dict[str, Any]:
    """Copy portable settings from one display to others; one failing target doesn't stop the rest."""
    await source.async_refresh_settings()
    settings = schema_util.portable(source.settings, await source.async_get_schema())
    if keys:
        settings = {k: v for k, v in settings.items() if k in keys}
    results: dict[str, list[dict[str, Any]]] = {}
    errors: dict[str, str] = {}
    for target in targets:
        if target is source:
            continue
        key = target.device_entry_id or target.device_id
        try:
            await target.async_refresh_settings()
            portable = schema_util.portable(settings, await target.async_get_schema())
            known = await target.async_known_keys()
            changes = schema_util.diff(target.settings, {k: v for k, v in portable.items() if k in known})
            if changes:
                _backups(target).snapshot(REASON_BEFORE_PROFILE)
                await target.async_set_settings({item["key"]: item["new"] for item in changes})
        except HomeAssistantError as err:
            errors[key] = str(err)
            continue
        results[key] = changes
    return {"results": results, "errors": errors}


async def async_export_payload(device: ShellyElevateIntegrationDevice, include_secrets: bool) -> dict[str, Any]:
    """Settings export format (`import_settings` accepts it back)."""
    await device.async_refresh_settings()
    settings = dict(device.settings)
    if not include_secrets:
        secrets = schema_util.secret_keys(await device.async_get_schema())
        settings = {k: v for k, v in settings.items() if k not in secrets}
    info = device.info
    return {
        "format": "shellyelevateintegration.settings/1",
        "exported": datetime.now(UTC).isoformat(),
        "device": {"id": info.device_id, "name": device.entry.title, "model": info.model, "fw": info.fw_version},
        "settings": settings,
    }


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register actions."""

    async def backup(call: ServiceCall) -> ServiceResponse:
        out = []
        for device in _devices(hass, call):
            item = await _backups(device).async_backup(call.data.get(ATTR_NAME))
            out.append({"device_id": device.device_entry_id, "backup_id": item["id"], "created": item["created"]})
        return {"backups": out}

    async def restore(call: ServiceCall) -> ServiceResponse:
        device = _get_device(hass, call.data[ATTR_DEVICE_ID])
        changes = await _backups(device).async_restore(call.data.get(ATTR_BACKUP_ID), call.data.get(ATTR_KEYS))
        return {"changes": changes}

    async def apply_profile(call: ServiceCall) -> ServiceResponse:
        return {
            "results": {
                device.device_entry_id: await async_apply_profile(hass, device, call.data[ATTR_PROFILE])
                for device in _devices(hass, call)
            }
        }

    async def save_profile(call: ServiceCall) -> ServiceResponse:
        device = _get_device(hass, call.data[ATTR_DEVICE_ID])
        await device.async_refresh_settings()
        settings = dict(device.settings)
        if keys := call.data.get(ATTR_KEYS):
            settings = {k: v for k, v in settings.items() if k in keys}
        manager = await async_get_profile_manager(hass)
        name = call.data[ATTR_NAME].casefold()
        existing = next((p["id"] for p in manager.as_list() if p["name"].casefold() == name), None)
        profile_id = await manager.async_save_profile(
            call.data[ATTR_NAME],
            settings,
            profile_id=existing,
            schema=await device.async_get_schema(),
            make_default=call.data.get(ATTR_MAKE_DEFAULT),
        )
        return {"profile_id": profile_id}

    async def copy(call: ServiceCall) -> ServiceResponse:
        source = _get_device(hass, call.data[ATTR_SOURCE])
        return await async_copy_settings(source, _devices(hass, call), call.data.get(ATTR_KEYS))

    async def export(call: ServiceCall) -> ServiceResponse:
        device = _get_device(hass, call.data[ATTR_DEVICE_ID])
        return await async_export_payload(device, call.data[ATTR_INCLUDE_SECRETS])

    async def import_settings(call: ServiceCall) -> ServiceResponse:
        device = _get_device(hass, call.data[ATTR_DEVICE_ID])
        payload = call.data[ATTR_SETTINGS]
        settings = payload.get("settings", payload) if isinstance(payload, dict) else {}
        if not isinstance(settings, dict) or not settings:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="invalid_import")
        backups = _backups(device)
        portable = schema_util.portable(settings, await device.async_get_schema())
        backup = backups.store.import_backup(
            device.device_id,
            {"settings": portable, "name": call.data.get(ATTR_NAME)},
            backups.keep,
        )
        changes: list[dict[str, Any]] = []
        if call.data[ATTR_APPLY]:
            changes = await backups.async_restore(backup["id"])
        return {"backup_id": backup["id"], "changes": changes}

    async def get_settings(call: ServiceCall) -> ServiceResponse:
        device = _get_device(hass, call.data[ATTR_DEVICE_ID])
        await device.async_refresh_settings()
        return {"settings": schema_util.redact(device.settings, await device.async_get_schema())}

    async def set_settings(call: ServiceCall) -> None:
        for device in _devices(hass, call):
            await device.async_set_settings(dict(call.data[ATTR_SETTINGS]))

    async def navigate(call: ServiceCall) -> None:
        if not (ATTR_PATH in call.data) ^ (ATTR_URL in call.data):
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="path_or_url")
        params = {k: call.data[k] for k in (ATTR_PATH, ATTR_URL) if k in call.data}
        for device in _devices(hass, call):
            await device.async_command("webview.navigate", **params)

    async def message(call: ServiceCall) -> None:
        params = {k: call.data[k] for k in (ATTR_MESSAGE, ATTR_TITLE, ATTR_DURATION, ATTR_LEVEL) if k in call.data}
        for device in _devices(hass, call):
            await device.async_command("ui.notify", **params)

    async def adb_shell(call: ServiceCall) -> ServiceResponse:
        device = _get_device(hass, call.data[ATTR_DEVICE_ID])
        if device.adb is None:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="adb_disabled")
        return {"output": await device.adb.async_shell(call.data[ATTR_COMMAND], timeout=60)}

    async def install_app(call: ServiceCall) -> ServiceResponse:
        device = _get_device(hass, call.data[ATTR_DEVICE_ID])
        if device.adb is None:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="adb_disabled")
        release = None
        if version := call.data.get(ATTR_VERSION):
            release = next((r for r in await async_get_releases(hass) if r.version == version), None)
            if release is None:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="version_not_found",
                    translation_placeholders={"version": version},
                )
        installed = await device.adb.async_install_app(
            release, device.entry.options.get(OPT_UPDATE_CHANNEL, UPDATE_CHANNEL_STABLE), post_install=False
        )
        if device.permissions is not None:
            device.permissions.async_after_update()
        return {"version": installed.version}

    async def revert_display(call: ServiceCall) -> ServiceResponse:
        device = _get_device(hass, call.data[ATTR_DEVICE_ID])
        options = RevertOptions(
            host=device.client.host,
            remove_entry=call.data[ATTR_REMOVE],
            reboot=call.data[ATTR_REBOOT],
            disable_adb=call.data[ATTR_DISABLE_ADB],
            accept_wifi_loss=call.data[ATTR_ACCEPT_WIFI],
        )
        return await async_revert(hass, options, lambda step, data: None)

    one = {vol.Required(ATTR_DEVICE_ID): cv.string}
    many = {vol.Required(ATTR_DEVICE_ID): STRING_LIST}

    def register_admin(
        service: str,
        handler: Callable[[ServiceCall], Awaitable[ServiceResponse | None]],
        schema: vol.Schema,
        supports_response: SupportsResponse = SupportsResponse.NONE,
    ) -> None:
        async_register_admin_service(hass, DOMAIN, service, handler, schema, supports_response=supports_response)

    # Actions that change, store or reveal settings (secrets included) are admin-only.
    register = hass.services.async_register
    register(
        DOMAIN,
        SERVICE_BACKUP,
        backup,
        vol.Schema({**many, vol.Optional(ATTR_NAME): cv.string}),
        supports_response=SupportsResponse.OPTIONAL,
    )
    register_admin(
        SERVICE_RESTORE,
        restore,
        vol.Schema({**one, vol.Optional(ATTR_BACKUP_ID): cv.string, vol.Optional(ATTR_KEYS): STRING_LIST}),
        supports_response=SupportsResponse.OPTIONAL,
    )
    register_admin(
        SERVICE_APPLY_PROFILE,
        apply_profile,
        vol.Schema({**many, vol.Required(ATTR_PROFILE): cv.string}),
        supports_response=SupportsResponse.OPTIONAL,
    )
    register_admin(
        SERVICE_SAVE_PROFILE,
        save_profile,
        vol.Schema(
            {
                **one,
                vol.Required(ATTR_NAME): cv.string,
                vol.Optional(ATTR_MAKE_DEFAULT): cv.boolean,
                vol.Optional(ATTR_KEYS): STRING_LIST,
            }
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )
    register_admin(
        SERVICE_COPY,
        copy,
        vol.Schema({vol.Required(ATTR_SOURCE): cv.string, **many, vol.Optional(ATTR_KEYS): STRING_LIST}),
        supports_response=SupportsResponse.OPTIONAL,
    )
    register_admin(
        SERVICE_EXPORT,
        export,
        vol.Schema({**one, vol.Optional(ATTR_INCLUDE_SECRETS, default=False): cv.boolean}),
        supports_response=SupportsResponse.ONLY,
    )
    register_admin(
        SERVICE_IMPORT,
        import_settings,
        vol.Schema(
            {
                **one,
                vol.Required(ATTR_SETTINGS): dict,
                vol.Optional(ATTR_NAME): cv.string,
                vol.Optional(ATTR_APPLY, default=False): cv.boolean,
            }
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )
    register(DOMAIN, SERVICE_GET, get_settings, vol.Schema(one), supports_response=SupportsResponse.ONLY)
    register_admin(SERVICE_SET, set_settings, vol.Schema({**many, vol.Required(ATTR_SETTINGS): dict}))
    register(
        DOMAIN,
        SERVICE_NAVIGATE,
        navigate,
        vol.Schema({**many, vol.Optional(ATTR_PATH): cv.string, vol.Optional(ATTR_URL): cv.url}),
    )
    register(
        DOMAIN,
        SERVICE_MESSAGE,
        message,
        vol.Schema(
            {
                **many,
                vol.Required(ATTR_MESSAGE): cv.string,
                vol.Optional(ATTR_TITLE): cv.string,
                vol.Optional(ATTR_DURATION): vol.All(vol.Coerce(float), vol.Range(0.5, 3600)),
                vol.Optional(ATTR_LEVEL): vol.In(["info", "warning", "alert"]),
            }
        ),
    )
    register_admin(
        SERVICE_ADB_SHELL,
        adb_shell,
        vol.Schema({**one, vol.Required(ATTR_COMMAND): cv.string}),
        supports_response=SupportsResponse.ONLY,
    )
    register_admin(
        SERVICE_REVERT,
        revert_display,
        vol.Schema(
            {
                **one,
                vol.Optional(ATTR_REMOVE, default=True): cv.boolean,
                vol.Optional(ATTR_REBOOT, default=True): cv.boolean,
                vol.Optional(ATTR_DISABLE_ADB, default=False): cv.boolean,
                vol.Optional(ATTR_ACCEPT_WIFI, default=False): cv.boolean,
            }
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )
    register_admin(
        SERVICE_INSTALL_APP,
        install_app,
        vol.Schema({**one, vol.Optional(ATTR_VERSION): cv.string}),
        supports_response=SupportsResponse.OPTIONAL,
    )
