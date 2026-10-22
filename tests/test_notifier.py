"""Scenario tests for notifications with fake notify services."""

from __future__ import annotations

from datetime import timedelta

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.core import HomeAssistant, ServiceCall
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.heat_pilot.const import DOMAIN, SUBENTRY_ROOM

THERMOSTAT = "climate.room"
DOOR = "binary_sensor.room_door"
WINDOW = "binary_sensor.room_window"
PERSON_A = "person.alice"
PERSON_B = "person.bob"

ROOM_DATA = {
    "thermostats": [THERMOSTAT],
    "schedule": "schedule.room",
    "door_sensors": [DOOR],
    "window_sensors": [WINDOW],
    "persons": [],
    "open_delay_minutes": 3,
    "absence_delay_minutes": 15,
}
OPTIONS = {
    "admin_notify": "mobile_app_admin",
    "person_notify": {PERSON_A: "mobile_app_alice", PERSON_B: "mobile_app_bob"},
    "ventilation_delay": 15,
    "unavailable_delay": 30,
    "overheat_delta": 3.0,
    "overheat_minutes": 45,
    "dashboard_path": "/dashboard-heat",
}


@pytest.fixture
def sent(hass: HomeAssistant) -> list[tuple[str, ServiceCall]]:
    calls: list[tuple[str, ServiceCall]] = []

    def _register(name: str) -> None:
        async def _record(call: ServiceCall) -> None:
            calls.append((name, call))

        hass.services.async_register("notify", name, _record)

    for name in ("mobile_app_admin", "mobile_app_alice", "mobile_app_bob"):
        _register(name)

    async def _climate(call: ServiceCall) -> None:
        state = hass.states.get(call.data["entity_id"])
        attrs = dict(state.attributes)
        mode = state.state
        if call.service == "set_hvac_mode":
            mode = str(call.data["hvac_mode"])
        else:
            attrs["temperature"] = call.data["temperature"]
        hass.states.async_set(call.data["entity_id"], mode, attrs)

    hass.services.async_register("climate", "set_hvac_mode", _climate)
    hass.services.async_register("climate", "set_temperature", _climate)
    return calls


def _thermostat(hass: HomeAssistant, current: float = 19.0, target: float = 21.0) -> None:
    hass.states.async_set(
        THERMOSTAT,
        "heat",
        {"hvac_modes": ["off", "heat"], "temperature": target, "current_temperature": current},
    )


async def _setup(
    hass: HomeAssistant, room_data: dict | None = None, *, wants_heat: bool = True
) -> None:
    await hass.config.async_set_time_zone("UTC")
    hass.states.async_set("schedule.room", "on")
    hass.states.async_set(DOOR, "off")
    hass.states.async_set(WINDOW, "off")
    hass.states.async_set(PERSON_A, "home")
    hass.states.async_set(PERSON_B, "not_home")
    _thermostat(hass) if wants_heat else _thermostat(hass, current=22.0, target=21.0)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options=OPTIONS,
        subentries_data=[
            ConfigSubentryData(
                data=room_data or ROOM_DATA, subentry_type=SUBENTRY_ROOM, title="Room", unique_id=None
            )
        ],
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def _advance(hass: HomeAssistant, freezer: FrozenDateTimeFactory, **kw) -> None:
    """Advance time in 15 s steps so the notifier tick sees every moment."""
    total = timedelta(**kw)
    step = timedelta(seconds=15)
    elapsed = timedelta()
    while elapsed < total:
        freezer.tick(step)
        elapsed += step
        async_fire_time_changed(hass)
        await hass.async_block_till_done()


def _messages(sent: list[tuple[str, ServiceCall]], service: str) -> list[ServiceCall]:
    return [c for n, c in sent if n == service and c.data["message"] != "clear_notification"]


