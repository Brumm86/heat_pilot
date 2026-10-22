"""Pure decision logic for Heat Pilot.

This module has deliberately *no* Home Assistant imports: given a snapshot of
everything that influences one room, :func:`decide` returns what the room's
thermostats should do. That keeps the priority rules testable in isolation.

Priority (highest first):

1. Outside the heating period      -> off
2. Absence mode (whole house)      -> frost protection (mode ``heat``)
3. Door/window open beyond delay   -> off
4. Room absent (its persons away)  -> off
5. Schedule                        -> comfort or setback
   (the one-shot "skip setback" flag turns a setback phase into comfort)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class Reason(StrEnum):
    """Why a room currently has the target it has."""

    OUTSIDE_PERIOD = "outside_period"
    ABSENCE_MODE = "absence_mode"
    OPENING = "opening"
    ROOM_ABSENT = "room_absent"
    COMFORT = "comfort"
    SETBACK = "setback"
    COMFORT_SKIPPED = "comfort_skipped"


HVAC_OFF = "off"
HVAC_HEAT = "heat"


@dataclass(frozen=True, slots=True)
class RoomInputs:
    """Everything that influences one room's target at a given moment."""

    period_active: bool
    absence_mode: bool
    frost_temp: float
    # Door/window logic. ``opening_open_beyond_delay`` is True once any
    # sensor of the room has been open for longer than the room's delay;
    # unavailable sensors count as closed (handled by the caller).
    opening_shutdown_enabled: bool
    opening_open_beyond_delay: bool
    # Room-level absence ("children's rooms"). ``persons_away_beyond_delay``
    # is True once *all* of the room's persons have been away for longer
    # than the room's grace period. A room without persons is never absent.
    absence_shutdown_enabled: bool
    has_persons: bool
    persons_away_beyond_delay: bool
    # Schedule phase: True = comfort, False = setback.
    schedule_on: bool
    skip_setback: bool
    comfort_temp: float
    setback_temp: float
    # Global maximum, applied to every heating target if enabled.
    max_limit_enabled: bool
    max_temp: float


@dataclass(frozen=True, slots=True)
class Decision:
    """What the thermostats of a room should do."""

    hvac_mode: str
    target: float | None
    reason: Reason


def clamp_target(target: float, max_enabled: bool, max_temp: float) -> float:
    """Limit ``target`` to ``max_temp`` when the room has the limit enabled."""
    if max_enabled and target > max_temp:
        return max_temp
    return target


def decide(inputs: RoomInputs) -> Decision:
    """Return the decision for one room, applying the priority order."""
    if not inputs.period_active:
        return Decision(HVAC_OFF, None, Reason.OUTSIDE_PERIOD)

    if inputs.absence_mode:
        target = clamp_target(
            inputs.frost_temp, inputs.max_limit_enabled, inputs.max_temp
        )
        return Decision(HVAC_HEAT, target, Reason.ABSENCE_MODE)

    if inputs.opening_shutdown_enabled and inputs.opening_open_beyond_delay:
        return Decision(HVAC_OFF, None, Reason.OPENING)

    if (
        inputs.absence_shutdown_enabled
        and inputs.has_persons
        and inputs.persons_away_beyond_delay
    ):
        return Decision(HVAC_OFF, None, Reason.ROOM_ABSENT)

    if inputs.schedule_on:
        reason = Reason.COMFORT
        target = inputs.comfort_temp
    elif inputs.skip_setback:
        reason = Reason.COMFORT_SKIPPED
        target = inputs.comfort_temp
    else:
        reason = Reason.SETBACK
        target = inputs.setback_temp

    target = clamp_target(target, inputs.max_limit_enabled, inputs.max_temp)
    return Decision(HVAC_HEAT, target, reason)


def in_heating_period(
    today: date, start: tuple[int, int], end: tuple[int, int]
) -> bool:
    """Return whether ``today`` lies in the period [start, end] (month, day).

    The period may wrap around the new year (e.g. 1 Oct - 30 Apr). Both
    boundaries are inclusive.
    """
    current = (today.month, today.day)
    if start <= end:
        return start <= current <= end
    return current >= start or current <= end


def sensor_is_open(state: str | None) -> bool:
    """Return True only for a definite ``on`` state.

    ``unavailable``, ``unknown`` and a missing entity all count as *closed*,
    so a broken sensor never shuts a room's heating off.
    """
    return state == "on"
