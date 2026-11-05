"""Tests for the pure night window logic."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from custom_components.heat_pilot import night

TZ = ZoneInfo("Europe/Berlin")
TIMES = {
    "weekday_start": "20:30",
    "weekday_end": "05:00",
    "weekend_start": "21:30",
    "weekend_end": "05:00",
}


def at(day: str, hhmm: str) -> datetime:
    return datetime.fromisoformat(f"{day}T{hhmm}:00").replace(tzinfo=TZ)


def test_a_night_belongs_to_the_day_it_begins_on() -> None:
    # Sunday 8 Nov 20:30 -> Monday 05:00 uses the weekday times.
    start, end = night.base_window(date(2026, 11, 8), TIMES, TZ)
    assert (start, end) == (at("2026-11-08", "20:30"), at("2026-11-09", "05:00"))
    # Friday and Saturday nights use the weekend start.
    assert night.base_window(date(2026, 11, 13), TIMES, TZ)[0] == at("2026-11-13", "21:30")
    assert night.base_window(date(2026, 11, 14), TIMES, TZ)[0] == at("2026-11-14", "21:30")


def test_active_after_midnight_belongs_to_the_previous_nights_times() -> None:
    assert night.is_active(at("2026-11-14", "04:59"), TIMES)  # Fri night, ends 05:00
    assert not night.is_active(at("2026-11-14", "05:00"), TIMES)
    assert not night.is_active(at("2026-11-14", "21:00"), TIMES)  # Sat: weekend start 21:30
    assert night.is_active(at("2026-11-14", "21:30"), TIMES)


def test_shift_applies_to_one_night_only() -> None:
    now = at("2026-11-10", "20:00")
    assert night.next_start(now, TIMES, 1, "2026-11-10") == at("2026-11-10", "21:30")
    assert night.next_start(now, TIMES, 1, "2026-11-09") == at("2026-11-10", "20:30")


def test_shift_past_the_end_cancels_that_night() -> None:
    now = at("2026-11-10", "20:00")
    assert night.room_window(date(2026, 11, 10), TIMES, TZ, 9, "2026-11-10") is None
    assert night.next_start(now, TIMES, 9, "2026-11-10") == at("2026-11-11", "20:30")


def test_upcoming_night_is_the_running_one_until_it_ends() -> None:
    assert night.upcoming_night(at("2026-11-10", "23:00"), TIMES) == date(2026, 11, 10)
    assert night.upcoming_night(at("2026-11-11", "03:00"), TIMES) == date(2026, 11, 10)
    assert night.upcoming_night(at("2026-11-11", "06:00"), TIMES) == date(2026, 11, 11)


def test_next_boundary_is_start_or_end() -> None:
    assert night.next_boundary(at("2026-11-10", "12:00"), TIMES) == at("2026-11-10", "20:30")
    assert night.next_boundary(at("2026-11-10", "23:00"), TIMES) == at("2026-11-11", "05:00")
