"""Number platform: comfort/setback per room, frost and maximum globally."""

from __future__ import annotations

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberMode,
)
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from . import HeatPilotConfigEntry
from .const import (
    BOOST_STEP_MINUTES,
    MAX_BOOST_MINUTES,
    MAX_TEMP,
    MIN_BOOST_MINUTES,
    MIN_TEMP,
)
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
    for room_id, room in coordinator.rooms.items():
        if not room.thermostats:
            continue  # heated outside Home Assistant: nothing to set
        async_add_entities(
            [
                RoomTemperatureNumber(coordinator, room_id, "comfort"),
                RoomTemperatureNumber(coordinator, room_id, "setback"),
                BoostDurationNumber(coordinator, room_id),
                RoomSetpointNumber(coordinator, room_id),
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


class BoostDurationNumber(HeatPilotEntity, NumberEntity):
    """How long a room's boost lasts (applies to the next boost)."""

    _attr_device_class = NumberDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_native_min_value = MIN_BOOST_MINUTES
    _attr_native_max_value = MAX_BOOST_MINUTES
    _attr_native_step = BOOST_STEP_MINUTES
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: HeatPilotCoordinator, room_id: str) -> None:
        super().__init__(coordinator, "boost_minutes", room_id)

    @property
    def native_value(self) -> float:
        return float(self.coordinator.room_state(self._room_id)["boost_minutes"])

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_room_value(
            self._room_id, "boost_minutes", float(value)
        )


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


class RoomSetpointNumber(_TemperatureNumber):
    """Slider for the setpoint of all the room's thermostats.

    Shows the mean setpoint of the thermostats that report one; setting it
    sets every thermostat of the room (switching switched-off ones to heat).
    Heat Pilot's standing rules (maximum, open door, night setback) still apply.
    """

    _attr_native_min_value = MIN_TEMP
    _attr_native_max_value = MAX_TEMP
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: HeatPilotCoordinator, room_id: str) -> None:
        super().__init__(coordinator, "setpoint", room_id)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        thermostats = list(self.coordinator.rooms[self._room_id].thermostats)

        @callback
        def _changed(_event: Event) -> None:
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(self.hass, thermostats, _changed)
        )

    @property
    def native_value(self) -> float | None:
        values: list[float] = []
        for entity_id in self.coordinator.rooms[self._room_id].thermostats:
            state = self.hass.states.get(entity_id)
            if state is None:
                continue
            try:
                values.append(float(state.attributes["temperature"]))
            except (KeyError, TypeError, ValueError):
                continue
        if not values:
            return None
        return round(sum(values) / len(values) * 2) / 2

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_room_setpoint(self._room_id, float(value))
