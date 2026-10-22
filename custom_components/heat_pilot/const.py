"""Constants for the Heat Pilot integration."""

from __future__ import annotations

DOMAIN = "heat_pilot"

STORAGE_KEY = f"{DOMAIN}.state"
STORAGE_VERSION = 1

# Config subentry type: one subentry per room.
SUBENTRY_ROOM = "room"

# Room subentry data keys.
CONF_THERMOSTATS = "thermostats"
CONF_SCHEDULE = "schedule"
CONF_DOOR_SENSORS = "door_sensors"
CONF_WINDOW_SENSORS = "window_sensors"
CONF_PERSONS = "persons"
CONF_OPEN_DELAY = "open_delay_minutes"
CONF_ABSENCE_DELAY = "absence_delay_minutes"

DEFAULT_OPEN_DELAY = 3  # minutes a door/window may be open before shutdown
DEFAULT_ABSENCE_DELAY = 15  # minutes all persons must be away before shutdown

# Runtime defaults (stored in the Store, editable via entities).
DEFAULT_COMFORT_TEMP = 21.0
DEFAULT_SETBACK_TEMP = 17.0
DEFAULT_FROST_TEMP = 7.0
DEFAULT_MAX_TEMP = 24.0
DEFAULT_PERIOD_START = (10, 1)  # 1 October
DEFAULT_PERIOD_END = (4, 30)  # 30 April

MIN_TEMP = 5.0
MAX_TEMP = 30.0

# Per-room feature toggles (switch entities). Keys double as translation keys.
FEATURE_DOOR_WARNING = "door_warning"
FEATURE_OPENING_SHUTDOWN = "opening_shutdown"
FEATURE_ABSENCE_SHUTDOWN = "absence_shutdown"
FEATURE_MAX_LIMIT = "max_limit"
ROOM_FEATURES = (
    FEATURE_DOOR_WARNING,
    FEATURE_OPENING_SHUTDOWN,
    FEATURE_ABSENCE_SHUTDOWN,
    FEATURE_MAX_LIMIT,
)

SERVICE_SET_HEATING_PERIOD = "set_heating_period"
ATTR_START_MONTH = "start_month"
ATTR_START_DAY = "start_day"
ATTR_END_MONTH = "end_month"
ATTR_END_DAY = "end_day"
