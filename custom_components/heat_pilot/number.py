"""Number platform: comfort/setback per room, frost and maximum globally."""

from __future__ import annotations

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HeatPilotConfigEntry
from .const import MAX_TEMP, MIN_TEMP
from .coordinator import HeatPilotCoordinator
from .entity import HeatPilotEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeatPilotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
            GlobalTemperatureNumber(coordinator, "frost_temp", MIN_TEMP, 15.0),
            GlobalTemperatureNumber(coordinator, "max_temp", 15.0, MAX_TEMP),
        ]
    )
    for room_id in coordinator.rooms:
        async_add_entities(
            [
                RoomTemperatureNumber(coordinator, room_id, "comfort"),
                RoomTemperatureNumber(coordinator, room_id, "setback"),
            ],
            config_subentry_id=room_id,
        )


class _TemperatureNumber(HeatPilotEntity, NumberEntity):
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_step = 0.5
    _attr_mode = NumberMode.BOX


class GlobalTemperatureNumber(_TemperatureNumber):
    """A house-wide temperature (frost protection or maximum)."""

    def __init__(
        self,
        coordinator: HeatPilotCoordinator,
        key: str,
        minimum: float,
        maximum: float,
    ) -> None:
        super().__init__(coordinator, key)
        self._key = key
        self._attr_native_min_value = minimum
        self._attr_native_max_value = maximum

    @property
    def native_value(self) -> float:
        return float(self.coordinator.global_state[self._key])

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_global(self._key, float(value))


class RoomTemperatureNumber(_TemperatureNumber):
    """A room's comfort or setback temperature."""

    _attr_native_min_value = MIN_TEMP
    _attr_native_max_value = MAX_TEMP

    def __init__(
        self, coordinator: HeatPilotCoordinator, room_id: str, key: str
    ) -> None:
        super().__init__(coordinator, key, room_id)
        self._key = key

    @property
    def native_value(self) -> float:
        return float(self.coordinator.room_state(self._room_id)[self._key])

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_room_value(
            self._room_id, self._key, float(value)
        )
