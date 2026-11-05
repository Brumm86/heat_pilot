"""Pure time logic of the forced night setback (no Home Assistant imports).

A *night* belongs to the day on which it begins. Friday and Saturday nights
use the weekend times, all other nights the weekday times. A room can push the
start of one night back by whole hours (``shift_hours`` for ``shift_night``);
if that moves the start to or past the end, the room has no setback that night.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, time, timedelta, tzinfo

WEEKEND_NIGHT_WEEKDAYS = (4, 5)  # Friday, Saturday (Monday = 0)

Window = tuple[date, datetime, datetime]


def base_window(night: date, times: Mapping[str, str], tz: tzinfo) -> tuple[datetime, datetime]:
    """Start and end of a night without any shift."""
    kind = "weekend" if night.weekday() in WEEKEND_NIGHT_WEEKDAYS else "weekday"
    start_t = time.fromisoformat(times[f"{kind}_start"])
    end_t = time.fromisoformat(times[f"{kind}_end"])
    start = datetime.combine(night, start_t, tzinfo=tz)
    end_day = night if end_t > start_t else night + timedelta(days=1)
    return start, datetime.combine(end_day, end_t, tzinfo=tz)


def room_window(
    night: date,
    times: Mapping[str, str],
    tz: tzinfo,
    shift_hours: int,
    shift_night: str | None,
) -> tuple[datetime, datetime] | None:
    """The room's window of ``night`` (None if the shift cancels it)."""
    start, end = base_window(night, times, tz)
    if shift_night == night.isoformat() and shift_hours:
        start += timedelta(hours=shift_hours)
    if start >= end:
        return None
    return start, end


def windows(
    now: datetime,
    times: Mapping[str, str],
    shift_hours: int = 0,
    shift_night: str | None = None,
) -> list[Window]:
    """The room's windows of yesterday's to the day after tomorrow's night."""
    today = now.date()
    out: list[Window] = []
    for offset in range(-1, 3):
        night = today + timedelta(days=offset)
        window = room_window(night, times, now.tzinfo, shift_hours, shift_night)
        if window:
            out.append((night, *window))
    return out


def is_active(now, times, shift_hours=0, shift_night=None) -> bool:
    """Whether ``now`` lies inside one of the room's windows."""
    return any(s <= now < e for _n, s, e in windows(now, times, shift_hours, shift_night))


def next_start(now, times, shift_hours=0, shift_night=None) -> datetime | None:
    """The next window start after ``now``."""
    starts = [s for _n, s, _e in windows(now, times, shift_hours, shift_night) if s > now]
    return min(starts) if starts else None


def next_boundary(now, times, shift_hours=0, shift_night=None) -> datetime | None:
    """The next window start or end after ``now``."""
    points = [
        p
        for _n, s, e in windows(now, times, shift_hours, shift_night)
        for p in (s, e)
        if p > now
    ]
    return min(points) if points else None


def upcoming_night(now: datetime, times: Mapping[str, str]) -> date:
    """The night a "later" request refers to: the running or next one."""
    today = now.date()
    for offset in range(-1, 3):
        night = today + timedelta(days=offset)
        if base_window(night, times, now.tzinfo)[1] > now:
            return night
    return today
