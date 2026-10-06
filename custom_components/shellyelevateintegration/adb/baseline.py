"""Stock values of a display, read before ShellyElevate is first installed, for the revert.

Keyed by the Android serial number, so it survives removing and re-adding the display in Home
Assistant. Stored in .storage (and therefore in HA backups).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util.hass_dict import HassKey

from ..const import DOMAIN

STORAGE_KEY = f"{DOMAIN}.baseline"
STORAGE_VERSION = 1
DATA_BASELINE: HassKey[BaselineStore] = HassKey(f"{DOMAIN}_baseline")
_LOCK: HassKey[asyncio.Lock] = HassKey(f"{DOMAIN}_baseline_lock")


class BaselineStore:
    """serial -> stock values."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize."""
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY, private=True)
        self.displays: dict[str, dict[str, Any]] = {}

    async def async_load(self) -> None:
        """Load from storage."""
        self.displays = (await self._store.async_load() or {}).get("displays", {})

    def get(self, serial: str | None) -> dict[str, str] | None:
        """The stock values of a display, if they were captured."""
        entry = self.displays.get(serial or "")
        return dict(entry["values"]) if entry else None

    async def async_capture(self, serial: str, values: dict[str, str]) -> None:
        """Remember the stock values; the first capture wins (later ones are not stock)."""
        if serial in self.displays:
            return
        self.displays[serial] = {"values": values, "captured": datetime.now(UTC).isoformat()}
        await self._store.async_save({"displays": self.displays})

    async def async_remove(self, serial: str) -> None:
        """Forget a display (after a revert: the next install captures stock again)."""
        if self.displays.pop(serial, None) is not None:
            await self._store.async_save({"displays": self.displays})


async def async_get_baseline_store(hass: HomeAssistant) -> BaselineStore:
    """Return the (lazily loaded) store."""
    if (store := hass.data.get(DATA_BASELINE)) is not None:
        return store
    async with hass.data.setdefault(_LOCK, asyncio.Lock()):
        if (store := hass.data.get(DATA_BASELINE)) is None:
            store = BaselineStore(hass)
            await store.async_load()
            hass.data[DATA_BASELINE] = store
    return store
