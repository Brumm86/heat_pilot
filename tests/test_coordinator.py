"""Scenario tests for the Heat Pilot coordinator with simulated devices."""

from __future__ import annotations

from datetime import timedelta

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.heat_pilot.const import DOMAIN, SUBENTRY_ROOM

THERMOSTAT = "climate.room"
SCHEDULE = "schedule.room"
DOOR = "binary_sensor.room_door"
PERSON = "person.kid"

ROOM_DATA = {
    "thermostats": [THERMOSTAT],
    "schedule": SCHEDULE,
    "door_sensors": [DOOR],
    "window_sensors": [],
    "persons": [PERSON],
    "open_delay_minutes": 3,
    "absence_delay_minutes": 15,
}


@pytest.fixture
def climate_calls(hass: HomeAssistant) -> list[ServiceCall]:
    """Register fake climate services and record the calls."""
    calls: list[ServiceCall] = []

    async def _record(call: ServiceCall) -> None:
        calls.append(call)
        # Behave like a real thermostat so later decisions see the new state.
        state = hass.states.get(call.data["entity_id"])
        attrs = dict(state.attributes)
        mode = state.state
        if call.service == "set_hvac_mode":
            mode = str(call.data["hvac_mode"])
        else:
            attrs["temperature"] = call.data["temperature"]
        hass.states.async_set(call.data["entity_id"], mode, attrs)

    hass.services.async_register("climate", "set_hvac_mode", _record)
    hass.services.async_register("climate", "set_temperature", _record)
    return calls


