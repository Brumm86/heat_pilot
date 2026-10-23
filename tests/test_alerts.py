"""Tests for the pure notification timing logic."""

from datetime import UTC, datetime, timedelta

import pytest

from custom_components.heat_pilot.alerts import (
    Episode,
    Plan,
    in_window,
    is_due,
    is_too_hot,
)

T0 = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
DOOR = Plan(timedelta(minutes=3), timedelta(minutes=3), 3)
ADMIN = Plan(timedelta(minutes=30), timedelta(hours=6), None, (8, 22))


def test_door_sequence_three_warnings_then_stop() -> None:
    ep = Episode(since=T0)
    assert not is_due(ep, DOOR, T0 + timedelta(minutes=2, seconds=59), 12)
    sent_at = []
    for minute in range(30):
        now = T0 + timedelta(minutes=minute)
        if is_due(ep, DOOR, now, 12):
            ep.sent += 1
            ep.last_sent = now
            sent_at.append(minute)
    assert sent_at == [3, 6, 9]


def test_single_reminder() -> None:
    plan = Plan(timedelta(minutes=15), max_sent=1)
    ep = Episode(since=T0)
    assert is_due(ep, plan, T0 + timedelta(minutes=15), 12)
    ep.sent, ep.last_sent = 1, T0 + timedelta(minutes=15)
    assert not is_due(ep, plan, T0 + timedelta(hours=5), 12)


def test_admin_waits_for_window_then_repeats_every_six_hours() -> None:
    ep = Episode(since=T0)
    assert not is_due(ep, ADMIN, T0 + timedelta(minutes=29), 12)
    # Due at night: postponed, then sent as soon as the window opens.
    assert not is_due(ep, ADMIN, T0 + timedelta(hours=10), 22)
    assert not is_due(ep, ADMIN, T0 + timedelta(hours=10), 3)
    assert is_due(ep, ADMIN, T0 + timedelta(hours=20), 8)
    ep.sent, ep.last_sent = 1, T0 + timedelta(hours=20)
    assert not is_due(ep, ADMIN, T0 + timedelta(hours=25), 13)
    assert is_due(ep, ADMIN, T0 + timedelta(hours=26), 14)


@pytest.mark.parametrize(
    ("hour", "expected"), [(7, False), (8, True), (21, True), (22, False), (0, False)]
)
def test_window(hour: int, expected: bool) -> None:
    assert in_window(hour, (8, 22)) is expected
    assert in_window(hour, None)


def test_too_hot() -> None:
    assert is_too_hot(25.0, 25.0)
    assert is_too_hot("26.3", 25.0)
    assert not is_too_hot(24.9, 25.0)
    assert not is_too_hot(None, 25.0)
    assert not is_too_hot("unavailable", 25.0)
