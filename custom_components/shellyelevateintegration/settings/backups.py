"""Settings backups per display.

Snapshots live in `.storage/shellyelevateintegration.backups`, so they are part of every Home
Assistant backup automatically.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import logging
from typing import TYPE_CHECKING, Any
import uuid

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store
from homeassistant.util.hass_dict import HassKey

from ..const import DEFAULT_BACKUP_KEEP, DOMAIN, OPT_AUTO_BACKUP, OPT_BACKUP_KEEP
from .schema import diff

if TYPE_CHECKING:
    from ..device import ShellyElevateIntegrationDevice

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY = f"{DOMAIN}.backups"
STORAGE_VERSION = 1
AUTO_BACKUP_DELAY = 60
DATA_BACKUPS: HassKey[BackupStore] = HassKey(f"{DOMAIN}_backups")
_LOCK: HassKey[asyncio.Lock] = HassKey(f"{DOMAIN}_backups_lock")

REASON_MANUAL = "manual"
REASON_AUTO = "auto"
REASON_SETUP = "setup"
REASON_BEFORE_RESTORE = "before_restore"
REASON_BEFORE_PROFILE = "before_profile"
REASON_BEFORE_UPDATE = "before_update"
REASON_IMPORT = "import"


class BackupStore:
    """All backups of all displays."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize."""
        self.hass = hass
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY, private=True)
        self.backups: dict[str, list[dict[str, Any]]] = {}

    async def async_load(self) -> None:
        """Load from storage."""
        data = await self._store.async_load() or {}
        self.backups = data.get("backups", {})

    @callback
    def _schedule_save(self) -> None:
        self._store.async_delay_save(lambda: {"backups": self.backups}, 2)

    def list(self, device_id: str) -> list[dict[str, Any]]:
        """Backups of one display, newest first."""
        return list(reversed(self.backups.get(device_id, [])))

    def get(self, device_id: str, backup_id: str | None = None) -> dict[str, Any]:
        """Return a backup (latest if no id)."""
        items = self.backups.get(device_id, [])
        if backup_id is None and items:
            return items[-1]
        for item in items:
            if item["id"] == backup_id:
                return item
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="backup_not_found",
            translation_placeholders={"backup": str(backup_id)},
        )

    @callback
    def add(
        self,
        device_id: str,
        settings: dict[str, Any],
        *,
        reason: str,
        fw_version: str | None,
        model: str | None,
        keep: int,
        name: str | None = None,
    ) -> dict[str, Any] | None:
        """Add a snapshot unless it equals the latest one. Returns the backup or None."""
        items = self.backups.setdefault(device_id, [])
        if items and items[-1]["settings"] == settings and reason in (REASON_AUTO, REASON_SETUP):
            return None
        backup = {
            "id": uuid.uuid4().hex[:12],
            "created": datetime.now(UTC).isoformat(),
            "reason": reason,
            "name": name,
            "fw_version": fw_version,
            "model": model,
            "settings": dict(settings),
        }
        items.append(backup)
        # Keep named (manual) backups beyond the limit; prune the oldest automatic ones first.
        while len(items) > keep:
            for idx, item in enumerate(items):
                if not item.get("name"):
                    del items[idx]
                    break
            else:
                del items[0]
        self._schedule_save()
        return backup

    @callback
    def delete(self, device_id: str, backup_id: str) -> None:
        """Delete a backup."""
        self.get(device_id, backup_id)
        self.backups[device_id] = [b for b in self.backups[device_id] if b["id"] != backup_id]
        self._schedule_save()

    @callback
    def import_backup(self, device_id: str, backup: dict[str, Any], keep: int) -> dict[str, Any]:
        """Import a backup exported earlier (from any display)."""
        new = self.add(
            device_id,
            backup["settings"],
            reason=REASON_IMPORT,
            fw_version=backup.get("fw_version"),
            model=backup.get("model"),
            keep=keep,
            name=backup.get("name") or "Imported",
        )
        assert new is not None
        return new


