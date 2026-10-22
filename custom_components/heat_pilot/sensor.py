"""Sensor platform: per-room status and the heating-period state."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HeatPilotConfigEntry
from .coordinator import HeatPilotCoordinator
from .decision import Reason
from .entity import HeatPilotEntity

PERIOD_ACTIVE = "active"
PERIOD_INACTIVE = "inactive"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeatPilotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([HeatingPeriodSensor(coordinator)])
    for room_id in coordinator.rooms:
        async_add_entities(
            [RoomStatusSensor(coordinator, room_id)], config_subentry_id=room_id
        )


class RoomStatusSensor(HeatPilotEntity, SensorEntity):
    """Why the room has its current target (comfort, setback, opening ...)."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [reason.value for reason in Reason]  # noqa: RUF012

    def __init__(self, coordinator: HeatPilotCoordinator, room_id: str) -> None:
        super().__init__(coordinator, "status", room_id)

    @property
    def native_value(self) -> str | None:
        status = self.room_status
        return status.decision.reason.value if status else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        status = self.room_status
        if status is None:
            return None
        return {
            "hvac_mode": status.decision.hvac_mode,
            "target_temperature": status.decision.target,
            "next_change": status.next_change,
            "heated_today": status.heated_today,
            "opening_open": status.opening_open,
            "opening_pending": status.opening_pending,
            "room_absent": status.room_absent,
            "unavailable_sensors": list(status.unavailable_sensors),
        }


class HeatingPeriodSensor(HeatPilotEntity, SensorEntity):
    """Whether the heating period is active today."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [PERIOD_ACTIVE, PERIOD_INACTIVE]  # noqa: RUF012
    _attr_icon = "mdi:calendar-range"

    def __init__(self, coordinator: HeatPilotCoordinator) -> None:
        super().__init__(coordinator, "heating_period")

    @property
    def native_value(self) -> str:
        return PERIOD_ACTIVE if self.coordinator.period_active_today() else PERIOD_INACTIVE

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        g = self.coordinator.global_state
        return {
            "start_month": g["period_start"][0],
            "start_day": g["period_start"][1],
            "end_month": g["period_end"][0],
            "end_day": g["period_end"][1],
            "override": g["period_override"],
        }
