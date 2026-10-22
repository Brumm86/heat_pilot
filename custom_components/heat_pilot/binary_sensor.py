"""Binary sensor platform: is a door or window of the room open."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
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
        if room.openings:
            async_add_entities(
                [RoomOpeningBinarySensor(coordinator, room_id)],
                config_subentry_id=room_id,
            )


class RoomOpeningBinarySensor(HeatPilotEntity, BinarySensorEntity):
    """On while any door/window sensor of the room reports open.

    Unavailable sensors count as closed, same as in the shutdown logic.
    """

    _attr_device_class = BinarySensorDeviceClass.OPENING

    def __init__(self, coordinator: HeatPilotCoordinator, room_id: str) -> None:
        super().__init__(coordinator, "opening", room_id)

    @property
    def is_on(self) -> bool | None:
        status = self.room_status
        return status.opening_open if status else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        status = self.room_status
        if status is None:
            return None
        return {
            "shutdown_pending": status.opening_pending,
            "unavailable_sensors": list(status.unavailable_sensors),
        }
