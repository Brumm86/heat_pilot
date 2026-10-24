"""Persistent runtime state for Heat Pilot.

Room *definitions* (thermostats, sensors, schedule, persons) live in the
config entry's subentries and are edited through the config flow. What is
stored here is the *runtime* state that users change from the dashboard and
that has to survive restarts: toggles, temperatures, the absence mode, the
heating period and the one-shot "skip setback" flags.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import (
    DEFAULT_COMFORT_TEMP,
    DEFAULT_FROST_TEMP,
    DEFAULT_MAX_TEMP,
    DEFAULT_PERIOD_END,
    DEFAULT_PERIOD_START,
    DEFAULT_SETBACK_TEMP,
    FEATURES_DEFAULT_OFF,
    ROOM_FEATURES,
    STORAGE_KEY,
    STORAGE_VERSION,
)

SAVE_DELAY = 1.0  # seconds; coalesces bursts of changes into one write


def _default_global() -> dict[str, Any]:
    return {
        "absence_mode": False,
        "return_at": None,  # ISO string, tz-aware, or None
        "frost_temp": DEFAULT_FROST_TEMP,
        "max_temp": DEFAULT_MAX_TEMP,
        "period_start": list(DEFAULT_PERIOD_START),
        "period_end": list(DEFAULT_PERIOD_END),
        "period_override": False,
    }


def _default_room() -> dict[str, Any]:
    return {
        "comfort": DEFAULT_COMFORT_TEMP,
        "setback": DEFAULT_SETBACK_TEMP,
        "skip_setback": False,
        "features": {feature: feature not in FEATURES_DEFAULT_OFF for feature in ROOM_FEATURES},
        # ISO date of the last day on which the room asked for heat; used to
        # decide whether a room was "heated today".
        "heated_day": None,
    }


class HeatPilotStore:
    """Thin wrapper around :class:`Store` with defaults and typed access."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, STORAGE_KEY
        )
        self.data: dict[str, Any] = {
            "global": _default_global(),
            "rooms": {},
        }

    async def async_load(self) -> None:
        """Load stored state, filling in defaults for anything missing."""
        stored = await self._store.async_load()
        if not stored:
            return
        merged_global = _default_global()
        merged_global.update(stored.get("global", {}))
        self.data["global"] = merged_global
        rooms: dict[str, Any] = {}
        for room_id, room in stored.get("rooms", {}).items():
            merged = _default_room()
            features = merged["features"]
            features.update(room.get("features", {}))
            merged.update({k: v for k, v in room.items() if k != "features"})
            merged["features"] = features
            rooms[room_id] = merged
        self.data["rooms"] = rooms

    def room(self, room_id: str) -> dict[str, Any]:
        """Return (creating on first access) the state dict of one room."""
        return self.data["rooms"].setdefault(room_id, _default_room())

    def forget_rooms_except(self, keep: set[str]) -> None:
        """Drop state of rooms that no longer exist."""
        for room_id in list(self.data["rooms"]):
            if room_id not in keep:
                del self.data["rooms"][room_id]

    @property
    def global_state(self) -> dict[str, Any]:
        return self.data["global"]

    def schedule_save(self) -> None:
        """Persist soon (debounced)."""
        self._store.async_delay_save(lambda: deepcopy(self.data), SAVE_DELAY)

    async def async_save_now(self) -> None:
        await self._store.async_save(deepcopy(self.data))
