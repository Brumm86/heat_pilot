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

# Notification options (stored in the main entry's options).
CONF_ADMIN_NOTIFY = "admin_notify"
CONF_PERSON_NOTIFY = "person_notify"
CONF_VENTILATION_DELAY = "ventilation_delay"
CONF_UNAVAILABLE_DELAY = "unavailable_delay"
CONF_OVERHEAT_DELTA = "overheat_delta"
CONF_OVERHEAT_MINUTES = "overheat_minutes"
CONF_DASHBOARD_PATH = "dashboard_path"

DEFAULT_VENTILATION_DELAY = 15  # minutes a window may stay open before the reminder
DEFAULT_UNAVAILABLE_DELAY = 30  # minutes a device may be unreachable before an alert
DEFAULT_OVERHEAT_DELTA = 3.0  # kelvin above the setpoint
DEFAULT_OVERHEAT_MINUTES = 45
DEFAULT_DASHBOARD_PATH = "/"

# Door warning: first after the room's open delay, then every 3 minutes, max 3.
DOOR_WARNING_REPEAT_MINUTES = 3
DOOR_WARNING_MAX = 3
# Admin alerts repeat every 6 hours, but only between 08:00 and 22:00.
ADMIN_REPEAT_HOURS = 6
ADMIN_WINDOW = (8, 22)

# Lovelace card, served from the integration's www folder.
CARD_FILENAME = "heat-pilot-card.js"
CARD_URL_PATH = f"/{DOMAIN}_static/{CARD_FILENAME}"
