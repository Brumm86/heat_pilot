"""Button platform: push the start of tonight's night setback back by an hour."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
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
                [NightSetbackLaterButton(coordinator, room_id)],
                config_subentry_id=room_id,
            )


class NightSetbackLaterButton(HeatPilotEntity, ButtonEntity):
    """Each press moves the start of the current/next night setback back by 1 h."""

    _attr_icon = "mdi:clock-plus-outline"

    def __init__(self, coordinator: HeatPilotCoordinator, room_id: str) -> None:
        super().__init__(coordinator, "night_setback_later", room_id)

    async def async_press(self) -> None:
        await self.coordinator.async_shift_night(self._room_id)
