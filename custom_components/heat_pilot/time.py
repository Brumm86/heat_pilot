"""Time platform: the global start and end of the forced night setback."""

from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HeatPilotConfigEntry
from .const import NIGHT_TIME_KEYS
from .coordinator import HeatPilotCoordinator
from .entity import HeatPilotEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeatPilotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(NightTime(coordinator, key) for key in NIGHT_TIME_KEYS)


class NightTime(HeatPilotEntity, TimeEntity):
    """Start or end of the night window (weekday or weekend nights)."""

    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator: HeatPilotCoordinator, key: str) -> None:
        super().__init__(coordinator, f"night_{key}")
        self._key = key

    @property
    def native_value(self) -> time:
        return self.coordinator.night_time(self._key)

    async def async_set_value(self, value: time) -> None:
        await self.coordinator.async_set_night_time(self._key, value)
