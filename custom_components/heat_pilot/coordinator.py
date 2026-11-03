"""Coordinator for Heat Pilot.

There is nothing to poll. The coordinator is the event-driven engine: it
listens to schedules, door/window sensors, persons and thermostats, runs the
pure decision logic for each room and applies the result to the room's
thermostats. ``DataUpdateCoordinator`` is used as the single source of truth
for entities (``data`` maps room id -> :class:`RoomStatus`).

Heat Pilot only *acts* on events (schedule change, sensor/person change, a
toggle, a timer, start-up, midnight). A manual change on a thermostat stays
until the next such event. Three deliberate exceptions, all requested:

* outside the heating period thermostats are forced off again,
* while a room is shut off because a door/window stands open, a manual
  switch-on is reverted immediately, and
* a room with the maximum-temperature limit enabled has any setpoint above
  the global maximum pulled back down (not while the room is boosted).

Door/window events never touch the setpoint: while the delay runs nothing
happens at all, the shutdown only switches the thermostats off, and after
closing they are switched back on with the setpoint they have - unless the
room's plan target changed in the meantime (then the new target is set).

A room can be boosted: for a configurable time its thermostats are turned up
to their maximum. The end is persisted and re-armed after a restart.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
)
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    EVENT_HOMEASSISTANT_STARTED,
    STATE_HOME,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import (
    async_call_later,
    async_track_point_in_time,
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ABSENCE_DELAY,
    CONF_DOOR_SENSORS,
    CONF_EXTERNAL_HEATING,
    CONF_OPEN_DELAY,
    CONF_PERSONS,
    CONF_SCHEDULE,
    CONF_THERMOSTATS,
    CONF_WINDOW_SENSORS,
    DEFAULT_ABSENCE_DELAY,
    DEFAULT_OPEN_DELAY,
    DOMAIN,
    FEATURE_ABSENCE_SHUTDOWN,
    FEATURE_MAX_LIMIT,
    FEATURE_OPENING_SHUTDOWN,
    SUBENTRY_ROOM,
)
from .decision import (
    HVAC_OFF,
    Decision,
    Reason,
    RoomInputs,
    decide,
    in_heating_period,
    sensor_is_open,
)
from .storage import HeatPilotStore

_LOGGER = logging.getLogger(__name__)

# Timers are armed for exactly the configured delay; allow a little slack so
# a timer that fires a few milliseconds early still counts as elapsed.
_TIMER_SLACK_SECONDS = 1.0
_SETPOINT_TOLERANCE = 0.05

_NOT_REPORTING = (STATE_UNAVAILABLE, STATE_UNKNOWN)

# How an evaluation applies its decision to the thermostats.
_APPLY_FULL = "full"  # mode and setpoint
_APPLY_KEEP_SETPOINT = "keep_setpoint"  # mode only, setpoint stays as it is
_APPLY_NONE = "none"  # do not touch the thermostats


@dataclass(frozen=True, slots=True)
class RoomConfig:
    """A room as configured in its config subentry."""

    room_id: str
    name: str
    thermostats: tuple[str, ...]
    schedule: str | None
    door_sensors: tuple[str, ...]
    window_sensors: tuple[str, ...]
    persons: tuple[str, ...]
    open_delay: int
    absence_delay: int
    # Room is (also) heated outside Home Assistant, e.g. by underfloor heating.
    external_heating: bool = False

    @property
    def externally_heated(self) -> bool:
        """Heat does not (only) come from the room's thermostats.

        A room without any thermostat is heated externally by definition.
        """
        return self.external_heating or not self.thermostats

    @property
    def openings(self) -> tuple[str, ...]:
        return self.door_sensors + self.window_sensors

    @classmethod
    def from_subentry(cls, subentry: ConfigSubentry) -> RoomConfig:
        data = subentry.data
        return cls(
            room_id=subentry.subentry_id,
            name=subentry.title,
            thermostats=tuple(data.get(CONF_THERMOSTATS, [])),
            schedule=data.get(CONF_SCHEDULE) or None,
            door_sensors=tuple(data.get(CONF_DOOR_SENSORS, [])),
            window_sensors=tuple(data.get(CONF_WINDOW_SENSORS, [])),
            persons=tuple(data.get(CONF_PERSONS, [])),
            open_delay=int(data.get(CONF_OPEN_DELAY, DEFAULT_OPEN_DELAY)),
            absence_delay=int(data.get(CONF_ABSENCE_DELAY, DEFAULT_ABSENCE_DELAY)),
            external_heating=bool(data.get(CONF_EXTERNAL_HEATING, False)),
        )


@dataclass(frozen=True, slots=True)
class RoomStatus:
    """What entities show for one room."""

    room_id: str
    name: str
    decision: Decision
    opening_open: bool
    opening_pending: bool
    room_absent: bool
    unavailable_sensors: tuple[str, ...]
    next_change: str | None
    heated_today: bool
    # Schedule phase is setback (independent of door/window/absence shutdowns).
    in_setback: bool = False
    # Schedule phase is comfort (or setback skipped) and nothing else overrides it
    # except door/window shutdown: the room is meant to be heated to comfort now.
    in_comfort: bool = False


def _person_is_away(state: str | None) -> bool:
    """A person is away when definitely somewhere other than home.

    A person without a usable state is *not* counted as away, so a flaky
    tracker never switches a child's room off.
    """
    return state is not None and state not in (STATE_HOME, *_NOT_REPORTING)


class HeatPilotCoordinator(DataUpdateCoordinator[dict[str, RoomStatus]]):
    """Event-driven engine; ``data`` holds the status of every room."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, store: HeatPilotStore
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=None,
        )
        self.store = store
        self.rooms: dict[str, RoomConfig] = {}
        # Active alerts, maintained by the notifier and shown by a sensor/the card.
        self.active_alerts: list[dict[str, str]] = []
        self._entity_rooms: dict[str, set[str]] = {}
        self._open_since: dict[str, datetime] = {}
        self._away_since: dict[str, datetime] = {}
        self._timers: dict[tuple[str, str], CALLBACK_TYPE] = {}
        self._unsubs: list[CALLBACK_TYPE] = []
        self._return_unsub: CALLBACK_TYPE | None = None
        self._boost_unsubs: dict[str, CALLBACK_TYPE] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------ setup

    async def async_setup(self) -> None:
        """Load state, start tracking and run the first evaluation."""
        await self.store.async_load()
        self._load_rooms()
        self.store.forget_rooms_except(set(self.rooms))

        now = dt_util.utcnow()
        for room in self.rooms.values():
            self._refresh_timers(room, now)

        self._register_listeners()
        self._expire_or_schedule_return()
        self._restore_boosts(now)
        self.async_set_updated_data(self._compute_all(now))

        if self.hass.is_running:
            await self.async_evaluate_all()
        else:
            self._unsubs.append(
                self.hass.bus.async_listen_once(
                    EVENT_HOMEASSISTANT_STARTED, self._async_on_started
                )
            )

    async def _async_on_started(self, _event: Event) -> None:
        await self.async_evaluate_all()

    def _load_rooms(self) -> None:
        self.rooms = {}
        self._entity_rooms = {}
        for subentry in self.config_entry.subentries.values():
            if subentry.subentry_type != SUBENTRY_ROOM:
                continue
            room = RoomConfig.from_subentry(subentry)
            self.rooms[room.room_id] = room
            tracked = (
                room.thermostats
                + room.openings
                + room.persons
                + ((room.schedule,) if room.schedule else ())
            )
            for entity_id in tracked:
                self._entity_rooms.setdefault(entity_id, set()).add(room.room_id)

    def _register_listeners(self) -> None:
        if self._entity_rooms:
            self._unsubs.append(
                async_track_state_change_event(
                    self.hass, list(self._entity_rooms), self._async_state_changed
                )
            )
        # Midnight: the heating period may start/end and "heated today"
        # rolls over.
        self._unsubs.append(
            async_track_time_change(
                self.hass, self._async_midnight, hour=0, minute=0, second=5
            )
        )

    @callback
    def async_shutdown_engine(self) -> None:
        """Cancel every listener and timer (on unload)."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        for cancel in self._timers.values():
            cancel()
        self._timers.clear()
        for cancel in self._boost_unsubs.values():
            cancel()
        self._boost_unsubs.clear()
        if self._return_unsub:
            self._return_unsub()
            self._return_unsub = None

    # ------------------------------------------------------------- listeners

    @callback
    def _async_state_changed(self, event: Event[EventStateChangedData]) -> None:
        entity_id = event.data["entity_id"]
        old_state = event.data["old_state"]
        new_state = event.data["new_state"]
        now = dt_util.utcnow()

        for room_id in self._entity_rooms.get(entity_id, ()):
            room = self.rooms[room_id]
            if entity_id in room.thermostats:
                self._spawn(self._async_thermostat_changed(room, entity_id))
                continue

            old = old_state.state if old_state else None
            new = new_state.state if new_state else None
            if old == new:
                continue  # attribute-only change

            if entity_id == room.schedule and old == "off" and new == "on":
                # Comfort phase begins: a one-shot "skip setback" ends here.
                room_state = self.store.room(room_id)
                if room_state["skip_setback"]:
                    room_state["skip_setback"] = False
                    self.store.schedule_save()

            self._refresh_timers(room, now)
            self._spawn(
                self.async_evaluate_room(
                    room_id, opening_event=entity_id in room.openings
                )
            )

    @callback
    def _async_midnight(self, _now: datetime) -> None:
        self._spawn(self.async_evaluate_all())

    def _spawn(self, coro: Coroutine[Any, Any, None]) -> None:
        self.config_entry.async_create_background_task(
            self.hass, coro, name=f"{DOMAIN} evaluation"
        )

    # ----------------------------------------------------------------- timers

    def _refresh_timers(self, room: RoomConfig, now: datetime) -> None:
        """Track how long a room's openings/persons have been in their state."""
        # Openings: any sensor definitely open starts the clock.
        if any(sensor_is_open(self._state(e)) for e in room.openings):
            since = self._open_since.setdefault(room.room_id, now)
            remaining = room.open_delay * 60 - (now - since).total_seconds()
            self._arm_timer(room.room_id, "open", remaining)
        else:
            self._open_since.pop(room.room_id, None)
            self._cancel_timer(room.room_id, "open")

        # Persons: the clock runs while *all* of the room's persons are away.
        if room.persons and all(
            _person_is_away(self._state(p)) for p in room.persons
        ):
            since = self._away_since.setdefault(room.room_id, now)
            remaining = room.absence_delay * 60 - (now - since).total_seconds()
            self._arm_timer(room.room_id, "away", remaining)
        else:
            self._away_since.pop(room.room_id, None)
            self._cancel_timer(room.room_id, "away")

    def _arm_timer(self, room_id: str, kind: str, remaining: float) -> None:
        key = (room_id, kind)
        if key in self._timers:
            return  # already armed for this episode
        if remaining <= _TIMER_SLACK_SECONDS:
            return  # already elapsed; the evaluation that follows sees it

        @callback
        def _fire(_now: datetime) -> None:
            self._timers.pop(key, None)
            self._spawn(self.async_evaluate_room(room_id))

        self._timers[key] = async_call_later(self.hass, remaining, _fire)

    def _cancel_timer(self, room_id: str, kind: str) -> None:
        if cancel := self._timers.pop((room_id, kind), None):
            cancel()

    @staticmethod
    def _elapsed(since: datetime | None, now: datetime, minutes: int) -> bool:
        if since is None:
            return False
        return (now - since).total_seconds() >= minutes * 60 - _TIMER_SLACK_SECONDS

    # ------------------------------------------------------------ computation

    def _state(self, entity_id: str) -> str | None:
        state = self.hass.states.get(entity_id)
        return state.state if state else None

    def _inputs(self, room: RoomConfig, now: datetime) -> RoomInputs:
        g = self.store.global_state
        r = self.store.room(room.room_id)
        features = r["features"]
        today = dt_util.as_local(now).date()
        period_active = bool(g["period_override"]) or in_heating_period(
            today, tuple(g["period_start"]), tuple(g["period_end"])
        )
        return RoomInputs(
            period_active=period_active,
            absence_mode=bool(g["absence_mode"]),
            frost_temp=float(g["frost_temp"]),
            opening_shutdown_enabled=bool(features[FEATURE_OPENING_SHUTDOWN]),
            opening_open_beyond_delay=self._elapsed(
                self._open_since.get(room.room_id), now, room.open_delay
            ),
            absence_shutdown_enabled=bool(features[FEATURE_ABSENCE_SHUTDOWN]),
            has_persons=bool(room.persons),
            persons_away_beyond_delay=self._elapsed(
                self._away_since.get(room.room_id), now, room.absence_delay
            ),
            schedule_on=room.schedule is not None and self._state(room.schedule) == "on",
            skip_setback=bool(r["skip_setback"]),
            comfort_temp=float(r["comfort"]),
            setback_temp=float(r["setback"]),
            max_limit_enabled=bool(features[FEATURE_MAX_LIMIT]),
            max_temp=float(g["max_temp"]),
            boost_active=self.boost_active(room.room_id, now),
        )

    def _compute_status(self, room: RoomConfig, now: datetime) -> RoomStatus:
        inputs = self._inputs(room, now)
        decision = decide(inputs)
        room_absent_shutdown = (
            inputs.absence_shutdown_enabled
            and inputs.has_persons
            and inputs.persons_away_beyond_delay
        )
        in_comfort = (
            bool(room.thermostats)
            and inputs.period_active
            and not inputs.absence_mode
            and (
                inputs.boost_active  # explicit, beats room absence
                or (
                    not room_absent_shutdown
                    and (inputs.schedule_on or inputs.skip_setback)
                )
            )
        )
        opening_open = any(sensor_is_open(self._state(e)) for e in room.openings)
        beyond = self._elapsed(
            self._open_since.get(room.room_id), now, room.open_delay
        )
        unavailable = tuple(
            e
            for e in room.openings
            if self._state(e) is None or self._state(e) in _NOT_REPORTING
        )
        next_event = None
        schedule = self.hass.states.get(room.schedule) if room.schedule else None
        if schedule:
            raw = schedule.attributes.get("next_event")
            next_event = raw.isoformat() if isinstance(raw, datetime) else raw
        return RoomStatus(
            room_id=room.room_id,
            name=room.name,
            decision=decision,
            opening_open=opening_open,
            opening_pending=opening_open and not beyond,
            room_absent=self._elapsed(
                self._away_since.get(room.room_id), now, room.absence_delay
            ),
            unavailable_sensors=unavailable,
            next_change=next_event,
            heated_today=self.store.room(room.room_id)["heated_day"]
            == dt_util.as_local(now).date().isoformat(),
            in_setback=bool(room.thermostats)
            and self._state(room.schedule or "") != "on"
            and not self.store.room(room.room_id)["skip_setback"]
            and not inputs.boost_active,
            in_comfort=in_comfort,
        )

    def _compute_all(self, now: datetime) -> dict[str, RoomStatus]:
        return {rid: self._compute_status(room, now) for rid, room in self.rooms.items()}

    async def _async_update_data(self) -> dict[str, RoomStatus]:
        return self._compute_all(dt_util.utcnow())

    # -------------------------------------------------------------- evaluation

    async def async_evaluate_all(self) -> None:
        for room_id in self.rooms:
            await self.async_evaluate_room(room_id)

    def _apply_policy(
        self,
        room: RoomConfig,
        now: datetime,
        decision: Decision,
        opening_event: bool,
    ) -> str:
        """Decide how far ``decision`` may touch the thermostats.

        A door/window shutdown remembers the plan target of the moment. When
        the room is released again, the setpoint is only set if that target
        changed meanwhile; otherwise the thermostat keeps what it has (e.g. a
        manual setting). A door/window event that neither starts nor ends a
        shutdown (the delay is still running, a flapping sensor) does nothing.
        """
        room_state = self.store.room(room.room_id)
        shutdown_plan = room_state["opening_plan"]
        if decision.reason is Reason.OPENING:
            if shutdown_plan is None:
                plan = decide(
                    replace(self._inputs(room, now), opening_open_beyond_delay=False)
                )
                room_state["opening_plan"] = [plan.hvac_mode, plan.target]
                self.store.schedule_save()
            return _APPLY_FULL
        if shutdown_plan is not None:
            room_state["opening_plan"] = None
            self.store.schedule_save()
            if [decision.hvac_mode, decision.target] == shutdown_plan:
                return _APPLY_KEEP_SETPOINT
            return _APPLY_FULL
        return _APPLY_NONE if opening_event else _APPLY_FULL

    async def async_evaluate_room(
        self, room_id: str, *, opening_event: bool = False
    ) -> None:
        """Decide for one room, apply it to its thermostats, publish status.

        ``opening_event`` marks an evaluation caused by a door/window sensor
        changing its state (see :meth:`_apply_policy`).
        """
        room = self.rooms.get(room_id)
        if room is None:
            return
        async with self._lock:
            now = dt_util.utcnow()
            self._refresh_timers(room, now)
            self._note_heating(room, now)
            status = self._compute_status(room, now)
            policy = self._apply_policy(room, now, status.decision, opening_event)
            if policy != _APPLY_NONE:
                await self._async_apply(
                    room,
                    status.decision,
                    keep_setpoint=policy == _APPLY_KEEP_SETPOINT,
                )
            self.async_set_updated_data({**(self.data or {}), room_id: status})

    async def _async_apply(
        self, room: RoomConfig, decision: Decision, *, keep_setpoint: bool = False
    ) -> None:
        for entity_id in room.thermostats:
            state = self.hass.states.get(entity_id)
            if state is None or state.state in _NOT_REPORTING:
                continue
            if decision.hvac_mode == HVAC_OFF:
                if state.state != HVACMode.OFF:
                    await self._async_climate(
                        SERVICE_SET_HVAC_MODE, entity_id, {ATTR_HVAC_MODE: HVACMode.OFF}
                    )
                continue

            assert decision.target is not None
            target = decision.target
            if decision.reason is Reason.BOOST:
                # Full blast, but never above what this thermostat accepts.
                try:
                    target = min(target, float(state.attributes[ATTR_MAX_TEMP]))
                except (KeyError, TypeError, ValueError):
                    pass
            if state.state == HVACMode.OFF:
                modes = state.attributes.get(ATTR_HVAC_MODES) or []
                if HVACMode.HEAT not in modes:
                    _LOGGER.debug("%s does not support mode heat", entity_id)
                    continue
                await self._async_climate(
                    SERVICE_SET_HVAC_MODE, entity_id, {ATTR_HVAC_MODE: HVACMode.HEAT}
                )
            current = state.attributes.get(ATTR_TEMPERATURE)
            if current is not None and keep_setpoint:
                continue  # released after a door/window shutdown: setpoint stays
            if current is None or abs(float(current) - target) > _SETPOINT_TOLERANCE:
                await self._async_climate(
                    SERVICE_SET_TEMPERATURE,
                    entity_id,
                    {ATTR_TEMPERATURE: target},
                )

    async def _async_climate(
        self, service: str, entity_id: str, data: dict[str, Any]
    ) -> None:
        try:
            await self.hass.services.async_call(
                CLIMATE_DOMAIN,
                service,
                {ATTR_ENTITY_ID: entity_id, **data},
                blocking=True,
            )
        except HomeAssistantError as err:
            _LOGGER.warning("Could not call climate.%s on %s: %s", service, entity_id, err)

    async def _async_thermostat_changed(self, room: RoomConfig, entity_id: str) -> None:
        """React to a thermostat change: the two standing enforcements."""
        state = self.hass.states.get(entity_id)
        if state is None or state.state in _NOT_REPORTING:
            return
        now = dt_util.utcnow()
        self._note_heating(room, now)

        inputs = self._inputs(room, now)
        if not inputs.period_active:
            if state.state != HVACMode.OFF:
                await self._async_climate(
                    SERVICE_SET_HVAC_MODE, entity_id, {ATTR_HVAC_MODE: HVACMode.OFF}
                )
            return

        reason = decide(inputs).reason
        if reason is Reason.OPENING and state.state != HVACMode.OFF:
            # The room was shut off because a door/window stands open: a manual
            # switch-on is reverted right away.
            await self._async_climate(
                SERVICE_SET_HVAC_MODE, entity_id, {ATTR_HVAC_MODE: HVACMode.OFF}
            )
            return

        # A running boost keeps its setpoint even while a door/window or absence
        # shutdown overrides it, so it is still in place when the room is released.
        if inputs.max_limit_enabled and not inputs.boost_active:
            setpoint = state.attributes.get(ATTR_TEMPERATURE)
            if setpoint is not None and float(setpoint) > inputs.max_temp + _SETPOINT_TOLERANCE:
                await self._async_climate(
                    SERVICE_SET_TEMPERATURE, entity_id, {ATTR_TEMPERATURE: inputs.max_temp}
                )

    def _note_heating(self, room: RoomConfig, now: datetime) -> None:
        """Remember that the room asked for heat today.

        Thermostats here expose no ``hvac_action``; a room counts as heated
        when a thermostat in mode ``heat`` has a setpoint above its measured
        temperature.
        """
        for entity_id in room.thermostats:
            state = self.hass.states.get(entity_id)
            if state is None or state.state != HVACMode.HEAT:
                continue
            setpoint = state.attributes.get(ATTR_TEMPERATURE)
            measured = state.attributes.get("current_temperature")
            try:
                wants_heat = float(setpoint) > float(measured)
            except (TypeError, ValueError):
                continue
            if wants_heat:
                today = dt_util.as_local(now).date().isoformat()
                room_state = self.store.room(room.room_id)
                if room_state["heated_day"] != today:
                    room_state["heated_day"] = today
                    self.store.schedule_save()
                return

    # ------------------------------------------------------------------ setters

    async def async_set_absence_mode(self, enabled: bool) -> None:
        g = self.store.global_state
        g["absence_mode"] = enabled
        if not enabled:
            g["return_at"] = None
        self._expire_or_schedule_return()
        self.store.schedule_save()
        await self.async_evaluate_all()

    async def async_set_return_at(self, value: datetime | None) -> None:
        self.store.global_state["return_at"] = (
            dt_util.as_utc(value).isoformat() if value else None
        )
        self._expire_or_schedule_return()
        self.store.schedule_save()
        await self.async_evaluate_all()

    async def async_set_global(self, key: str, value: Any) -> None:
        self.store.global_state[key] = value
        self.store.schedule_save()
        await self.async_evaluate_all()

    async def async_set_period(
        self, start: tuple[int, int], end: tuple[int, int]
    ) -> None:
        g = self.store.global_state
        g["period_start"] = list(start)
        g["period_end"] = list(end)
        self.store.schedule_save()
        await self.async_evaluate_all()

    async def async_set_room_value(self, room_id: str, key: str, value: Any) -> None:
        self.store.room(room_id)[key] = value
        self.store.schedule_save()
        await self.async_evaluate_room(room_id)

    async def async_set_room_feature(
        self, room_id: str, feature: str, value: bool
    ) -> None:
        self.store.room(room_id)["features"][feature] = value
        self.store.schedule_save()
        await self.async_evaluate_room(room_id)

    # -------------------------------------------------------------------- boost

    def boost_until(self, room_id: str) -> datetime | None:
        """When the room's running boost ends (None if there is none)."""
        raw = self.store.room(room_id)["boost_until"]
        return dt_util.parse_datetime(raw) if raw else None

    def boost_active(self, room_id: str, now: datetime | None = None) -> bool:
        until = self.boost_until(room_id)
        return until is not None and until > (now or dt_util.utcnow())

    async def async_start_boost(self, room_id: str) -> None:
        """Heat the room at full power for its configured boost duration."""
        room = self.rooms.get(room_id)
        if room is None or not room.thermostats:
            return
        room_state = self.store.room(room_id)
        until = dt_util.utcnow() + timedelta(minutes=float(room_state["boost_minutes"]))
        room_state["boost_until"] = until.isoformat()
        self._schedule_boost_end(room_id)
        self.store.schedule_save()
        await self.async_evaluate_room(room_id)

    async def async_stop_boost(self, room_id: str) -> None:
        """End a running boost early; the room returns to its normal target."""
        if self.rooms.get(room_id) is None:
            return
        self._clear_boost(room_id)
        await self.async_evaluate_room(room_id)

    def _clear_boost(self, room_id: str) -> None:
        if cancel := self._boost_unsubs.pop(room_id, None):
            cancel()
        room_state = self.store.room(room_id)
        if room_state["boost_until"] is not None:
            room_state["boost_until"] = None
            self.store.schedule_save()

    def _schedule_boost_end(self, room_id: str) -> None:
        if cancel := self._boost_unsubs.pop(room_id, None):
            cancel()
        until = self.boost_until(room_id)
        if until is None:
            return

        @callback
        def _end(_now: datetime) -> None:
            self._boost_unsubs.pop(room_id, None)
            self._clear_boost(room_id)
            self._spawn(self.async_evaluate_room(room_id))

        self._boost_unsubs[room_id] = async_track_point_in_time(
            self.hass, _end, until
        )

    def _restore_boosts(self, now: datetime) -> None:
        """After a restart: drop expired boosts, re-arm the running ones."""
        for room_id in self.rooms:
            if self.boost_active(room_id, now):
                self._schedule_boost_end(room_id)
            else:
                self._clear_boost(room_id)

    # -------------------------------------------------------------- absence end

    def _expire_or_schedule_return(self) -> None:
        """(Re)arm the timer that ends the absence mode at the return time."""
        if self._return_unsub:
            self._return_unsub()
            self._return_unsub = None
        g = self.store.global_state
        if not g["absence_mode"] or not g["return_at"]:
            return
        return_at = dt_util.parse_datetime(g["return_at"])
        if return_at is None:
            g["return_at"] = None
            return

        if return_at <= dt_util.utcnow():
            self._spawn(self.async_set_absence_mode(False))
            return

        @callback
        def _return(_now: datetime) -> None:
            self._return_unsub = None
            self._spawn(self.async_set_absence_mode(False))

        self._return_unsub = async_track_point_in_time(self.hass, _return, return_at)

    # ----------------------------------------------------------------- helpers

    def room_state(self, room_id: str) -> dict[str, Any]:
        return self.store.room(room_id)

    @property
    def global_state(self) -> dict[str, Any]:
        return self.store.global_state

    def period_active_today(self) -> bool:
        g = self.store.global_state
        today: date = dt_util.now().date()
        return bool(g["period_override"]) or in_heating_period(
            today, tuple(g["period_start"]), tuple(g["period_end"])
        )
