"""Websocket API for the Shelly Elevate panel (admin only)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import functools
from typing import Any

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
import voluptuous as vol

from .adb.apk import async_get_releases
from .api import ShellyElevateIntegrationError
from .api.app_schema import app_schema
from .const import DOMAIN, SIGNAL_SETTINGS_CHANGED, is_panel_entry
from .device import ShellyElevateIntegrationDevice
from .installer import ProvisionOptions, async_provision, default_dashboard_url
from .revert import RevertOptions, async_revert, async_revert_check
from .services import async_apply_profile, async_copy_settings, async_export_payload, async_profile_diff
from .settings import schema as schema_util
from .settings.backups import async_get_backup_store
from .settings.profiles import async_get_profile_manager


def _device(hass: HomeAssistant, entry_id: str) -> ShellyElevateIntegrationDevice:
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.domain != DOMAIN or is_panel_entry(entry) or entry.state is not ConfigEntryState.LOADED:
        raise HomeAssistantError(f"Display {entry_id} is not loaded")
    return entry.runtime_data


def _device_summary(device: ShellyElevateIntegrationDevice) -> dict[str, Any]:
    info = device.info
    return {
        "entry_id": device.entry.entry_id,
        "device_id": device.device_entry_id,
        "display_id": info.device_id,
        "name": device.entry.title,
        "model": info.model_name,
        "sku": info.model,
        "fw_version": info.fw_version,
        "api_version": info.api_version,
        "host": device.client.host,
        "legacy": device.legacy,
        "available": device.available,
        "adb": device.adb is not None,
        "capabilities": info.capabilities.as_dict(),
    }


def _guess_type(value: Any) -> str:
    """Setting type for a value the schema does not describe."""
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, list):
        return "string_list"
    return "string"


REMOVED_KEYS = frozenset(
    {
        "bluetoothProxyEnabled",
        "bluetoothProxyName",
        "voiceAssistantEnabled",
        "voiceAssistantToken",
        "voiceAssistantPipelineId",
        "deprecatedMigrationPrompted",
    }
)
"""Keys of features the app removed (RemovedSettings.java); never listed as undescribed settings."""


def _managed_settings(device: ShellyElevateIntegrationDevice, keys: set[str]) -> dict[str, str]:
    """Settings the integration controls itself (key -> reason), shown read-only in the panel."""
    managed: dict[str, str] = {}
    if device.legacy:
        # older apps use the mqtt id as the display id
        managed["mqttDeviceId"] = "Identifies the display in Home Assistant"
        managed["httpServer"] = "Home Assistant connects to this display through the legacy HTTP server"
    else:
        managed["integrationApiEnabled"] = "Turning it off disconnects this display from Home Assistant"
    if device.voice_enabled:
        reason = "Set by the wake word of the Assist satellite in Home Assistant"
        managed["voiceWakeEnabled"] = reason
        managed["voiceWakeModelName"] = reason
    return {key: reason for key, reason in managed.items() if key in keys}


type _CommandFn = Callable[[HomeAssistant, websocket_api.ActiveConnection, dict[str, Any]], Awaitable[dict[str, Any]]]


def _cmd(schema: dict[Any, Any]) -> Callable[[_CommandFn], websocket_api.WebSocketCommandHandler]:
    """Admin-only async command; the return value is the result, HomeAssistantError an error."""

    def decorator(fn: _CommandFn) -> websocket_api.WebSocketCommandHandler:
        @functools.wraps(fn)
        async def handler(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
            try:
                result = await fn(hass, connection, msg)
            except (HomeAssistantError, ShellyElevateIntegrationError) as err:
                connection.send_error(msg["id"], "failed", str(err))
                return
            connection.send_result(msg["id"], result)

        return websocket_api.websocket_command(schema)(
            websocket_api.require_admin(websocket_api.async_response(handler))
        )

    return decorator


# --------------------------------------------------------------------------- devices / settings


@_cmd({vol.Required("type"): f"{DOMAIN}/devices"})
async def ws_devices(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> dict[str, Any]:
    """List displays (including not loaded ones)."""
    out = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        if is_panel_entry(entry):
            continue
        if entry.state is ConfigEntryState.LOADED:
            out.append(_device_summary(entry.runtime_data))
        else:
            out.append(
                {"entry_id": entry.entry_id, "name": entry.title, "available": False, "state": entry.state.value}
            )
    return {"devices": out}


@_cmd({vol.Required("type"): f"{DOMAIN}/settings/get", vol.Required("entry_id"): str})
async def ws_settings_get(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> dict[str, Any]:
    """Settings + schema of a display."""
    device = _device(hass, msg["entry_id"])
    await device.async_refresh_settings()
    schema = await device.async_get_schema()
    rules = schema
    if not schema and not device.legacy:
        # without the schema of the display the rules of the app (like device.visibility)
        rules = app_schema(set(device.settings), undescribed=False)
    known = {item.key for item in rules or ()}
    # undescribed keys stay editable as raw values in a collapsed section of the panel
    extra = [
        {"key": k, "type": _guess_type(v), "category": "other", "label": k}
        for k, v in device.settings.items()
        if k not in known and k not in REMOVED_KEYS
    ]
    return {
        "settings": device.settings,
        "schema": [item.as_dict() for item in rules or ()] + extra,
        "per_device": sorted(schema_util.per_device_keys(schema)),
        "secret": sorted(schema_util.secret_keys(schema)),
        "capabilities": device.capabilities,
        # requires on a capability outside this list counts as met
        "known_caps": sorted(device.known_caps),
        # legacy displays may report values as strings so the panel compares loosely
        "legacy": device.legacy,
        "managed": _managed_settings(device, known | set(device.settings)),
    }


@_cmd({vol.Required("type"): f"{DOMAIN}/settings/set", vol.Required("entry_id"): str, vol.Required("changes"): dict})
async def ws_settings_set(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> dict[str, Any]:
    """Write settings; `ignored` lists the keys the display does not know (not written)."""
    device = _device(hass, msg["entry_id"])
    result = await device.async_set_settings(msg["changes"])
    return {"settings": result.settings, "ignored": result.ignored}


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/settings/subscribe", vol.Required("entry_id"): str})
@websocket_api.require_admin
@callback
def ws_settings_subscribe(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Forward the setting changes of one display (from Home Assistant or the display itself).

    Keeps working while the entry reloads (the panel reads all settings again after a reconnect).
    """
    msg_id = msg["id"]
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    if entry is None or entry.domain != DOMAIN or is_panel_entry(entry):
        connection.send_error(msg_id, "not_found", f"Display {msg['entry_id']} not found")
        return

    @callback
    def forward(changes: dict[str, Any]) -> None:
        if changes:
            connection.send_message(websocket_api.event_message(msg_id, {"changes": changes}))

    connection.subscriptions[msg_id] = async_dispatcher_connect(
        hass, SIGNAL_SETTINGS_CHANGED.format(entry.entry_id), forward
    )
    connection.send_result(msg_id)


