"""Button platform: open the ZHA network to (re-)pair a failed door sensor."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HeatPilotConfigEntry
from .const import DOMAIN, PAIRING_DURATION_SECONDS
from .coordinator import HeatPilotCoordinator
from .entity import HeatPilotEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeatPilotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([PairDoorSensorButton(entry.runtime_data)])


class PairDoorSensorButton(HeatPilotEntity, ButtonEntity):
    """Opens the ZHA network for a limited time.

    A door sensor that dropped off the network is re-joined by pressing this
    button and then holding the sensor's reset button until its LED blinks.
    ZHA recognises the device by its IEEE address, so it keeps its entities.
    """

    _attr_icon = "mdi:link-variant-plus"

    def __init__(self, coordinator: HeatPilotCoordinator) -> None:
        super().__init__(coordinator, "pair_door_sensor")

    async def async_press(self) -> None:
        if not self.hass.services.has_service("zha", "permit"):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="zha_missing"
            )
        await self.hass.services.async_call(
            "zha", "permit", {"duration": PAIRING_DURATION_SECONDS}, blocking=True
        )
