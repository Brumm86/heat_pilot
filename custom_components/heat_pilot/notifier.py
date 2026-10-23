"""Push notifications: door warnings, ventilation reminders, admin alerts.

Notifications are Android-companion-app style: persistent and sticky, with a
chronometer, one ``tag`` per condition so repeats replace each other, and
cleared again as soon as the condition ends. Every phone message is mirrored
as a persistent notification in Home Assistant's notification centre (same
``tag``-derived id, dismissed together with the phone message); tapping the
phone message opens that notification centre.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.components import persistent_notification
from homeassistant.const import STATE_HOME, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .alerts import Episode, Plan, is_due, is_overheating
from .const import (
    ADMIN_REPEAT_HOURS,
    ADMIN_WINDOW,
    CONF_ADMIN_NOTIFY,
    CONF_DASHBOARD_PATH,
    CONF_OVERHEAT_DELTA,
    CONF_OVERHEAT_MINUTES,
    CONF_PERSON_NOTIFY,
    CONF_UNAVAILABLE_DELAY,
    CONF_VENTILATION_DELAY,
    DEFAULT_DASHBOARD_PATH,
    DEFAULT_OVERHEAT_DELTA,
    DEFAULT_OVERHEAT_MINUTES,
    DEFAULT_UNAVAILABLE_DELAY,
    DEFAULT_VENTILATION_DELAY,
    DOOR_WARNING_MAX,
    DOOR_WARNING_REPEAT_MINUTES,
    FEATURE_DOOR_WARNING,
    FEATURE_OPENING_SHUTDOWN,
)
from .decision import HVAC_OFF, Reason

if TYPE_CHECKING:
    from .coordinator import HeatPilotCoordinator, RoomConfig

_LOGGER = logging.getLogger(__name__)

TICK = timedelta(seconds=15)
_CHANNEL_DOOR = "Heat Pilot Türwarnung"
_CHANNEL_ALERT = "Heat Pilot Störung"

Key = tuple[str, str]  # (kind, id)

# Opening this query on any dashboard makes the frontend card script show the
# notification centre (see www/heat-pilot-card.js).
NOTIFICATIONS_QUERY = "heat_pilot_notifications=1"

_TEXT = {
    "de": {
        "door_title": "Tür offen – {room}",
        "door_msg": "Die Tür im Raum {room} ist seit {minutes} Min. offen.",
        "vent_title": "Fenster noch offen – {room}",
        "vent_msg": (
            "Das Fenster im Raum {room} ist seit {minutes} Min. offen, "
            "die Heizung ist aus. Bitte schließen."
        ),
        "alert_title": "Heat Pilot Störung",
        "unavailable": "{name} ({room}) ist seit {minutes} Min. nicht erreichbar.",
        "overheat": (
            "{room}: {name} liegt seit {minutes} Min. mehr als {delta} K über dem Sollwert."
        ),
    },
    "en": {
        "door_title": "Door open – {room}",
        "door_msg": "The door in {room} has been open for {minutes} min.",
        "vent_title": "Window still open – {room}",
        "vent_msg": (
            "The window in {room} has been open for {minutes} min and "
            "heating is off. Please close it."
        ),
        "alert_title": "Heat Pilot fault",
        "unavailable": "{name} ({room}) has been unreachable for {minutes} min.",
        "overheat": (
            "{room}: {name} has been more than {delta} K above its setpoint "
            "for {minutes} min."
        ),
    },
}


class HeatPilotNotifier:
    """Tracks conditions per room/device and sends notifications."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: HeatPilotCoordinator,
        options: dict[str, Any],
    ) -> None:
        self.hass = hass
        self.coordinator = coordinator
        self._admin: str | None = options.get(CONF_ADMIN_NOTIFY) or None
        self._person_notify: dict[str, str] = dict(options.get(CONF_PERSON_NOTIFY, {}))
        self._dashboard = options.get(CONF_DASHBOARD_PATH, DEFAULT_DASHBOARD_PATH)
        self._vent_delay = int(options.get(CONF_VENTILATION_DELAY, DEFAULT_VENTILATION_DELAY))
        self._unavail_delay = int(
            options.get(CONF_UNAVAILABLE_DELAY, DEFAULT_UNAVAILABLE_DELAY)
        )
        self._overheat_delta = float(options.get(CONF_OVERHEAT_DELTA, DEFAULT_OVERHEAT_DELTA))
        self._overheat_minutes = int(
            options.get(CONF_OVERHEAT_MINUTES, DEFAULT_OVERHEAT_MINUTES)
        )
        language = (hass.config.language or "en").split("-")[0]
        self._text = _TEXT.get(language, _TEXT["en"])
        self._episodes: dict[Key, Episode] = {}
        self._unsub: CALLBACK_TYPE | None = None

    # -------------------------------------------------------------- lifecycle

    @callback
    def async_start(self) -> None:
        self._unsub = async_track_time_interval(self.hass, self._async_tick, TICK)
        self.hass.async_create_task(self._async_tick(dt_util.utcnow()))

    @callback
    def async_stop(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None

    # ------------------------------------------------------------------ plans

    def _plan(self, kind: str, room: RoomConfig | None) -> Plan:
        if kind == "door" and room is not None:
            return Plan(
                first_delay=timedelta(minutes=room.open_delay),
                repeat=timedelta(minutes=DOOR_WARNING_REPEAT_MINUTES),
                max_sent=DOOR_WARNING_MAX,
            )
        if kind == "vent":
            return Plan(first_delay=timedelta(minutes=self._vent_delay), max_sent=1)
        first = (
            timedelta(minutes=self._overheat_minutes)
            if kind == "overheat"
            else timedelta(minutes=self._unavail_delay)
        )
        return Plan(
            first_delay=first,
            repeat=timedelta(hours=ADMIN_REPEAT_HOURS),
            window=ADMIN_WINDOW,
        )

    # ------------------------------------------------------------ observation

    def _state(self, entity_id: str) -> Any:
        return self.hass.states.get(entity_id)

    def _open_since(self, entity_ids: tuple[str, ...]) -> datetime | None:
        """Earliest moment since which any of the sensors reads ``on``."""
        times = [
            s.last_changed
            for eid in entity_ids
            if (s := self._state(eid)) is not None and s.state == STATE_ON
        ]
        return min(times) if times else None

    def _observe(self, now: datetime) -> dict[Key, tuple[datetime, dict[str, Any]]]:
        """Current conditions: key -> (since, message context)."""
        active: dict[Key, tuple[datetime, dict[str, Any]]] = {}
        data = self.coordinator.data or {}
        for room in self.coordinator.rooms.values():
            features = self.coordinator.room_state(room.room_id)["features"]
            status = data.get(room.room_id)

            if features.get(FEATURE_DOOR_WARNING) and (
                since := self._open_since(room.door_sensors)
            ):
                active[("door", room.room_id)] = (since, {"room": room.name})

            if (
                features.get(FEATURE_OPENING_SHUTDOWN)
                and status is not None
                and room.thermostats
                and status.decision.reason is Reason.OPENING
                and (since := self._open_since(room.window_sensors))
            ):
                active[("vent", room.room_id)] = (since, {"room": room.name})

            for entity_id in room.openings + room.thermostats:
                state = self._state(entity_id)
                if state is not None and state.state == STATE_UNAVAILABLE:
                    active[("unavailable", entity_id)] = (
                        state.last_changed,
                        {"room": room.name, "entity_id": entity_id},
                    )

            for entity_id in room.thermostats:
                state = self._state(entity_id)
                if state is not None and is_overheating(
                    state.state,
                    state.attributes.get("temperature"),
                    state.attributes.get("current_temperature"),
                    self._overheat_delta,
                ):
                    active[("overheat", entity_id)] = (
                        now,
                        {"room": room.name, "entity_id": entity_id},
                    )
        return active

    def _room_for(self, key: Key) -> RoomConfig | None:
        kind, ident = key
        if kind in ("door", "vent"):
            return self.coordinator.rooms.get(ident)
        return None

    def _suppressed(self, key: Key) -> bool:
        """Door/ventilation messages only make sense while heating matters."""
        kind, room_id = key
        if kind not in ("door", "vent"):
            return False
        if not self.coordinator.period_active_today():
            return True
        room = self.coordinator.rooms.get(room_id)
        if kind == "door" and room is not None and room.externally_heated:
            # Heated outside Home Assistant (e.g. underfloor heating): the
            # thermostats say nothing about whether the room is heated.
            return False
        status = (self.coordinator.data or {}).get(room_id)
        if status is None:
            return False
        return status.decision.hvac_mode == HVAC_OFF and not status.heated_today

    # ------------------------------------------------------------------- tick

    async def _async_tick(self, now: datetime) -> None:
        now = dt_util.utcnow()
        local_hour = dt_util.as_local(now).hour
        active = self._observe(now)

        for key in list(self._episodes):
            if key not in active:
                episode = self._episodes.pop(key)
                if episode.sent:
                    persistent_notification.async_dismiss(
                        self.hass, self._notification_id(key)
                    )
                    if key[0] in ("door", "vent"):
                        await self._async_clear(key)
        for key, (since, _ctx) in active.items():
            self._episodes.setdefault(key, Episode(since=since))

        for key, episode in self._episodes.items():
            if self._suppressed(key):
                continue
            plan = self._plan(key[0], self._room_for(key))
            if is_due(episode, plan, now, local_hour):
                episode.sent += 1
                episode.last_sent = now
                await self._async_send(key, episode, active[key][1], now)

    # ----------------------------------------------------------------- sending

    def _recipients(self, kind: str) -> list[str]:
        if kind in ("door", "vent"):
            return [
                service
                for person, service in self._person_notify.items()
                if (s := self._state(person)) is not None and s.state == STATE_HOME
            ]
        return [self._admin] if self._admin else []

    def _click_action(self) -> str:
        """Dashboard URL that opens Home Assistant's notification centre."""
        separator = "&" if "?" in self._dashboard else "?"
        return f"{self._dashboard}{separator}{NOTIFICATIONS_QUERY}"

    @staticmethod
    def _notification_id(key: Key) -> str:
        return f"heat_pilot_{key[0]}_{key[1]}"

    def _name(self, entity_id: str) -> str:
        state = self._state(entity_id)
        return str(state.attributes.get("friendly_name", entity_id)) if state else entity_id

    def _build(
        self, key: Key, episode: Episode, ctx: dict[str, Any], now: datetime
    ) -> tuple[str, str, dict[str, Any]]:
        kind = key[0]
        minutes = max(1, int((now - episode.since).total_seconds() // 60))
        text = self._text
        room = ctx["room"]
        if kind in ("door", "vent"):
            title = text[f"{kind}_title"].format(room=room)
            message = text[f"{kind}_msg"].format(room=room, minutes=minutes)
            data = {
                "tag": f"heat_pilot_{kind}_{key[1]}",
                "channel": _CHANNEL_DOOR,
                "importance": "high",
                "priority": "high",
                "ttl": 0,
                "persistent": True,
                "sticky": True,
                "chronometer": True,
                "when": int(episode.since.timestamp()),
                "color": "#e53935",
                "notification_icon": "mdi:door-open",
                "clickAction": self._click_action(),
            }
            return title, message, data
        name = self._name(ctx["entity_id"])
        template = text["unavailable" if kind == "unavailable" else "overheat"]
        message = template.format(
            name=name, room=room, minutes=minutes, delta=self._overheat_delta
        )
        data = {
            "tag": f"heat_pilot_{kind}_{key[1]}",
            "channel": _CHANNEL_ALERT,
            "importance": "high",
            "priority": "high",
            "ttl": 0,
            "color": "#e53935",
            "notification_icon": "mdi:thermometer-alert"
            if kind == "overheat"
            else "mdi:alert-circle",
            "clickAction": self._click_action(),
        }
        return text["alert_title"], message, data

    async def _async_send(
        self, key: Key, episode: Episode, ctx: dict[str, Any], now: datetime
    ) -> None:
        recipients = self._recipients(key[0])
        if not recipients:
            _LOGGER.debug("No notification recipients for %s", key)
            return
        title, message, data = self._build(key, episode, ctx, now)
        persistent_notification.async_create(
            self.hass,
            message,
            title=title,
            notification_id=self._notification_id(key),
        )
        for service in recipients:
            await self._async_call(service, {"title": title, "message": message, "data": data})

    async def _async_clear(self, key: Key) -> None:
        for service in set(self._person_notify.values()):
            await self._async_call(
                service,
                {"message": "clear_notification", "data": {"tag": self._notification_id(key)}},
            )

    async def _async_call(self, service: str, payload: dict[str, Any]) -> None:
        name = service.removeprefix("notify.")
        if not self.hass.services.has_service("notify", name):
            _LOGGER.warning("Notify service notify.%s does not exist", name)
            return
        try:
            await self.hass.services.async_call("notify", name, payload, blocking=True)
        except Exception:
            _LOGGER.exception("Sending notification via notify.%s failed", name)