async def async_get_backup_store(hass: HomeAssistant) -> BackupStore:
    """Return the (lazily loaded) backup store."""
    if (store := hass.data.get(DATA_BACKUPS)) is not None:
        return store
    lock = hass.data.setdefault(_LOCK, asyncio.Lock())
    async with lock:
        if (store := hass.data.get(DATA_BACKUPS)) is None:
            store = BackupStore(hass)
            await store.async_load()
            hass.data[DATA_BACKUPS] = store
    return store


class BackupManager:
    """Backups for one display, including automatic snapshots on change."""

    def __init__(self, device: ShellyElevateIntegrationDevice, store: BackupStore) -> None:
        """Initialize."""
        self.device = device
        self.store = store
        self._cancel_auto: CALLBACK_TYPE | None = None
        self._unsub: CALLBACK_TYPE | None = None

    @property
    def keep(self) -> int:
        """Backups to keep."""
        return int(self.device.entry.options.get(OPT_BACKUP_KEEP, DEFAULT_BACKUP_KEEP))

    @property
    def auto(self) -> bool:
        """Automatic backups enabled."""
        return bool(self.device.entry.options.get(OPT_AUTO_BACKUP, True))

    @callback
    def async_start(self) -> None:
        """Take a setup snapshot and watch for changes."""
        if self.auto:
            self.snapshot(REASON_SETUP)
        self._unsub = self.device.async_add_message_listener(self._on_message)

    @callback
    def async_stop(self) -> None:
        """Stop watching."""
        if self._unsub:
            self._unsub()
            self._unsub = None
        if self._cancel_auto:
            self._cancel_auto()
            self._cancel_auto = None

    @callback
    def _on_message(self, message: dict[str, Any]) -> None:
        if message.get("type") != "settings_changed" or not self.auto:
            return
        if self._cancel_auto:
            self._cancel_auto()
        self._cancel_auto = async_call_later(self.device.hass, AUTO_BACKUP_DELAY, self._auto_backup)

    async def _auto_backup(self, _now: datetime) -> None:
        self._cancel_auto = None
        try:
            await self.device.client.get_settings()
        except Exception:
            _LOGGER.debug("Could not refresh settings for auto backup of %s", self.device.entry.title)
        self.snapshot(REASON_AUTO)

    @callback
    def snapshot(self, reason: str, name: str | None = None) -> dict[str, Any] | None:
        """Snapshot the cached settings."""
        info = self.device.info
        return self.store.add(
            self.device.device_id,
            self.device.settings,
            reason=reason,
            fw_version=info.fw_version,
            model=info.model,
            keep=self.keep,
            name=name,
        )

    async def async_backup(self, name: str | None = None) -> dict[str, Any]:
        """Fresh manual backup."""
        await self.device.async_refresh_settings()
        backup = self.snapshot(REASON_MANUAL, name)
        assert backup is not None
        return backup

    async def _async_restore_target(self, settings: dict[str, Any], keys: list[str] | None) -> dict[str, Any]:
        known = await self.device.async_known_keys()
        return {k: v for k, v in settings.items() if k in known and (keys is None or k in keys)}

    async def async_restore(self, backup_id: str | None = None, keys: list[str] | None = None) -> list[dict[str, Any]]:
        """Restore a backup (only changed keys are written). Returns the applied diff."""
        backup = self.store.get(self.device.device_id, backup_id)
        return await self.async_apply(backup["settings"], keys)

    async def async_apply(self, settings: dict[str, Any], keys: list[str] | None = None) -> list[dict[str, Any]]:
        """Write the changed, known keys of `settings` after a safety snapshot. Returns the diff."""
        await self.device.async_refresh_settings()
        changes = diff(self.device.settings, await self._async_restore_target(settings, keys))
        if not changes:
            return []
        self.snapshot(REASON_BEFORE_RESTORE)
        await self.device.async_set_settings({item["key"]: item["new"] for item in changes})
        return changes

    # defined last so it does not shadow the builtin list in the annotations above
    def list(self) -> list[dict[str, Any]]:
        """Backups, newest first."""
        return self.store.list(self.device.device_id)
