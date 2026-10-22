"""Config flow for Heat Pilot.

The main entry only exists once and carries no data. Each room is a *config
subentry* (``SUBENTRY_ROOM``) that can be added, reconfigured and removed
independently from the integration's page in Settings.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)

from .const import (
    CONF_ABSENCE_DELAY,
    CONF_DOOR_SENSORS,
    CONF_OPEN_DELAY,
    CONF_PERSONS,
    CONF_SCHEDULE,
    CONF_THERMOSTATS,
    CONF_WINDOW_SENSORS,
    DEFAULT_ABSENCE_DELAY,
    DEFAULT_OPEN_DELAY,
    DOMAIN,
    SUBENTRY_ROOM,
)

DEFAULT_TITLE = "Heat Pilot"


def _room_schema() -> vol.Schema:
    """Schema of the room form (shared by add and reconfigure)."""
    return vol.Schema(
        {
            vol.Required(CONF_NAME): TextSelector(),
            vol.Required(CONF_THERMOSTATS, default=[]): EntitySelector(
                EntitySelectorConfig(domain="climate", multiple=True)
            ),
            vol.Required(CONF_SCHEDULE): EntitySelector(
                EntitySelectorConfig(domain="schedule")
            ),
            vol.Optional(CONF_DOOR_SENSORS, default=[]): EntitySelector(
                EntitySelectorConfig(domain="binary_sensor", multiple=True)
            ),
            vol.Optional(CONF_WINDOW_SENSORS, default=[]): EntitySelector(
                EntitySelectorConfig(domain="binary_sensor", multiple=True)
            ),
            vol.Optional(CONF_PERSONS, default=[]): EntitySelector(
                EntitySelectorConfig(domain="person", multiple=True)
            ),
            vol.Required(CONF_OPEN_DELAY, default=DEFAULT_OPEN_DELAY): NumberSelector(
                NumberSelectorConfig(
                    min=1, max=120, step=1, mode=NumberSelectorMode.BOX,
                    unit_of_measurement="min",
                )
            ),
            vol.Required(
                CONF_ABSENCE_DELAY, default=DEFAULT_ABSENCE_DELAY
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1, max=240, step=1, mode=NumberSelectorMode.BOX,
                    unit_of_measurement="min",
                )
            ),
        }
    )


class HeatPilotConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up Heat Pilot once; rooms are added as subentries afterwards."""

    VERSION = 1

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        return {SUBENTRY_ROOM: RoomSubentryFlow}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title=DEFAULT_TITLE, data={})
        return self.async_show_form(step_id="user")


class RoomSubentryFlow(ConfigSubentryFlow):
    """Add or reconfigure one room."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        return await self._async_room_form("user", user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        return await self._async_room_form("reconfigure", user_input)

    async def _async_room_form(
        self, step_id: str, user_input: dict[str, Any] | None
    ) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_entry()

        if user_input is not None:
            errors = self._validate(entry, step_id, user_input)
            if not errors:
                data = {k: v for k, v in user_input.items() if k != CONF_NAME}
                data[CONF_OPEN_DELAY] = int(data[CONF_OPEN_DELAY])
                data[CONF_ABSENCE_DELAY] = int(data[CONF_ABSENCE_DELAY])
                title = user_input[CONF_NAME].strip()
                if step_id == "user":
                    return self.async_create_entry(title=title, data=data)
                return self.async_update_and_abort(
                    entry,
                    self._get_reconfigure_subentry(),
                    title=title,
                    data=data,
                )

        if user_input is not None:
            suggested = user_input
        elif step_id == "reconfigure":
            subentry = self._get_reconfigure_subentry()
            suggested = {CONF_NAME: subentry.title, **subentry.data}
        else:
            suggested = {}

        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(_room_schema(), suggested),
            errors=errors,
        )

    def _validate(
        self, entry: ConfigEntry, step_id: str, user_input: dict[str, Any]
    ) -> dict[str, str]:
        errors: dict[str, str] = {}
        if not user_input.get(CONF_THERMOSTATS):
            errors[CONF_THERMOSTATS] = "no_thermostat"

        name = user_input[CONF_NAME].strip()
        if not name:
            errors[CONF_NAME] = "name_required"
        else:
            own_id = (
                self._get_reconfigure_subentry().subentry_id
                if step_id == "reconfigure"
                else None
            )
            for subentry in entry.subentries.values():
                if (
                    subentry.subentry_type == SUBENTRY_ROOM
                    and subentry.subentry_id != own_id
                    and subentry.title.strip().casefold() == name.casefold()
                ):
                    errors[CONF_NAME] = "name_exists"
                    break
        return errors
