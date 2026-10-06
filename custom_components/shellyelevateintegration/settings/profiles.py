"""Settings profiles: named, reusable sets of display settings.

One profile can be marked as the default; it is offered (pre-selected) when a new display
is added, so every display starts with the same configuration.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
import uuid

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store
from homeassistant.util.hass_dict import HassKey

from ..api import SettingDef
from ..const import DOMAIN
from .schema import per_device_keys

STORAGE_KEY = f"{DOMAIN}.profiles"
STORAGE_VERSION = 1
DATA_PROFILES: HassKey[ProfileManager] = HassKey(f"{DOMAIN}_profiles")
_LOCK: HassKey[asyncio.Lock] = HassKey(f"{DOMAIN}_profiles_lock")


class ProfileManager:
    """Stores profiles in .storage (and therefore in HA backups)."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize."""
        self.hass = hass
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY, private=True)
        self.profiles: dict[str, dict[str, Any]] = {}
        self.default_profile_id: str | None = None

    async def async_load(self) -> None:
        """Load from storage."""
        data = await self._store.async_load() or {}
        self.profiles = data.get("profiles", {})
        self.default_profile_id = data.get("default")
        if self.default_profile_id not in self.profiles:
            self.default_profile_id = None

    async def _async_save(self) -> None:
        await self._store.async_save({"profiles": self.profiles, "default": self.default_profile_id})

    def get(self, profile_id: str) -> dict[str, Any]:
        """Return a profile or raise."""
        if profile_id not in self.profiles:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="profile_not_found",
                translation_placeholders={"profile": profile_id},
            )
        return self.profiles[profile_id]

    def find(self, id_or_name: str) -> str:
        """Resolve a profile id from an id or a (case-insensitive) name."""
        if id_or_name in self.profiles:
            return id_or_name
        for pid, profile in self.profiles.items():
            if profile["name"].casefold() == id_or_name.casefold():
                return pid
        self.get(id_or_name)  # raises profile_not_found
        return id_or_name

    async def async_save_profile(
        self,
        name: str,
        settings: dict[str, Any],
        *,
        profile_id: str | None = None,
        schema: list[SettingDef] | None = None,
        make_default: bool | None = None,
    ) -> str:
        """Create or replace a profile. Per-device keys are always stripped."""
        skip = per_device_keys(schema)
        now = datetime.now(UTC).isoformat()
        profile_id = profile_id or uuid.uuid4().hex[:12]
        existing = self.profiles.get(profile_id, {})
        self.profiles[profile_id] = {
            "name": name,
            "settings": {k: v for k, v in settings.items() if k not in skip},
            "created": existing.get("created", now),
            "updated": now,
        }
        if make_default or (make_default is None and self.default_profile_id is None and not existing):
            self.default_profile_id = profile_id
        elif make_default is False and self.default_profile_id == profile_id:
            self.default_profile_id = None
        await self._async_save()
        return profile_id

    async def async_delete(self, profile_id: str) -> None:
        """Delete a profile."""
        self.get(profile_id)
        del self.profiles[profile_id]
        if self.default_profile_id == profile_id:
            self.default_profile_id = None
        await self._async_save()

    async def async_set_default(self, profile_id: str | None) -> None:
        """Mark a profile as default (None clears)."""
        if profile_id is not None:
            self.get(profile_id)
        self.default_profile_id = profile_id
        await self._async_save()

    def settings_for_device(
        self,
        profile_id: str,
        schema: list[SettingDef] | None,
        known_keys: set[str] | None = None,
    ) -> dict[str, Any]:
        """The profile settings that apply to a display."""
        profile = self.get(profile_id)
        skip = per_device_keys(schema)
        return {
            k: v for k, v in profile["settings"].items() if k not in skip and (known_keys is None or k in known_keys)
        }

    def as_list(self) -> list[dict[str, Any]]:
        """All profiles for the panel / services."""
        return [
            {"id": pid, "default": pid == self.default_profile_id, **profile}
            for pid, profile in sorted(self.profiles.items(), key=lambda item: item[1]["name"].casefold())
        ]


async def async_get_profile_manager(hass: HomeAssistant) -> ProfileManager:
    """Return the (lazily loaded) profile manager."""
    if (manager := hass.data.get(DATA_PROFILES)) is not None:
        return manager
    lock = hass.data.setdefault(_LOCK, asyncio.Lock())
    async with lock:
        if (manager := hass.data.get(DATA_PROFILES)) is None:
            manager = ProfileManager(hass)
            await manager.async_load()
            hass.data[DATA_PROFILES] = manager
    return manager
