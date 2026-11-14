"""Weekly thermostat schedule: switch points per weekday, kept per display in Home Assistant's store.

A switch point sets the target temperature at a time of day; it holds until the next switch point,
which may lie on a later day. Days without switch points keep the last target of an earlier day.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import re
from typing import Any, Final

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN, SIGNAL_SCHEDULE_CHANGED

STORAGE_KEY: Final = f"{DOMAIN}.schedules"
STORAGE_VERSION: Final = 1
DATA_SCHEDULES: HassKey[ScheduleStore] = HassKey(f"{DOMAIN}_schedules")
_LOCK: HassKey[asyncio.Lock] = HassKey(f"{DOMAIN}_schedules_lock")

DAYS: Final = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
MAX_POINTS_PER_DAY: Final = 12
MIN_TEMP: Final = -10.0
MAX_TEMP: Final = 50.0
_TIME = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


@dataclass(frozen=True)
class SwitchPoint:
    """From this time of day on, the target temperature is `temperature`."""

    at: time
    temperature: float


@dataclass(frozen=True)
class WeekSchedule:
    """Switch points per weekday, Monday first, each day sorted by time."""

    days: tuple[tuple[SwitchPoint, ...], ...]

    def as_dict(self) -> dict[str, list[dict[str, Any]]]:
        """JSON form: {"mon": [{"time": "05:30", "temperature": 22.0}, ...], ...}."""
        return {
            day: [{"time": p.at.strftime("%H:%M"), "temperature": p.temperature} for p in points]
            for day, points in zip(DAYS, self.days, strict=True)
        }

    @property
    def empty(self) -> bool:
        """No switch point on any day."""
        return not any(self.days)

    def target_at(self, now: datetime) -> tuple[float | None, datetime | None]:
        """Target temperature in effect at `now` and when it changes next (aware local datetimes).

        Looks back up to a week for the switch point in effect and forward up to a week for the next one.
        """
        local = dt_util.as_local(now)
        today = local.date()
        current: float | None = None
        for back in range(8):
            day = today - timedelta(days=back)
            for point in reversed(self.days[day.weekday()]):
                if _at(day, point.at) <= local:
                    current = point.temperature
                    break
            if current is not None:
                break
        upcoming: datetime | None = None
        for ahead in range(8):
            day = today + timedelta(days=ahead)
            for point in self.days[day.weekday()]:
                when = _at(day, point.at)
                if when > local:
                    upcoming = when
                    break
            if upcoming is not None:
                break
        return current, upcoming


def _at(day: date, at: time) -> datetime:
    """The aware local datetime of a switch point (a time skipped by a DST change counts as the next hour)."""
    naive = datetime.combine(day, at)
    aware = naive.replace(tzinfo=dt_util.get_default_time_zone())
    # zoneinfo keeps a skipped wall time with the old offset; normalizing through UTC moves it past the gap
    return dt_util.as_local(dt_util.as_utc(aware))


def parse_schedule(data: Any) -> WeekSchedule:
    """Validate the JSON form; raises ValueError with a readable reason."""
    if not isinstance(data, dict):
        raise ValueError("schedule must be an object with one list per weekday")
    unknown = set(data) - set(DAYS)
    if unknown:
        raise ValueError(f"unknown days: {', '.join(sorted(unknown))}")
    days: list[tuple[SwitchPoint, ...]] = []
    for day in DAYS:
        raw = data.get(day, [])
        if not isinstance(raw, list):
            raise ValueError(f"{day}: expected a list of switch points")
        if len(raw) > MAX_POINTS_PER_DAY:
            raise ValueError(f"{day}: at most {MAX_POINTS_PER_DAY} switch points")
        points: dict[time, SwitchPoint] = {}
        for item in raw:
            if not isinstance(item, dict):
                raise ValueError(f"{day}: a switch point needs time and temperature")
            match = _TIME.match(str(item.get("time", "")))
            if match is None:
                raise ValueError(f"{day}: invalid time {item.get('time')!r} (HH:MM)")
            at = time(int(match.group(1)), int(match.group(2)))
            try:
                temperature = round(float(item["temperature"]), 1)
            except (KeyError, TypeError, ValueError):
                raise ValueError(f"{day} {match.group(0)}: invalid temperature") from None
            if not MIN_TEMP <= temperature <= MAX_TEMP:
                raise ValueError(f"{day} {match.group(0)}: temperature out of range")
            if at in points:
                raise ValueError(f"{day}: {match.group(0)} appears twice")
            points[at] = SwitchPoint(at, temperature)
        days.append(tuple(sorted(points.values(), key=lambda p: p.at)))
    return WeekSchedule(tuple(days))


def _points(spec: str) -> list[dict[str, Any]]:
    return [{"time": t, "temperature": float(v)} for t, v in (part.split("=") for part in spec.split(","))]


_WORKDAY = _points("05:30=22,08:00=19,17:30=22,22:00=18")
_WEEKEND = _points("07:00=22,22:00=18")
DEFAULT_SCHEDULE: Final = parse_schedule({day: _WEEKEND if day in ("sat", "sun") else _WORKDAY for day in DAYS})


class ScheduleStore:
    """The schedules of all displays, keyed by config entry id."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize."""
        self._hass = hass
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._schedules: dict[str, WeekSchedule] = {}

    async def async_load(self) -> None:
        """Read the stored schedules; unreadable ones fall back to the default."""
        data = await self._store.async_load() or {}
        for key, raw in (data.get("schedules") or {}).items():
            try:
                self._schedules[key] = parse_schedule(raw)
            except ValueError:
                continue

    def get(self, entry_id: str) -> WeekSchedule:
        """The schedule of a display (the default until one is saved)."""
        return self._schedules.get(entry_id, DEFAULT_SCHEDULE)

    def is_default(self, entry_id: str) -> bool:
        """Whether the display still uses the built-in default."""
        return entry_id not in self._schedules

    async def async_set(self, entry_id: str, schedule: WeekSchedule) -> None:
        """Save a schedule and tell the thermostat."""
        self._schedules[entry_id] = schedule
        await self._store.async_save({"schedules": {k: v.as_dict() for k, v in self._schedules.items()}})
        async_dispatcher_send(self._hass, SIGNAL_SCHEDULE_CHANGED.format(entry_id))

    @callback
    def async_remove(self, entry_id: str) -> None:
        """Forget the schedule of a removed display."""
        if self._schedules.pop(entry_id, None) is not None:
            self._store.async_delay_save(lambda: {"schedules": {k: v.as_dict() for k, v in self._schedules.items()}}, 1)


async def async_get_schedule_store(hass: HomeAssistant) -> ScheduleStore:
    """The shared schedule store, loaded once."""
    if (store := hass.data.get(DATA_SCHEDULES)) is not None:
        return store
    lock = hass.data.setdefault(_LOCK, asyncio.Lock())
    async with lock:
        if (store := hass.data.get(DATA_SCHEDULES)) is None:
            store = ScheduleStore(hass)
            await store.async_load()
            hass.data[DATA_SCHEDULES] = store
    return store
