"""Shared entity base for Heat Pilot."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HeatPilotCoordinator, RoomStatus


class HeatPilotEntity(CoordinatorEntity[HeatPilotCoordinator]):
    """Base class: sets up naming, unique id and the device a entity sits on.

    Entities without ``room_id`` belong to the global "Heat Pilot" device;
    entities with one belong to that room's device. The link from the room
    devices to the hub device (``via_device_id``) is set in ``async_setup_entry``.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HeatPilotCoordinator,
        key: str,
        room_id: str | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._room_id = room_id
        self._attr_translation_key = key
        entry_id = coordinator.config_entry.entry_id
        if room_id is None:
            self._attr_unique_id = f"{entry_id}_{key}"
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, entry_id)},
                name="Heat Pilot",
                manufacturer="Heat Pilot",
                entry_type=DeviceEntryType.SERVICE,
            )
        else:
            self._attr_unique_id = f"{entry_id}_{room_id}_{key}"
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, room_id)},
                name=coordinator.rooms[room_id].name,
                manufacturer="Heat Pilot",
                model="Room",
            )

    @property
    def room_status(self) -> RoomStatus | None:
        """Latest status of this entity's room (None for global entities)."""
        if self._room_id is None or not self.coordinator.data:
            return None
        return self.coordinator.data.get(self._room_id)
