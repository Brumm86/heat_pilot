"""Tests for the config flow and the room subentry flow."""

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.heat_pilot.const import DOMAIN, SUBENTRY_ROOM

ROOM_INPUT = {
    "name": "Living",
    "thermostats": ["climate.living"],
    "schedule": "schedule.living",
    "door_sensors": ["binary_sensor.living_door"],
    "window_sensors": [],
    "persons": [],
    "open_delay_minutes": 3,
    "absence_delay_minutes": 15,
}


async def test_user_flow_creates_entry(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Heat Pilot"


async def test_single_instance(hass: HomeAssistant) -> None:
    MockConfigEntry(domain=DOMAIN, data={}).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def _setup_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data={}, title="Heat Pilot")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_add_room_subentry(hass: HomeAssistant) -> None:
    entry = await _setup_entry(hass)
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_ROOM), context={"source": "user"}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], ROOM_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Living"
    subentry = next(iter(entry.subentries.values()))
    assert subentry.data["thermostats"] == ["climate.living"]
    assert "name" not in subentry.data


async def test_room_requires_thermostat(hass: HomeAssistant) -> None:
    entry = await _setup_entry(hass)
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_ROOM), context={"source": "user"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {**ROOM_INPUT, "thermostats": []}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"thermostats": "no_thermostat"}


async def test_room_name_must_be_unique(hass: HomeAssistant) -> None:
    entry = await _setup_entry(hass)
    for expected in (FlowResultType.CREATE_ENTRY, FlowResultType.FORM):
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, SUBENTRY_ROOM), context={"source": "user"}
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], ROOM_INPUT
        )
        assert result["type"] is expected
    assert result["errors"] == {"name": "name_exists"}
