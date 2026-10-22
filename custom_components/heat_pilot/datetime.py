"""Datetime platform: optional return time that ends the absence mode."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.datetime import DateTimeEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import HeatPilotConfigEntry
from .coordinator import HeatPilotCoordinator
from .entity import HeatPilotEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeatPilotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([ReturnDateTime(entry.runtime_data)])


class ReturnDateTime(HeatPilotEntity, DateTimeEntity):
    """When the absence mode should end by itself (optional).

    The value is cleared whenever the absence mode is switched off.
    """

    _attr_icon = "mdi:home-import-outline"

    def __init__(self, coordinator: HeatPilotCoordinator) -> None:
        super().__init__(coordinator, "return_at")

    @property
    def native_value(self) -> datetime | None:
        raw = self.coordinator.global_state["return_at"]
        return dt_util.parse_datetime(raw) if raw else None

    async def async_set_value(self, value: datetime) -> None:
        await self.coordinator.async_set_return_at(value)
