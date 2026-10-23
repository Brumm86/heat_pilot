"""Pure timing logic for notifications (no Home Assistant imports).

An *episode* is a condition that has been true since some point in time
(a door standing open, a sensor being unreachable). A :class:`Plan` says when
notifications for an episode are due: after ``first_delay``, then every
``repeat``, at most ``max_sent`` times, and only while the local hour lies in
``window``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(slots=True)
class Episode:
    """A condition that has held since ``since``."""

    since: datetime
    sent: int = 0
    last_sent: datetime | None = None


@dataclass(frozen=True, slots=True)
class Plan:
    """When notifications for an episode are due."""

    first_delay: timedelta
    repeat: timedelta | None = None
    max_sent: int | None = None
    window: tuple[int, int] | None = None  # local hours, start incl., end excl.


def in_window(local_hour: int, window: tuple[int, int] | None) -> bool:
    """Whether ``local_hour`` lies in the allowed window (None = always)."""
    if window is None:
        return True
    start, end = window
    if start <= end:
        return start <= local_hour < end
    return local_hour >= start or local_hour < end


def is_due(episode: Episode, plan: Plan, now: datetime, local_hour: int) -> bool:
    """Whether the next notification of ``episode`` should go out now.

    Anything that came due outside the window is simply postponed: the first
    check inside the window finds it overdue and sends it.
    """
    if plan.max_sent is not None and episode.sent >= plan.max_sent:
        return False
    if episode.sent == 0:
        target = episode.since + plan.first_delay
    elif plan.repeat is None or episode.last_sent is None:
        return False
    else:
        target = episode.last_sent + plan.repeat
    return now >= target and in_window(local_hour, plan.window)


def is_too_hot(measured: object, threshold: float) -> bool:
    """A thermostat measures ``threshold`` or more (suspect: stuck valve)."""
    try:
        return float(measured) >= threshold  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