def _set_thermostat(hass: HomeAssistant, mode: str = "heat", target: float = 17.0):
    hass.states.async_set(
        THERMOSTAT,
        mode,
        {
            "hvac_modes": ["off", "heat"],
            "temperature": target,
            "current_temperature": 19.0,
        },
    )


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
    hass.states.async_set(SCHEDULE, "on")
    hass.states.async_set(DOOR, "off")
    hass.states.async_set(PERSON, "home")
    _set_thermostat(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        title="Heat Pilot",
        subentries_data=[
            ConfigSubentryData(
                data=ROOM_DATA,
                subentry_type=SUBENTRY_ROOM,
                title="Room",
                unique_id=None,
            )
        ],
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _modes(calls: list[ServiceCall]) -> list[str]:
    return [c.data["hvac_mode"] for c in calls if c.service == "set_hvac_mode"]


def _temps(calls: list[ServiceCall]) -> list[float]:
    return [c.data["temperature"] for c in calls if c.service == "set_temperature"]


async def _advance(hass: HomeAssistant, freezer: FrozenDateTimeFactory, **kw) -> None:
    freezer.tick(timedelta(**kw))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_comfort_applied_on_start(
    hass: HomeAssistant, climate_calls: list[ServiceCall], freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-11-10 12:00:00+00:00")
    await _setup(hass)
    assert _temps(climate_calls)[-1] == 21.0


async def test_open_door_turns_off_after_delay_and_restores(
    hass: HomeAssistant, climate_calls: list[ServiceCall], freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-11-10 12:00:00+00:00")
    await _setup(hass)
    climate_calls.clear()

    hass.states.async_set(DOOR, "on")
    await hass.async_block_till_done()
    await _advance(hass, freezer, minutes=2)
    assert "off" not in _modes(climate_calls)

    await _advance(hass, freezer, minutes=1, seconds=5)
    assert _modes(climate_calls)[-1] == "off"

    hass.states.async_set(DOOR, "off")
    await hass.async_block_till_done()
    assert _modes(climate_calls)[-1] == "heat"


async def test_unavailable_door_counts_as_closed(
    hass: HomeAssistant, climate_calls: list[ServiceCall], freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-11-10 12:00:00+00:00")
    await _setup(hass)
    climate_calls.clear()

    hass.states.async_set(DOOR, "unavailable")
    await hass.async_block_till_done()
    await _advance(hass, freezer, minutes=10)
    assert "off" not in _modes(climate_calls)


async def test_outside_heating_period_forces_off(
    hass: HomeAssistant, climate_calls: list[ServiceCall], freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-07-10 12:00:00+00:00")
    await _setup(hass)
    assert _modes(climate_calls)[-1] == "off"
    climate_calls.clear()

    # A manual switch-on is reverted.
    _set_thermostat(hass, "heat", 22.0)
    await hass.async_block_till_done()
    assert _modes(climate_calls)[-1] == "off"


async def test_person_away_turns_room_off_after_delay(
    hass: HomeAssistant, climate_calls: list[ServiceCall], freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-11-10 12:00:00+00:00")
    await _setup(hass)
    climate_calls.clear()

    hass.states.async_set(PERSON, "not_home")
    await hass.async_block_till_done()
    await _advance(hass, freezer, minutes=10)
    assert "off" not in _modes(climate_calls)
    await _advance(hass, freezer, minutes=5, seconds=5)
    assert _modes(climate_calls)[-1] == "off"

    hass.states.async_set(PERSON, "home")
    await hass.async_block_till_done()
    assert _modes(climate_calls)[-1] == "heat"


async def test_absence_mode_sets_frost_protection(
    hass: HomeAssistant, climate_calls: list[ServiceCall], freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-11-10 12:00:00+00:00")
    entry = await _setup(hass)
    climate_calls.clear()

    await entry.runtime_data.async_set_absence_mode(True)
    await hass.async_block_till_done()
    assert _temps(climate_calls)[-1] == 7.0


async def test_setback_when_schedule_off_and_skip_flag(
    hass: HomeAssistant, climate_calls: list[ServiceCall], freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-11-10 12:00:00+00:00")
    entry = await _setup(hass)
    coordinator = entry.runtime_data
    room_id = next(iter(entry.subentries))
    climate_calls.clear()

    hass.states.async_set(SCHEDULE, "off")
    await hass.async_block_till_done()
    assert _temps(climate_calls)[-1] == 17.0

    await coordinator.async_set_room_value(room_id, "skip_setback", True)
    await coordinator.async_evaluate_room(room_id)
    assert _temps(climate_calls)[-1] == 21.0

    # The one-shot flag is cleared at the next comfort start.
    hass.states.async_set(SCHEDULE, "on")
    await hass.async_block_till_done()
    assert coordinator.room_state(room_id)["skip_setback"] is False


async def test_max_limit_pulls_down_manual_setpoint(
    hass: HomeAssistant, climate_calls: list[ServiceCall], freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-11-10 12:00:00+00:00")
    await _setup(hass)
    climate_calls.clear()

    _set_thermostat(hass, "heat", 28.0)
    await hass.async_block_till_done()
    assert _temps(climate_calls)[-1] == 24.0


async def test_unload_and_reload(
    hass: HomeAssistant, climate_calls: list[ServiceCall], freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-11-10 12:00:00+00:00")
    entry = await _setup(hass)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert dt_util.utcnow().year == 2026


async def test_card_is_registered_and_status_exposes_schedule(
    hass: HomeAssistant, climate_calls: list[ServiceCall], freezer: FrozenDateTimeFactory
) -> None:
    from homeassistant.components.frontend import (
        DATA_EXTRA_JS_URL_ES5,
        DATA_EXTRA_MODULE_URL,
    )

    freezer.move_to("2026-11-10 12:00:00+00:00")
    await _setup(hass)
    modules = hass.data[DATA_EXTRA_MODULE_URL].urls
    es5 = hass.data[DATA_EXTRA_JS_URL_ES5].urls
    assert any("/heat_pilot_static/heat-pilot-card.js?v=" in url for url in modules)
    assert any("/heat_pilot_static/heat-pilot-card.js?v=" in url for url in es5)

    status = hass.states.get("sensor.room_status")
    assert status.attributes["schedule"] == SCHEDULE
    assert status.attributes["thermostats"] == [THERMOSTAT]
