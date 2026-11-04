"""Time platform: daily time of the night setback (rooms without schedule)."""

from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HeatPilotConfigEntry
from .coordinator import HeatPilotCoordinator
from .entity import HeatPilotEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeatPilotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    for room_id, room in coordinator.rooms.items():
        if room.night_setback_available:
            async_add_entities(
                [NightSetbackTime(coordinator, room_id)], config_subentry_id=room_id
            )


class NightSetbackTime(HeatPilotEntity, TimeEntity):
    """When the room is lowered to its setback temperature (every day)."""

    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator: HeatPilotCoordinator, room_id: str) -> None:
        super().__init__(coordinator, "night_setback_time", room_id)

    @property
    def native_value(self) -> time:
        return self.coordinator.night_setback_time(self._room_id)

    async def async_set_value(self, value: time) -> None:
        await self.coordinator.async_set_night_setback(self._room_id, at=value)
