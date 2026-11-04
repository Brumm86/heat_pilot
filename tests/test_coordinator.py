"""Scenario tests for the Heat Pilot coordinator with simulated devices."""

from __future__ import annotations

from datetime import datetime, time, timedelta

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


def _set_thermostat(
    hass: HomeAssistant,
    mode: str = "heat",
    target: float = 17.0,
    max_temp: float | None = None,
):
    attrs = {
        "hvac_modes": ["off", "heat"],
        "temperature": target,
        "current_temperature": 19.0,
    }
    if max_temp is not None:
        attrs["max_temp"] = max_temp
    hass.states.async_set(THERMOSTAT, mode, attrs)


NO_SCHEDULE_DATA = {k: v for k, v in ROOM_DATA.items() if k != "schedule"}


def _local(hhmm: str) -> datetime:
    """A moment on 10 Nov 2026 at ``hhmm`` in Home Assistant's time zone."""
    return datetime.fromisoformat(f"2026-11-10T{hhmm}:00").replace(
        tzinfo=dt_util.get_default_time_zone()
    )


async def _setup(hass: HomeAssistant, room_data: dict | None = None) -> MockConfigEntry:
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
                data=room_data or ROOM_DATA,
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


async def test_manual_switch_on_is_reverted_while_door_shut_the_room_off(
    hass: HomeAssistant, climate_calls: list[ServiceCall], freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-11-10 12:00:00+00:00")
    await _setup(hass)

    hass.states.async_set(DOOR, "on")
    await hass.async_block_till_done()
    await _advance(hass, freezer, minutes=3, seconds=5)
    assert _modes(climate_calls)[-1] == "off"
    climate_calls.clear()

    # Someone switches the radiator on by hand while the door is still open.
    _set_thermostat(hass, "heat", 22.0)
    await hass.async_block_till_done()
    assert _modes(climate_calls) == ["off"]

    # Once the door is closed, heating resumes as usual.
    hass.states.async_set(DOOR, "off")
    await hass.async_block_till_done()
    assert _modes(climate_calls)[-1] == "heat"


async def test_manual_switch_on_is_kept_while_door_open_within_delay(
    hass: HomeAssistant, climate_calls: list[ServiceCall], freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-11-10 12:00:00+00:00")
    await _setup(hass)
    climate_calls.clear()

    hass.states.async_set(DOOR, "on")
    await hass.async_block_till_done()
    await _advance(hass, freezer, minutes=1)
    _set_thermostat(hass, "heat", 22.0)
    await hass.async_block_till_done()
    assert "off" not in _modes(climate_calls)


async def test_door_events_within_delay_leave_the_setpoint_alone(
    hass: HomeAssistant, climate_calls: list[ServiceCall], freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-11-10 12:00:00+00:00")
    await _setup(hass)
    _set_thermostat(hass, "heat", 23.0)  # manual setting, plan says 21
    await hass.async_block_till_done()
    climate_calls.clear()

    hass.states.async_set(DOOR, "on")
    await hass.async_block_till_done()
    await _advance(hass, freezer, minutes=1)
    hass.states.async_set(DOOR, "off")
    await hass.async_block_till_done()
    hass.states.async_set(DOOR, "on")
    await hass.async_block_till_done()
    hass.states.async_set(DOOR, "off")
    await hass.async_block_till_done()
    assert climate_calls == []
    assert hass.states.get(THERMOSTAT).attributes["temperature"] == 23.0


async def test_setpoint_is_kept_when_the_room_is_released_after_a_door_shutdown(
    hass: HomeAssistant, climate_calls: list[ServiceCall], freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-11-10 12:00:00+00:00")
    entry = await _setup(hass)
    room_id = next(iter(entry.subentries))

    hass.states.async_set(DOOR, "on")
    await hass.async_block_till_done()
    await _advance(hass, freezer, minutes=3, seconds=5)
    assert _modes(climate_calls)[-1] == "off"
    assert entry.runtime_data.room_state(room_id)["opening_plan"] == ["heat", 21.0]

    # The setpoint is changed by hand while the thermostat is off.
    _set_thermostat(hass, "off", 23.0)
    await hass.async_block_till_done()
    climate_calls.clear()

    hass.states.async_set(DOOR, "off")
    await hass.async_block_till_done()
    assert _modes(climate_calls) == ["heat"]
    assert _temps(climate_calls) == []
    assert hass.states.get(THERMOSTAT).attributes["temperature"] == 23.0
    assert entry.runtime_data.room_state(room_id)["opening_plan"] is None


async def test_plan_target_is_set_on_release_when_the_plan_changed_meanwhile(
    hass: HomeAssistant, climate_calls: list[ServiceCall], freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-11-10 12:00:00+00:00")
    await _setup(hass)

    hass.states.async_set(DOOR, "on")
    await hass.async_block_till_done()
    await _advance(hass, freezer, minutes=3, seconds=5)
    assert _modes(climate_calls)[-1] == "off"

    # The comfort phase ends while the door is still open (room stays off).
    hass.states.async_set(SCHEDULE, "off")
    await hass.async_block_till_done()
    assert _modes(climate_calls)[-1] == "off"
    climate_calls.clear()

    hass.states.async_set(DOOR, "off")
    await hass.async_block_till_done()
    assert _modes(climate_calls) == ["heat"]
    assert _temps(climate_calls)[-1] == 17.0


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


async def test_boost_turns_up_fully_and_ends_by_itself(
    hass: HomeAssistant, climate_calls: list[ServiceCall], freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-11-10 12:00:00+00:00")
    entry = await _setup(hass)
    coordinator = entry.runtime_data
    room_id = next(iter(entry.subentries))
    climate_calls.clear()

    await coordinator.async_start_boost(room_id)
    await hass.async_block_till_done()
    # Full blast, and the maximum-temperature limit (24) does not pull it back.
    assert _temps(climate_calls)[-1] == 30.0
    assert coordinator.boost_active(room_id)
    assert hass.states.get("sensor.room_status").state == "boost"

    await _advance(hass, freezer, minutes=29)
    assert coordinator.boost_active(room_id)
    assert _temps(climate_calls)[-1] == 30.0

    await _advance(hass, freezer, minutes=1, seconds=5)
    assert not coordinator.boost_active(room_id)
    assert coordinator.room_state(room_id)["boost_until"] is None
    assert _temps(climate_calls)[-1] == 21.0


async def test_boost_is_capped_at_the_thermostats_own_maximum(
    hass: HomeAssistant, climate_calls: list[ServiceCall], freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-11-10 12:00:00+00:00")
    entry = await _setup(hass)
    room_id = next(iter(entry.subentries))
    _set_thermostat(hass, "heat", 21.0, max_temp=25.0)
    await hass.async_block_till_done()
    climate_calls.clear()

    await entry.runtime_data.async_start_boost(room_id)
    await hass.async_block_till_done()
    assert _temps(climate_calls)[-1] == 25.0


async def test_boost_can_be_stopped_early(
    hass: HomeAssistant, climate_calls: list[ServiceCall], freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-11-10 12:00:00+00:00")
    entry = await _setup(hass)
    coordinator = entry.runtime_data
    room_id = next(iter(entry.subentries))

    await coordinator.async_start_boost(room_id)
    await hass.async_block_till_done()
    await coordinator.async_stop_boost(room_id)
    await hass.async_block_till_done()
    assert not coordinator.boost_active(room_id)
    assert _temps(climate_calls)[-1] == 21.0


async def test_open_door_still_shuts_a_boosted_room_off(
    hass: HomeAssistant, climate_calls: list[ServiceCall], freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-11-10 12:00:00+00:00")
    entry = await _setup(hass)
    room_id = next(iter(entry.subentries))
    await entry.runtime_data.async_start_boost(room_id)
    await hass.async_block_till_done()

    hass.states.async_set(DOOR, "on")
    await hass.async_block_till_done()
    await _advance(hass, freezer, minutes=3, seconds=5)
    assert _modes(climate_calls)[-1] == "off"

    # The boost goes on once the door is closed again.
    hass.states.async_set(DOOR, "off")
    await hass.async_block_till_done()
    assert _modes(climate_calls)[-1] == "heat"
    assert _temps(climate_calls)[-1] == 30.0


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


async def test_night_setback_lowers_a_manually_heated_room_at_the_set_time(
    hass: HomeAssistant, climate_calls: list[ServiceCall], freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(_local("21:00"))
    entry = await _setup(hass, NO_SCHEDULE_DATA)
    coordinator = entry.runtime_data
    room_id = next(iter(entry.subentries))
    assert hass.states.get("switch.room_night_setback").state == "off"
    await coordinator.async_set_night_setback(room_id, enabled=True)

    _set_thermostat(hass, "heat", 23.0)  # heated by hand in the evening
    await hass.async_block_till_done()
    climate_calls.clear()

    await _advance(hass, freezer, minutes=30)
    assert climate_calls == []  # switching the option on does not lower the room
    await _advance(hass, freezer, minutes=31)
    assert _temps(climate_calls) == [17.0]
    assert hass.states.get(THERMOSTAT).attributes["temperature"] == 17.0


async def test_night_setback_does_nothing_while_the_option_is_off(
    hass: HomeAssistant, climate_calls: list[ServiceCall], freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(_local("21:00"))
    await _setup(hass, NO_SCHEDULE_DATA)
    _set_thermostat(hass, "heat", 23.0)
    await hass.async_block_till_done()
    climate_calls.clear()

    await _advance(hass, freezer, hours=2)
    assert climate_calls == []


async def test_night_setback_never_switches_a_thermostat_on(
    hass: HomeAssistant, climate_calls: list[ServiceCall], freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(_local("21:00"))
    entry = await _setup(hass, NO_SCHEDULE_DATA)
    room_id = next(iter(entry.subentries))
    await entry.runtime_data.async_set_night_setback(room_id, enabled=True)
    _set_thermostat(hass, "off", 23.0)
    await hass.async_block_till_done()
    climate_calls.clear()

    await _advance(hass, freezer, hours=2)
    assert climate_calls == []


async def test_night_setback_time_can_be_changed_and_ends_skip_setback(
    hass: HomeAssistant, climate_calls: list[ServiceCall], freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(_local("21:00"))
    entry = await _setup(hass, NO_SCHEDULE_DATA)
    coordinator = entry.runtime_data
    room_id = next(iter(entry.subentries))
    await coordinator.async_set_night_setback(room_id, enabled=True)
    await hass.services.async_call(
        "time",
        "set_value",
        {"entity_id": "time.room_night_setback_time", "time": "23:30:00"},
        blocking=True,
    )
    assert coordinator.night_setback_time(room_id) == time(23, 30)
    assert coordinator.room_state(room_id)["night_setback_time"] == "23:30"

    await coordinator.async_set_room_value(room_id, "skip_setback", True)
    assert _temps(climate_calls)[-1] == 21.0  # no schedule: skipping means comfort
    climate_calls.clear()

    await _advance(hass, freezer, hours=1, minutes=5)  # 22:05, old time passed
    assert climate_calls == []
    await _advance(hass, freezer, hours=1, minutes=30)  # 23:35
    assert _temps(climate_calls) == [17.0]
    assert coordinator.room_state(room_id)["skip_setback"] is False


async def test_night_setback_is_only_offered_to_rooms_without_schedule(
    hass: HomeAssistant, climate_calls: list[ServiceCall], freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to(_local("21:00"))
    await _setup(hass)  # the room has a schedule
    assert hass.states.get("switch.room_night_setback") is None
    assert hass.states.get("time.room_night_setback_time") is None


def _switch_id(hass: HomeAssistant, key: str) -> str:
    from homeassistant.helpers import entity_registry as er

    registry = er.async_get(hass)
    for entry in registry.entities.values():
        if entry.platform == DOMAIN and entry.translation_key == key:
            return entry.entity_id
    raise AssertionError(key)


async def test_paused_heating_period_forces_off_and_ignores_manual_changes(
    hass: HomeAssistant, climate_calls: list[ServiceCall], freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-11-10 12:00:00+00:00")
    await _setup(hass)
    assert _temps(climate_calls)[-1] == 21.0
    climate_calls.clear()

    pause = _switch_id(hass, "period_paused")
    await hass.services.async_call("switch", "turn_on", {"entity_id": pause}, blocking=True)
    await hass.async_block_till_done()
    assert _modes(climate_calls)[-1] == "off"
    assert hass.states.get(_switch_id(hass, "status")).state == "outside_period"
    climate_calls.clear()

    # A manual switch-on is reverted again.
    _set_thermostat(hass, "heat", 22.0)
    await hass.async_block_till_done()
    assert _modes(climate_calls)[-1] == "off"

    # The pause beats "force heating period".
    override = _switch_id(hass, "period_override")
    await hass.services.async_call("switch", "turn_on", {"entity_id": override}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get(_switch_id(hass, "heating_period")).state == "inactive"

    # Switching the pause off restores comfort.
    climate_calls.clear()
    await hass.services.async_call("switch", "turn_off", {"entity_id": pause}, blocking=True)
    await hass.async_block_till_done()
    assert _temps(climate_calls)[-1] == 21.0


async def test_boost_does_not_heat_outside_the_heating_period_and_ends(
    hass: HomeAssistant, climate_calls: list[ServiceCall], freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-11-10 12:00:00+00:00")
    await _setup(hass)
    boost = _switch_id(hass, "boost")
    await hass.services.async_call("switch", "turn_on", {"entity_id": boost}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get(boost).state == "on"

    pause = _switch_id(hass, "period_paused")
    await hass.services.async_call("switch", "turn_on", {"entity_id": pause}, blocking=True)
    await hass.async_block_till_done()
    assert _modes(climate_calls)[-1] == "off"
    assert hass.states.get(boost).state == "off"  # the boost ended with the period

    # A new boost does not turn the heating on while the period is paused.
    climate_calls.clear()
    await hass.services.async_call("switch", "turn_on", {"entity_id": boost}, blocking=True)
    await hass.async_block_till_done()
    assert "heat" not in _modes(climate_calls)
    assert hass.states.get(boost).state == "off"


async def test_plan_pause_holds_setback_until_midnight(
    hass: HomeAssistant, climate_calls: list[ServiceCall], freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-11-10 12:00:00+00:00")
    await _setup(hass)
    assert _temps(climate_calls)[-1] == 21.0
    climate_calls.clear()

    pause = _switch_id(hass, "plan_paused")
    await hass.services.async_call("switch", "turn_on", {"entity_id": pause}, blocking=True)
    await hass.async_block_till_done()
    assert _temps(climate_calls)[-1] == 17.0
    assert hass.states.get(_switch_id(hass, "status")).state == "plan_paused"

    # Schedule events are ignored: the room stays at setback.
    climate_calls.clear()
    hass.states.async_set(SCHEDULE, "off")
    await hass.async_block_till_done()
    hass.states.async_set(SCHEDULE, "on")
    await hass.async_block_till_done()
    assert 21.0 not in _temps(climate_calls)

    # At the next local midnight the schedule is back in charge.
    midnight = dt_util.start_of_local_day(dt_util.now() + timedelta(days=1))
    freezer.move_to(midnight + timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(pause).state == "off"
    assert _temps(climate_calls)[-1] == 21.0


async def test_plan_pause_only_for_rooms_with_a_schedule(
    hass: HomeAssistant, climate_calls: list[ServiceCall]
) -> None:
    await _setup(hass, NO_SCHEDULE_DATA)
    from homeassistant.helpers import entity_registry as er

    assert not [
        e
        for e in er.async_get(hass).entities.values()
        if e.platform == DOMAIN and e.translation_key == "plan_paused"
    ]
