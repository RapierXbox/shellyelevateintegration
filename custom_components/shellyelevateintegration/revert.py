"""Revert a display to stock: remove ShellyElevate and everything its installation changed.

What is undone, and why in this order, is in `adb/steps.py` (`revert_commands`). The check is
read-only; the panel shows its findings before the user confirms the run.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .adb import steps
from .adb.baseline import async_get_baseline_store
from .adb.manager import AdbError, ProgressCallback, async_create_adb_manager
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Findings the user should see before confirming (keys of the `revert_warning` translations).
WARN_WIFI = "wifi_by_app"
"""Uninstalling deletes Wi-Fi networks the app created: the display may drop off the network."""
WARN_STOCK_NEEDS_ROOT = "stock_needs_root"
"""The stock app was disabled as root; without root it cannot be enabled again."""
WARN_SYSTEM_COPY_NEEDS_ROOT = "system_copy_needs_root"
"""A copy in /system can only be removed with root; without it, it is hidden and emptied."""
WARN_STOCK_MISSING = "stock_missing"
"""The stock Shelly app is not installed; the display ends without a home app."""
WARN_NO_BASELINE = "no_baseline"
"""Not installed by this Home Assistant: screen settings stay as they are."""


@dataclass
class RevertOptions:
    """What the revert should do besides restoring stock."""

    host: str
    adb_port: int = steps.ADB_PORT
    remove_entry: bool = True
    reboot: bool = True
    disable_adb: bool = False
    """Also turn ADB over the network off (last; Home Assistant loses access)."""
    remove_wiki_launcher: bool = True
    accept_wifi_loss: bool = False


def entry_for_host(hass: HomeAssistant, host: str) -> ConfigEntry | None:
    """The configured display at `host`; None if there is none or the host is ambiguous."""
    entries = [e for e in hass.config_entries.async_entries(DOMAIN) if e.data.get(CONF_HOST) == host]
    return entries[0] if len(entries) == 1 else None


def _warnings(platform: steps.Platform, check: steps.RevertCheck, has_baseline: bool) -> list[str]:
    warnings = []
    if check.wifi_by_app:
        warnings.append(WARN_WIFI)
    if check.stock_disabled_by_root and not platform.root:
        warnings.append(WARN_STOCK_NEEDS_ROOT)
    if check.priv_app and not platform.root:
        warnings.append(WARN_SYSTEM_COPY_NEEDS_ROOT)
    if not check.stock_installed:
        warnings.append(WARN_STOCK_MISSING)
    if not has_baseline:
        warnings.append(WARN_NO_BASELINE)
    return warnings


async def async_revert_check(hass: HomeAssistant, host: str, adb_port: int = steps.ADB_PORT) -> dict[str, Any]:
    """Read-only: what a revert of the display at `host` would do."""
    adb = await async_create_adb_manager(hass, host, adb_port)
    platform, check = await adb.async_revert_check()
    has_baseline = (await async_get_baseline_store(hass)).get(platform.serial) is not None
    entry = entry_for_host(hass, host)
    return {
        "platform": {"sdk": platform.sdk, "model": platform.model, "root": platform.root},
        "check": check.as_dict(),
        "warnings": _warnings(platform, check, has_baseline),
        "entry_id": entry.entry_id if entry else None,
        "name": entry.title if entry else None,
    }


async def async_revert(hass: HomeAssistant, options: RevertOptions, progress: ProgressCallback) -> dict[str, Any]:
    """Revert the display; returns what was done and what could not be undone."""
    adb = await async_create_adb_manager(hass, options.host, options.adb_port)

    progress("adb_connect", {"status": "running", "command": f"connect {options.host}:{options.adb_port}"})
    progress("check", {"status": "running"})
    try:
        platform, check = await adb.async_revert_check()
    except AdbError as err:
        progress("adb_connect", {"status": "failed", "error": str(err)})
        raise
    progress("adb_connect", {"status": "done"})
    progress("check", {"status": "done", "root": platform.root, "sdk": platform.sdk, **check.as_dict()})
    if check.wifi_by_app and not options.accept_wifi_loss:
        raise HomeAssistantError(translation_domain=DOMAIN, translation_key="revert_wifi_by_app")

    entry = entry_for_host(hass, options.host)
    if entry is not None and entry.state is ConfigEntryState.LOADED:
        device = entry.runtime_data
        if device.settings.get("mqttHomeAssistantDiscovery"):
            # while the app still runs, so it clears the retained discovery topics on the broker
            progress("mqtt_cleanup", {"status": "running"})
            try:
                await device.async_set_settings({"mqttHomeAssistantDiscovery": False})
            except HomeAssistantError as err:
                progress("mqtt_cleanup", {"status": "failed", "error": str(err)})
            else:
                progress("mqtt_cleanup", {"status": "done"})

    store = await async_get_baseline_store(hass)
    baseline = store.get(platform.serial)
    await adb.async_run_steps(
        steps.revert_commands(
            check, root=platform.root, baseline=baseline, remove_wiki_launcher=options.remove_wiki_launcher
        ),
        progress,
    )

    progress("verify", {"status": "running"})
    _, after = await adb.async_revert_check()
    remaining = [
        name
        for name, left in (
            ("app", after.app_installed),
            ("system_copy", after.priv_app or after.init_rc),
            ("stock_disabled", after.stock_disabled),
        )
        if left
    ]
    progress("verify", {"status": "failed" if remaining else "done", "remaining": remaining})
    if platform.serial and not remaining:
        # a future install records stock values again
        await store.async_remove(platform.serial)

    entry_removed = False
    if entry is not None and options.remove_entry and not after.app_installed:
        progress("remove_entry", {"status": "running"})
        await hass.config_entries.async_remove(entry.entry_id)
        entry_removed = True
        progress("remove_entry", {"status": "done"})

    if options.disable_adb:
        await adb.async_disable_adb(platform.root, progress)
    elif options.reboot:
        progress("reboot", {"status": "running", "command": "reboot"})
        try:
            await adb.async_reboot()
        except AdbError as err:
            progress("reboot", {"status": "failed", "error": str(err)})
        else:
            progress("reboot", {"status": "done"})
    return {
        "remaining": remaining,
        "entry_removed": entry_removed,
        "adb_disabled": options.disable_adb,
        "warnings": _warnings(platform, check, baseline is not None),
    }
