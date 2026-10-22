"""Switch platform: absence mode, period override and per-room toggles."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HeatPilotConfigEntry
from .const import ROOM_FEATURES
from .coordinator import HeatPilotCoordinator
from .entity import HeatPilotEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeatPilotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [AbsenceModeSwitch(coordinator), PeriodOverrideSwitch(coordinator)]
    )
    for room_id in coordinator.rooms:
        entities: list[SwitchEntity] = [
            RoomFeatureSwitch(coordinator, room_id, feature)
            for feature in ROOM_FEATURES
        ]
        entities.append(SkipSetbackSwitch(coordinator, room_id))
        async_add_entities(entities, config_subentry_id=room_id)


class AbsenceModeSwitch(HeatPilotEntity, SwitchEntity):
    """Whole-house absence: every thermostat goes to frost protection."""

    _attr_icon = "mdi:home-export-outline"

    def __init__(self, coordinator: HeatPilotCoordinator) -> None:
        super().__init__(coordinator, "absence_mode")

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.global_state["absence_mode"])

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_absence_mode(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_absence_mode(False)


class PeriodOverrideSwitch(HeatPilotEntity, SwitchEntity):
    """Force the heating period to be active regardless of the dates."""

    _attr_icon = "mdi:radiator"

    def __init__(self, coordinator: HeatPilotCoordinator) -> None:
        super().__init__(coordinator, "period_override")

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.global_state["period_override"])

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_global("period_override", True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_global("period_override", False)


class RoomFeatureSwitch(HeatPilotEntity, SwitchEntity):
    """A per-room on/off option (door warning, shutdowns, max limit)."""

    def __init__(
        self, coordinator: HeatPilotCoordinator, room_id: str, feature: str
    ) -> None:
        super().__init__(coordinator, feature, room_id)
        self._feature = feature

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.room_state(self._room_id)["features"][self._feature])

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_room_feature(self._room_id, self._feature, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_room_feature(self._room_id, self._feature, False)


class SkipSetbackSwitch(HeatPilotEntity, SwitchEntity):
    """Skip the next setback phase; ends itself at the next comfort start."""

    _attr_icon = "mdi:weather-night-off"

    def __init__(self, coordinator: HeatPilotCoordinator, room_id: str) -> None:
        super().__init__(coordinator, "skip_setback", room_id)

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.room_state(self._room_id)["skip_setback"])

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_room_value(self._room_id, "skip_setback", True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_room_value(self._room_id, "skip_setback", False)