async def test_door_warnings_go_to_persons_at_home_max_three_then_clear(
    hass: HomeAssistant, sent, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-11-10 12:00:00+00:00")
    await _setup(hass)

    hass.states.async_set(DOOR, "on")
    await hass.async_block_till_done()
    await _advance(hass, freezer, minutes=2)
    assert not _messages(sent, "mobile_app_alice")

    await _advance(hass, freezer, minutes=30)
    alice = _messages(sent, "mobile_app_alice")
    assert len(alice) == 3
    assert not _messages(sent, "mobile_app_bob")  # not at home
    assert not _messages(sent, "mobile_app_admin")
    data = alice[0].data["data"]
    assert data["tag"].startswith("heat_pilot_door_")
    assert data["persistent"] and data["sticky"] and data["chronometer"]
    assert data["clickAction"] == "/dashboard-heat"

    sent.clear()
    hass.states.async_set(DOOR, "off")
    await _advance(hass, freezer, seconds=30)
    cleared = [c for _, c in sent if c.data["message"] == "clear_notification"]
    assert {c.data["data"]["tag"] for c in cleared} == {data["tag"]}


async def test_no_door_warning_when_room_not_heated_by_thermostat(
    hass: HomeAssistant, sent, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-11-10 12:00:00+00:00")
    await _setup(hass, wants_heat=False)
    hass.states.async_set(DOOR, "on")
    await hass.async_block_till_done()
    await _advance(hass, freezer, minutes=30)
    assert not _messages(sent, "mobile_app_alice")


async def test_door_warning_for_externally_heated_room(
    hass: HomeAssistant, sent, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-11-10 12:00:00+00:00")
    await _setup(hass, {**ROOM_DATA, "external_heating": True}, wants_heat=False)
    hass.states.async_set(DOOR, "on")
    await hass.async_block_till_done()
    await _advance(hass, freezer, minutes=30)
    assert len(_messages(sent, "mobile_app_alice")) == 3


async def test_door_warning_for_room_without_thermostat(
    hass: HomeAssistant, sent, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-11-10 12:00:00+00:00")
    room = {k: v for k, v in ROOM_DATA.items() if k != "schedule"}
    await _setup(hass, {**room, "thermostats": []})
    hass.states.async_set(DOOR, "on")
    await hass.async_block_till_done()
    await _advance(hass, freezer, minutes=30)
    assert len(_messages(sent, "mobile_app_alice")) == 3


async def test_no_door_warning_outside_heating_period(
    hass: HomeAssistant, sent, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-07-10 12:00:00+00:00")
    await _setup(hass)
    hass.states.async_set(DOOR, "on")
    await _advance(hass, freezer, minutes=10)
    assert not _messages(sent, "mobile_app_alice")


async def test_ventilation_reminder_once_after_window_shutdown(
    hass: HomeAssistant, sent, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-11-10 12:00:00+00:00")
    await _setup(hass)
    hass.states.async_set(WINDOW, "on")
    await _advance(hass, freezer, minutes=14)
    assert not _messages(sent, "mobile_app_alice")
    await _advance(hass, freezer, minutes=60)
    reminders = _messages(sent, "mobile_app_alice")
    assert len(reminders) == 1
    assert "vent" in reminders[0].data["data"]["tag"]


async def test_admin_alert_for_unavailable_sensor_after_30_minutes(
    hass: HomeAssistant, sent, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-11-10 12:00:00+00:00")
    await _setup(hass)
    hass.states.async_set(DOOR, "unavailable")
    await _advance(hass, freezer, minutes=29)
    assert not _messages(sent, "mobile_app_admin")
    await _advance(hass, freezer, minutes=2)
    assert len(_messages(sent, "mobile_app_admin")) == 1
    assert not _messages(sent, "mobile_app_alice")


async def test_admin_alert_postponed_to_morning(
    hass: HomeAssistant, sent, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-11-10 21:50:00+00:00")
    await _setup(hass)
    hass.states.async_set(DOOR, "unavailable")
    await _advance(hass, freezer, hours=9)  # 06:50, still night
    assert not _messages(sent, "mobile_app_admin")
    await _advance(hass, freezer, hours=1, minutes=30)  # 08:20
    assert len(_messages(sent, "mobile_app_admin")) == 1


async def test_overheating_alert(
    hass: HomeAssistant, sent, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-11-10 12:00:00+00:00")
    await _setup(hass)
    _thermostat(hass, current=25.0, target=21.0)
    await _advance(hass, freezer, minutes=44)
    assert not _messages(sent, "mobile_app_admin")
    await _advance(hass, freezer, minutes=2)
    assert len(_messages(sent, "mobile_app_admin")) == 1
