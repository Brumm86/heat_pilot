"""Coordinator for Heat Pilot.

There is nothing to poll. The coordinator is the event-driven engine: it
listens to schedules, door/window sensors, persons and thermostats, runs the
pure decision logic for each room and applies the result to the room's
thermostats. ``DataUpdateCoordinator`` is used as the single source of truth
for entities (``data`` maps room id -> :class:`RoomStatus`).

Heat Pilot only *acts* on events (schedule change, sensor/person change, a
toggle, a timer, start-up, midnight). A manual change on a thermostat stays
until the next such event. Two deliberate exceptions, both requested:

* outside the heating period thermostats are forced off again, and
* a room with the maximum-temperature limit enabled has any setpoint above
  the global maximum pulled back down.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
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
            self._spawn(self.async_evaluate_room(room_id))

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
        )

    def _compute_status(self, room: RoomConfig, now: datetime) -> RoomStatus:
        inputs = self._inputs(room, now)
        decision = decide(inputs)
        in_comfort = (
            bool(room.thermostats)
            and inputs.period_active
            and not inputs.absence_mode
            and not (
                inputs.absence_shutdown_enabled
                and inputs.has_persons
                and inputs.persons_away_beyond_delay
            )
            and (inputs.schedule_on or inputs.skip_setback)
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
            and not self.store.room(room.room_id)["skip_setback"],
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

    async def async_evaluate_room(self, room_id: str) -> None:
        """Decide for one room, apply it to its thermostats, publish status."""
        room = self.rooms.get(room_id)
        if room is None:
            return
        async with self._lock:
            now = dt_util.utcnow()
            self._refresh_timers(room, now)
            self._note_heating(room, now)
            status = self._compute_status(room, now)
            await self._async_apply(room, status.decision)
            self.async_set_updated_data({**(self.data or {}), room_id: status})

    async def _async_apply(self, room: RoomConfig, decision: Decision) -> None:
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
            if state.state == HVACMode.OFF:
                modes = state.attributes.get(ATTR_HVAC_MODES) or []
                if HVACMode.HEAT not in modes:
                    _LOGGER.debug("%s does not support mode heat", entity_id)
                    continue
                await self._async_climate(
                    SERVICE_SET_HVAC_MODE, entity_id, {ATTR_HVAC_MODE: HVACMode.HEAT}
                )
            current = state.attributes.get(ATTR_TEMPERATURE)
            if current is None or abs(float(current) - decision.target) > _SETPOINT_TOLERANCE:
                await self._async_climate(
                    SERVICE_SET_TEMPERATURE,
                    entity_id,
                    {ATTR_TEMPERATURE: decision.target},
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

        if inputs.max_limit_enabled:
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
