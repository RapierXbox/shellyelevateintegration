"""Weekly thermostat schedule."""

from __future__ import annotations

from datetime import datetime

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
import pytest

from custom_components.shellyelevateintegration.schedule import (
    DAYS,
    DEFAULT_SCHEDULE,
    async_get_schedule_store,
    parse_schedule,
)


def _local(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=dt_util.get_default_time_zone())


async def test_default(hass: HomeAssistant) -> None:
    """Workdays four switch points, the weekend two; a switch point holds until the next one."""
    await hass.config.async_set_time_zone("Europe/Berlin")
    data = DEFAULT_SCHEDULE.as_dict()
    assert [p["time"] for p in data["mon"]] == ["05:30", "08:00", "17:30", "22:00"]
    assert [p["time"] for p in data["sun"]] == ["07:00", "22:00"]
    # Monday 2026-11-16, before the first switch point: Sunday 22:00 still holds
    target, upcoming = DEFAULT_SCHEDULE.target_at(_local("2026-11-16T04:00"))
    assert target == 18.0
    assert upcoming == _local("2026-11-16T05:30")
    target, upcoming = DEFAULT_SCHEDULE.target_at(_local("2026-11-16T05:30"))
    assert target == 22.0
    assert upcoming == _local("2026-11-16T08:00")
    # Friday late to Saturday morning
    target, upcoming = DEFAULT_SCHEDULE.target_at(_local("2026-11-20T23:00"))
    assert (target, upcoming) == (18.0, _local("2026-11-21T07:00"))


async def test_sparse_and_empty(hass: HomeAssistant) -> None:
    """A single switch point in the week holds all week; an empty schedule has no target."""
    await hass.config.async_set_time_zone("Europe/Berlin")
    single = parse_schedule({"wed": [{"time": "12:00", "temperature": 20}]})
    target, upcoming = single.target_at(_local("2026-11-16T10:00"))
    assert (target, upcoming) == (20.0, _local("2026-11-18T12:00"))
    empty = parse_schedule({})
    assert empty.empty
    assert empty.target_at(_local("2026-11-16T10:00")) == (None, None)


async def test_dst(hass: HomeAssistant) -> None:
    """A switch point in the skipped hour fires right after the change."""
    await hass.config.async_set_time_zone("Europe/Berlin")
    schedule = parse_schedule({"sun": [{"time": "02:30", "temperature": 21}, {"time": "12:00", "temperature": 19}]})
    _, upcoming = schedule.target_at(_local("2026-03-29T01:00"))
    assert upcoming is not None
    assert dt_util.as_utc(upcoming) == datetime.fromisoformat("2026-03-29T01:30+00:00")


@pytest.mark.parametrize(
    ("data", "reason"),
    [
        ([], "object"),
        ({"xyz": []}, "unknown days"),
        ({"mon": "05:30=22"}, "list"),
        ({"mon": [{"time": "5:30", "temperature": 22}]}, "invalid time"),
        ({"mon": [{"time": "24:00", "temperature": 22}]}, "invalid time"),
        ({"mon": [{"time": "05:30"}]}, "invalid temperature"),
        ({"mon": [{"time": "05:30", "temperature": "warm"}]}, "invalid temperature"),
        ({"mon": [{"time": "05:30", "temperature": 99}]}, "out of range"),
        ({"mon": [{"time": "05:30", "temperature": 22}, {"time": "05:30", "temperature": 20}]}, "twice"),
        ({"mon": [{"time": f"{h:02}:00", "temperature": 20} for h in range(13)]}, "at most"),
    ],
)
def test_invalid(data: object, reason: str) -> None:
    """Broken schedules are refused with a reason."""
    with pytest.raises(ValueError, match=reason):
        parse_schedule(data)


def test_sorted_and_rounded() -> None:
    """Switch points are sorted by time and temperatures rounded to 0.1."""
    schedule = parse_schedule(
        {"tue": [{"time": "18:00", "temperature": 21.04}, {"time": "06:00", "temperature": "22"}]}
    )
    assert schedule.as_dict()["tue"] == [{"time": "06:00", "temperature": 22.0}, {"time": "18:00", "temperature": 21.0}]
    assert set(schedule.as_dict()) == set(DAYS)


async def test_store(hass: HomeAssistant, hass_storage: dict[str, object]) -> None:
    """Schedules are kept per entry and survive a reload; broken stored ones fall back to the default."""
    hass_storage["shellyelevateintegration.schedules"] = {
        "version": 1,
        "data": {"schedules": {"broken": {"mon": "x"}, "kept": {"fri": [{"time": "07:00", "temperature": 20}]}}},
    }
    store = await async_get_schedule_store(hass)
    assert store is await async_get_schedule_store(hass)
    assert store.get("broken") is DEFAULT_SCHEDULE
    assert store.is_default("broken")
    assert store.get("kept").as_dict()["fri"] == [{"time": "07:00", "temperature": 20.0}]
    new = parse_schedule({"mon": [{"time": "06:00", "temperature": 21}]})
    await store.async_set("entry", new)
    assert store.get("entry") == new
    assert hass_storage["shellyelevateintegration.schedules"]["data"]["schedules"]["entry"]["mon"] == [
        {"time": "06:00", "temperature": 21.0}
    ]
