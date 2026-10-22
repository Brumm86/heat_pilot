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
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
)

from .const import (
    CONF_ABSENCE_DELAY,
    CONF_ADMIN_NOTIFY,
    CONF_DASHBOARD_PATH,
    CONF_DOOR_SENSORS,
    CONF_OPEN_DELAY,
    CONF_OVERHEAT_DELTA,
    CONF_OVERHEAT_MINUTES,
    CONF_PERSON_NOTIFY,
    CONF_PERSONS,
    CONF_SCHEDULE,
    CONF_THERMOSTATS,
    CONF_UNAVAILABLE_DELAY,
    CONF_VENTILATION_DELAY,
    CONF_WINDOW_SENSORS,
    DEFAULT_ABSENCE_DELAY,
    DEFAULT_DASHBOARD_PATH,
    DEFAULT_OPEN_DELAY,
    DEFAULT_OVERHEAT_DELTA,
    DEFAULT_OVERHEAT_MINUTES,
    DEFAULT_UNAVAILABLE_DELAY,
    DEFAULT_VENTILATION_DELAY,
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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return HeatPilotOptionsFlow()

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


def _notify_services(hass: HomeAssistant) -> list[str]:
    """Names of the available ``notify`` services (e.g. mobile_app_phone)."""
    services = hass.services.async_services_for_domain("notify")
    return sorted(name for name in services if name != "send_message")


def _notify_selector(hass: HomeAssistant, current: list[str]) -> SelectSelector:
    options = sorted(set(_notify_services(hass)) | {c for c in current if c})
    return SelectSelector(
        SelectSelectorConfig(options=options, mode="dropdown", custom_value=False)
    )


class HeatPilotOptionsFlow(OptionsFlow):
    """Notification settings: admin phone, person -> phone mapping, thresholds."""

    def __init__(self) -> None:
        self._options: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        current = dict(self.config_entry.options)
        if user_input is not None:
            self._options = {
                k: v for k, v in user_input.items() if v not in (None, "")
            }
            self._options[CONF_DASHBOARD_PATH] = self._options.get(
                CONF_DASHBOARD_PATH, DEFAULT_DASHBOARD_PATH
            )
            return await self.async_step_persons()

        schema = vol.Schema(
            {
                vol.Optional(CONF_ADMIN_NOTIFY): _notify_selector(
                    self.hass, [current.get(CONF_ADMIN_NOTIFY, "")]
                ),
                vol.Required(
                    CONF_VENTILATION_DELAY, default=DEFAULT_VENTILATION_DELAY
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=1, max=240, step=1, mode=NumberSelectorMode.BOX,
                        unit_of_measurement="min",
                    )
                ),
                vol.Required(
                    CONF_UNAVAILABLE_DELAY, default=DEFAULT_UNAVAILABLE_DELAY
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=1, max=1440, step=1, mode=NumberSelectorMode.BOX,
                        unit_of_measurement="min",
                    )
                ),
                vol.Required(
                    CONF_OVERHEAT_DELTA, default=DEFAULT_OVERHEAT_DELTA
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=0.5, max=15, step=0.5, mode=NumberSelectorMode.BOX,
                        unit_of_measurement="K",
                    )
                ),
                vol.Required(
                    CONF_OVERHEAT_MINUTES, default=DEFAULT_OVERHEAT_MINUTES
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=5, max=720, step=5, mode=NumberSelectorMode.BOX,
                        unit_of_measurement="min",
                    )
                ),
                vol.Optional(
                    CONF_DASHBOARD_PATH, default=DEFAULT_DASHBOARD_PATH
                ): TextSelector(),
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(schema, current),
        )

    async def async_step_persons(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        persons = sorted(self.hass.states.async_entity_ids("person"))
        if user_input is not None or not persons:
            mapping = {
                person: service
                for person, service in (user_input or {}).items()
                if service
            }
            options = {**self._options, CONF_PERSON_NOTIFY: mapping}
            for key in (CONF_VENTILATION_DELAY, CONF_UNAVAILABLE_DELAY, CONF_OVERHEAT_MINUTES):
                options[key] = int(options[key])
            return self.async_create_entry(data=options)

        current = self.config_entry.options.get(CONF_PERSON_NOTIFY, {})
        selector = _notify_selector(self.hass, list(current.values()))
        schema = vol.Schema({vol.Optional(person): selector for person in persons})
        return self.async_show_form(
            step_id="persons",
            data_schema=self.add_suggested_values_to_schema(schema, current),
        )
