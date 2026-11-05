"""Heat Pilot: central, room-by-room heating control for Home Assistant."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import voluptuous as vol
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.loader import async_get_integration

from .const import (
    ATTR_END_DAY,
    ATTR_END_MONTH,
    ATTR_START_DAY,
    ATTR_START_MONTH,
    CARD_FILENAME,
    CARD_URL_PATH,
    DOMAIN,
    PAIRING_DURATION_SECONDS,
    SERVICE_PAIR_DOOR_SENSOR,
    SERVICE_SET_HEATING_PERIOD,
)
from .coordinator import HeatPilotCoordinator
from .notifier import HeatPilotNotifier
from .storage import HeatPilotStore

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.DATETIME,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
]

type HeatPilotConfigEntry = ConfigEntry[HeatPilotCoordinator]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SET_HEATING_PERIOD_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_START_MONTH): vol.All(vol.Coerce(int), vol.Range(min=1, max=12)),
        vol.Required(ATTR_START_DAY): vol.All(vol.Coerce(int), vol.Range(min=1, max=31)),
        vol.Required(ATTR_END_MONTH): vol.All(vol.Coerce(int), vol.Range(min=1, max=12)),
        vol.Required(ATTR_END_DAY): vol.All(vol.Coerce(int), vol.Range(min=1, max=31)),
    }
)


def _valid_month_day(month: int, day: int) -> bool:
    """Whether (month, day) exists in some year (29 Feb is accepted)."""
    try:
        date(2024, month, day)  # 2024 is a leap year
    except ValueError:
        return False
    return True


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register the integration's services (once, independent of entries)."""

    async def _async_set_heating_period(call: ServiceCall) -> None:
        start = (call.data[ATTR_START_MONTH], call.data[ATTR_START_DAY])
        end = (call.data[ATTR_END_MONTH], call.data[ATTR_END_DAY])
        for month, day in (start, end):
            if not _valid_month_day(month, day):
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="invalid_date",
                    translation_placeholders={"day": str(day), "month": str(month)},
                )
        entries = hass.config_entries.async_loaded_entries(DOMAIN)
        if not entries:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="not_loaded"
            )
        await entries[0].runtime_data.async_set_period(start, end)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_HEATING_PERIOD,
        _async_set_heating_period,
        schema=SET_HEATING_PERIOD_SCHEMA,
    )

    async def _async_pair_door_sensor(call: ServiceCall) -> None:
        """Open the ZHA network so a failed door sensor can re-join."""
        if not hass.services.has_service("zha", "permit"):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="zha_missing"
            )
        await hass.services.async_call(
            "zha", "permit", {"duration": PAIRING_DURATION_SECONDS}, blocking=True
        )

    hass.services.async_register(
        DOMAIN, SERVICE_PAIR_DOOR_SENSOR, _async_pair_door_sensor, schema=vol.Schema({})
    )
    await _async_register_frontend(hass)
    return True


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Serve the Lovelace card and load it on every dashboard.

    Three workarounds, all proven with the family_tasks card on Android:

    * the URL carries ``?v=<version>`` so the companion app's cache is busted
      on every release,
    * it is registered twice, as module and as ``es5`` script, because a
      WebView that Home Assistant does not classify as "latest" only loads
      the ES5 list (the card file has no import/export for that reason),
    * the card file re-defines itself once ``<home-assistant>`` is defined
      (see the end of the card file).
    """
    integration = await async_get_integration(hass, DOMAIN)
    www_dir = Path(__file__).parent / "www"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL_PATH, str(www_dir / CARD_FILENAME), cache_headers=False)]
    )
    card_url = f"{CARD_URL_PATH}?v={integration.version}"
    add_extra_js_url(hass, card_url)
    add_extra_js_url(hass, card_url, es5=True)


async def async_setup_entry(hass: HomeAssistant, entry: HeatPilotConfigEntry) -> bool:
    """Set up Heat Pilot from a config entry."""
    store = HeatPilotStore(hass)
    coordinator = HeatPilotCoordinator(hass, entry, store)
    await coordinator.async_setup()
    entry.runtime_data = coordinator

    # The hub device must exist before the room devices can point to it.
    device_registry = dr.async_get(hass)
    hub = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name="Heat Pilot",
        manufacturer="Heat Pilot",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
    for room_id, room in coordinator.rooms.items():
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, room_id)},
            name=room.name,
            manufacturer="Heat Pilot",
            model="Room",
            via_device_id=hub.id,
        )
    # The pairing button is gone (the card calls the service from an alert).
    entity_registry = er.async_get(hass)
    if button_id := entity_registry.async_get_entity_id(
        "button", DOMAIN, f"{entry.entry_id}_pair_door_sensor"
    ):
        entity_registry.async_remove(button_id)
    _prune_room_entities(hass, entry, coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    notifier = HeatPilotNotifier(hass, coordinator, dict(entry.options))
    notifier.async_start()
    entry.async_on_unload(notifier.async_stop)
    # Adding, changing or removing a room (subentry) reloads the entry.
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_update))
    return True


_ENTITY_DOMAINS = ("switch", "number", "sensor", "button", "time", "binary_sensor")
# Entities a room only has with thermostats (everything but the door warning).
_THERMOSTAT_ONLY_KEYS = (
    "comfort", "setback", "skip_setback", "boost", "boost_minutes", "plan_paused",
    "night_setback", "next_night_setback", "night_setback_later", "setpoint",
    "door_warning_setback_only", "door_warning_heating_only", "opening_shutdown",
    "absence_shutdown", "max_limit",
)


def _prune_room_entities(
    hass: HomeAssistant, entry: HeatPilotConfigEntry, coordinator: HeatPilotCoordinator
) -> None:
    """Remove registry entries of room entities that no longer exist."""
    registry = er.async_get(hass)
    for room_id, room in coordinator.rooms.items():
        stale = {"night_setback_time"}  # per-room night time, gone since 0.14
        if not room.thermostats:
            stale |= set(_THERMOSTAT_ONLY_KEYS)
        elif room.schedule is None:
            stale.add("plan_paused")
        for key in stale:
            for domain in _ENTITY_DOMAINS:
                if entity_id := registry.async_get_entity_id(
                    domain, DOMAIN, f"{entry.entry_id}_{room_id}_{key}"
                ):
                    registry.async_remove(entity_id)


async def _async_reload_on_update(hass: HomeAssistant, entry: HeatPilotConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: HeatPilotConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        coordinator = entry.runtime_data
        coordinator.async_shutdown_engine()
        await coordinator.store.async_save_now()
    return unloaded