@_cmd(
    {
        vol.Required("type"): f"{DOMAIN}/settings/export",
        vol.Required("entry_id"): str,
        vol.Optional("include_secrets", default=False): bool,
    }
)
async def ws_export(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> dict[str, Any]:
    """Export settings."""
    device = _device(hass, msg["entry_id"])
    return await async_export_payload(device, msg["include_secrets"])


@_cmd(
    {
        vol.Required("type"): f"{DOMAIN}/settings/copy",
        vol.Required("source"): str,
        vol.Required("targets"): [str],
        vol.Optional("keys"): [str],
    }
)
async def ws_copy(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> dict[str, Any]:
    """Copy settings between displays."""
    source = _device(hass, msg["source"])
    targets = [_device(hass, entry_id) for entry_id in msg["targets"]]
    return await async_copy_settings(source, targets, msg.get("keys"))


@_cmd(
    {
        vol.Required("type"): f"{DOMAIN}/command",
        vol.Required("entry_ids"): [str],
        vol.Required("action"): str,
        vol.Optional("params", default={}): dict,
    }
)
async def ws_command(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> dict[str, Any]:
    """Run a command on one or more displays (fleet actions)."""
    results: dict[str, Any] = {}
    for entry_id in msg["entry_ids"]:
        try:
            results[entry_id] = {
                "ok": True,
                "data": await _device(hass, entry_id).async_command(msg["action"], **msg["params"]),
            }
        except HomeAssistantError as err:
            results[entry_id] = {"ok": False, "error": str(err)}
    return {"results": results}


# --------------------------------------------------------------------------- backups


@_cmd({vol.Required("type"): f"{DOMAIN}/backups/list", vol.Optional("entry_id"): str})
async def ws_backups_list(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> dict[str, Any]:
    """Backups of one display, or of all (also of displays that were removed)."""
    store = await async_get_backup_store(hass)
    if entry_id := msg.get("entry_id"):
        device = _device(hass, entry_id)
        return {"backups": {device.device_id: store.list(device.device_id)}}
    return {"backups": {device_id: store.list(device_id) for device_id in store.backups}}


@_cmd({vol.Required("type"): f"{DOMAIN}/backups/create", vol.Required("entry_id"): str, vol.Optional("name"): str})
async def ws_backups_create(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> dict[str, Any]:
    """Create a backup."""
    device = _device(hass, msg["entry_id"])
    assert device.backups is not None
    return {"backup": await device.backups.async_backup(msg.get("name"))}


@_cmd(
    {
        vol.Required("type"): f"{DOMAIN}/backups/diff",
        vol.Required("entry_id"): str,
        vol.Optional("backup_id"): str,
        vol.Optional("source_device_id"): str,
    }
)
async def ws_backups_diff(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> dict[str, Any]:
    """What restoring a backup would change (backup may come from another display)."""
    device = _device(hass, msg["entry_id"])
    store = await async_get_backup_store(hass)
    backup = store.get(msg.get("source_device_id") or device.device_id, msg.get("backup_id"))
    await device.async_refresh_settings()
    settings = backup["settings"]
    if msg.get("source_device_id") and msg["source_device_id"] != device.device_id:
        settings = schema_util.portable(settings, await device.async_get_schema())
    target = {k: v for k, v in settings.items() if k in device.settings}
    return {"diff": schema_util.diff(device.settings, target)}


@_cmd(
    {
        vol.Required("type"): f"{DOMAIN}/backups/restore",
        vol.Required("entry_id"): str,
        vol.Optional("backup_id"): str,
        vol.Optional("source_device_id"): str,
        vol.Optional("keys"): [str],
    }
)
async def ws_backups_restore(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> dict[str, Any]:
    """Restore (selected keys of) a backup."""
    device = _device(hass, msg["entry_id"])
    assert device.backups is not None
    source = msg.get("source_device_id")
    if source and source != device.device_id:
        # Apply another display's backup directly; importing it would add a named backup each time.
        backup = device.backups.store.get(source, msg.get("backup_id"))
        settings = schema_util.portable(backup["settings"], await device.async_get_schema())
        return {"changes": await device.backups.async_apply(settings, msg.get("keys"))}
    return {"changes": await device.backups.async_restore(msg.get("backup_id"), msg.get("keys"))}


@_cmd(
    {vol.Required("type"): f"{DOMAIN}/backups/delete", vol.Required("device_id"): str, vol.Required("backup_id"): str}
)
async def ws_backups_delete(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> dict[str, Any]:
    """Delete a backup."""
    store = await async_get_backup_store(hass)
    store.delete(msg["device_id"], msg["backup_id"])
    return {}


# --------------------------------------------------------------------------- profiles


@_cmd({vol.Required("type"): f"{DOMAIN}/profiles/list"})
async def ws_profiles_list(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> dict[str, Any]:
    """List profiles."""
    manager = await async_get_profile_manager(hass)
    return {"profiles": manager.as_list(), "default": manager.default_profile_id}


@_cmd(
    {
        vol.Required("type"): f"{DOMAIN}/profiles/save",
        vol.Optional("profile_id"): str,
        vol.Required("name"): str,
        vol.Optional("settings"): dict,
        vol.Optional("from_entry_id"): str,
        vol.Optional("keys"): [str],
        vol.Optional("make_default"): bool,
    }
)
async def ws_profiles_save(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> dict[str, Any]:
    """Create/update a profile from explicit settings or from a display."""
    manager = await async_get_profile_manager(hass)
    settings = dict(msg.get("settings") or {})
    schema = None
    if from_entry := msg.get("from_entry_id"):
        device = _device(hass, from_entry)
        await device.async_refresh_settings()
        settings = {**device.settings, **settings}
        schema = await device.async_get_schema()
    if keys := msg.get("keys"):
        settings = {k: v for k, v in settings.items() if k in keys}
    profile_id = await manager.async_save_profile(
        msg["name"],
        settings,
        profile_id=msg.get("profile_id"),
        schema=schema,
        make_default=msg.get("make_default"),
    )
    return {"profile_id": profile_id}


@_cmd({vol.Required("type"): f"{DOMAIN}/profiles/delete", vol.Required("profile_id"): str})
async def ws_profiles_delete(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> dict[str, Any]:
    """Delete a profile."""
    await (await async_get_profile_manager(hass)).async_delete(msg["profile_id"])
    return {}


@_cmd({vol.Required("type"): f"{DOMAIN}/profiles/set_default", vol.Optional("profile_id"): vol.Any(str, None)})
async def ws_profiles_default(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> dict[str, Any]:
    """Set the default profile for new displays."""
    await (await async_get_profile_manager(hass)).async_set_default(msg.get("profile_id"))
    return {}


@_cmd(
    {
        vol.Required("type"): f"{DOMAIN}/profiles/apply",
        vol.Required("profile_id"): str,
        vol.Required("entry_ids"): [str],
        vol.Optional("dry_run", default=False): bool,
    }
)
async def ws_profiles_apply(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> dict[str, Any]:
    """Apply a profile to displays (or preview the changes)."""
    (await async_get_profile_manager(hass)).get(msg["profile_id"])  # unknown profile: one error, not one per display
    results: dict[str, Any] = {}
    errors: dict[str, str] = {}
    for entry_id in msg["entry_ids"]:
        try:
            device = _device(hass, entry_id)
            if msg["dry_run"]:
                results[entry_id] = await async_profile_diff(hass, device, msg["profile_id"])
            else:
                results[entry_id] = await async_apply_profile(hass, device, msg["profile_id"])
        except (HomeAssistantError, ShellyElevateIntegrationError) as err:
            errors[entry_id] = str(err)
    return {"results": results, "errors": errors}


# --------------------------------------------------------------------------- installer


@_cmd({vol.Required("type"): f"{DOMAIN}/installer/info"})
async def ws_installer_info(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> dict[str, Any]:
    """Everything the install wizard needs."""
    releases = []
    try:
        releases = [
            {"version": r.version, "prerelease": r.prerelease, "published": r.published}
            for r in await async_get_releases(hass)
        ]
    except HomeAssistantError:
        pass
    manager = await async_get_profile_manager(hass)
    return {
        "releases": releases,
        "profiles": manager.as_list(),
        "default_profile": manager.default_profile_id,
        "dashboard_url": default_dashboard_url(hass),
    }


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/installer/provision",
        vol.Required("host"): str,
        vol.Optional("install_app", default=True): bool,
        vol.Optional("channel", default="stable"): vol.In(["stable", "beta"]),
        vol.Optional("version"): vol.Any(str, None),
        vol.Optional("disable_stock", default=False): bool,
        vol.Optional("profile_id"): vol.Any(str, None),
        vol.Optional("dashboard_url"): vol.Any(str, None),
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_provision(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Install + provision a display over ADB (subscription with progress events)."""
    msg_id = msg["id"]
    options = ProvisionOptions(
        host=msg["host"],
        install_app=msg["install_app"],
        channel=msg["channel"],
        version=msg.get("version"),
        disable_stock=msg["disable_stock"],
        profile_id=msg.get("profile_id"),
        dashboard_url=msg.get("dashboard_url"),
    )

    def send(event: dict[str, Any]) -> None:
        connection.send_message(websocket_api.event_message(msg_id, event))

    async def run() -> None:
        try:
            result = await async_provision(
                hass, options, lambda step, data: send({"type": "step", "step": step, **data})
            )
        except Exception as err:
            send({"type": "error", "error": str(err)})
        else:
            send({"type": "done", **result})

    task = hass.async_create_background_task(run(), f"{DOMAIN} provision {options.host}")
    connection.subscriptions[msg_id] = task.cancel
    connection.send_result(msg_id)


# --------------------------------------------------------------------------- revert


@_cmd({vol.Required("type"): f"{DOMAIN}/revert/check", vol.Required("host"): str})
async def ws_revert_check(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> dict[str, Any]:
    """Read-only: what reverting the display at `host` would find and do."""
    return await async_revert_check(hass, msg["host"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/revert/run",
        vol.Required("host"): str,
        vol.Optional("remove_entry", default=True): bool,
        vol.Optional("reboot", default=True): bool,
        vol.Optional("disable_adb", default=False): bool,
        vol.Optional("remove_wiki_launcher", default=True): bool,
        vol.Optional("accept_wifi_loss", default=False): bool,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_revert(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Revert a display to stock (subscription with progress events, like the installer)."""
    msg_id = msg["id"]
    options = RevertOptions(
        host=msg["host"],
        remove_entry=msg["remove_entry"],
        reboot=msg["reboot"],
        disable_adb=msg["disable_adb"],
        remove_wiki_launcher=msg["remove_wiki_launcher"],
        accept_wifi_loss=msg["accept_wifi_loss"],
    )

    def send(event: dict[str, Any]) -> None:
        connection.send_message(websocket_api.event_message(msg_id, event))

    async def run() -> None:
        try:
            result = await async_revert(hass, options, lambda step, data: send({"type": "step", "step": step, **data}))
        except Exception as err:
            send({"type": "error", "error": str(err)})
        else:
            send({"type": "done", **result})

    task = hass.async_create_background_task(run(), f"{DOMAIN} revert {options.host}")
    connection.subscriptions[msg_id] = task.cancel
    connection.send_result(msg_id)


@callback
def async_setup_websocket(hass: HomeAssistant) -> None:
    """Register all commands."""
    for command in (
        ws_devices,
        ws_settings_get,
        ws_settings_set,
        ws_settings_subscribe,
        ws_export,
        ws_copy,
        ws_command,
        ws_backups_list,
        ws_backups_create,
        ws_backups_diff,
        ws_backups_restore,
        ws_backups_delete,
        ws_profiles_list,
        ws_profiles_save,
        ws_profiles_delete,
        ws_profiles_default,
        ws_profiles_apply,
        ws_installer_info,
        ws_provision,
        ws_revert_check,
        ws_revert,
    ):
        websocket_api.async_register_command(hass, command)
