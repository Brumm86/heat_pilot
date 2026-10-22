"""Tests for the pure decision logic (no Home Assistant involved)."""

from dataclasses import replace
from datetime import date

import pytest

from custom_components.heat_pilot.decision import (
    HVAC_HEAT,
    HVAC_OFF,
    Reason,
    RoomInputs,
    clamp_target,
    decide,
    in_heating_period,
    sensor_is_open,
)

BASE = RoomInputs(
    period_active=True,
    absence_mode=False,
    frost_temp=7.0,
    opening_shutdown_enabled=True,
    opening_open_beyond_delay=False,
    absence_shutdown_enabled=True,
    has_persons=False,
    persons_away_beyond_delay=False,
    schedule_on=True,
    skip_setback=False,
    comfort_temp=21.0,
    setback_temp=17.0,
    max_limit_enabled=True,
    max_temp=24.0,
)


def test_comfort_when_schedule_on() -> None:
    result = decide(BASE)
    assert (result.hvac_mode, result.target, result.reason) == (
        HVAC_HEAT,
        21.0,
        Reason.COMFORT,
    )


def test_setback_when_schedule_off() -> None:
    result = decide(replace(BASE, schedule_on=False))
    assert (result.hvac_mode, result.target, result.reason) == (
        HVAC_HEAT,
        17.0,
        Reason.SETBACK,
    )


def test_skip_setback_keeps_comfort_in_setback_phase() -> None:
    result = decide(replace(BASE, schedule_on=False, skip_setback=True))
    assert (result.target, result.reason) == (21.0, Reason.COMFORT_SKIPPED)


def test_skip_flag_does_not_change_comfort_phase() -> None:
    result = decide(replace(BASE, skip_setback=True))
    assert result.reason is Reason.COMFORT


def test_opening_beyond_delay_turns_off() -> None:
    result = decide(replace(BASE, opening_open_beyond_delay=True))
    assert (result.hvac_mode, result.target, result.reason) == (
        HVAC_OFF,
        None,
        Reason.OPENING,
    )


def test_opening_ignored_when_feature_disabled() -> None:
    result = decide(
        replace(BASE, opening_open_beyond_delay=True, opening_shutdown_enabled=False)
    )
    assert result.reason is Reason.COMFORT


def test_room_absent_turns_off_only_with_persons() -> None:
    absent = replace(BASE, persons_away_beyond_delay=True)
    # No persons configured: never absent, whatever the flag says.
    assert decide(absent).reason is Reason.COMFORT
    result = decide(replace(absent, has_persons=True))
    assert (result.hvac_mode, result.reason) == (HVAC_OFF, Reason.ROOM_ABSENT)


def test_room_absent_ignored_when_feature_disabled() -> None:
    result = decide(
        replace(
            BASE,
            has_persons=True,
            persons_away_beyond_delay=True,
            absence_shutdown_enabled=False,
        )
    )
    assert result.reason is Reason.COMFORT


def test_absence_mode_is_frost_protection_in_mode_heat() -> None:
    result = decide(replace(BASE, absence_mode=True))
    assert (result.hvac_mode, result.target, result.reason) == (
        HVAC_HEAT,
        7.0,
        Reason.ABSENCE_MODE,
    )


def test_absence_mode_beats_open_door() -> None:
    # An open door must not switch to "off" during absence (frost!).
    result = decide(
        replace(BASE, absence_mode=True, opening_open_beyond_delay=True)
    )
    assert (result.hvac_mode, result.reason) == (HVAC_HEAT, Reason.ABSENCE_MODE)


def test_outside_period_beats_everything() -> None:
    result = decide(replace(BASE, period_active=False, absence_mode=True))
    assert (result.hvac_mode, result.target, result.reason) == (
        HVAC_OFF,
        None,
        Reason.OUTSIDE_PERIOD,
    )


def test_opening_beats_room_absence_and_schedule() -> None:
    result = decide(
        replace(
            BASE,
            opening_open_beyond_delay=True,
            has_persons=True,
            persons_away_beyond_delay=True,
        )
    )
    assert result.reason is Reason.OPENING


def test_max_limit_clamps_targets() -> None:
    result = decide(replace(BASE, comfort_temp=26.0))
    assert result.target == 24.0
    unlimited = decide(replace(BASE, comfort_temp=26.0, max_limit_enabled=False))
    assert unlimited.target == 26.0


def test_clamp_target() -> None:
    assert clamp_target(30.0, True, 24.0) == 24.0
    assert clamp_target(20.0, True, 24.0) == 20.0
    assert clamp_target(30.0, False, 24.0) == 30.0


@pytest.mark.parametrize(
    ("today", "expected"),
    [
        (date(2026, 10, 1), True),  # first day, inclusive
        (date(2026, 12, 31), True),
        (date(2027, 1, 1), True),  # wraps over new year
        (date(2027, 4, 30), True),  # last day, inclusive
        (date(2027, 5, 1), False),
        (date(2026, 9, 30), False),
        (date(2026, 7, 15), False),
    ],
)
def test_heating_period_wraps_over_new_year(today: date, expected: bool) -> None:
    assert in_heating_period(today, (10, 1), (4, 30)) is expected


def test_heating_period_within_one_year() -> None:
    assert in_heating_period(date(2026, 6, 1), (5, 1), (9, 30))
    assert not in_heating_period(date(2026, 10, 1), (5, 1), (9, 30))


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("on", True),
        ("off", False),
        ("unavailable", False),
        ("unknown", False),
        (None, False),
    ],
)
def test_only_definite_on_counts_as_open(state: str | None, expected: bool) -> None:
    assert sensor_is_open(state) is expected
