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
CONF_EXTERNAL_HEATING = "external_heating"  # legacy (< 0.14), see heating_type_of
# How a room is heated: by its thermostats, by something Home Assistant does not
# control (e.g. underfloor heating), or both.
CONF_HEATING_TYPE = "heating_type"
HEATING_THERMOSTAT = "thermostat"
HEATING_EXTERNAL = "external"
HEATING_COMBINED = "combined"
HEATING_TYPES = (HEATING_THERMOSTAT, HEATING_EXTERNAL, HEATING_COMBINED)
# Persons whose phones get this room's door/ventilation messages (empty = all).
CONF_NOTIFY_PERSONS = "notify_persons"

DEFAULT_OPEN_DELAY = 3  # minutes a door/window may be open before shutdown
DEFAULT_ABSENCE_DELAY = 15  # minutes all persons must be away before shutdown

# Runtime defaults (stored in the Store, editable via entities).
DEFAULT_COMFORT_TEMP = 21.0
DEFAULT_SETBACK_TEMP = 17.0
DEFAULT_FROST_TEMP = 7.0
DEFAULT_MAX_TEMP = 24.0
# Forced night setback: two global night windows (stored as "HH:MM"). A night
# belongs to the day on which it begins; Friday and Saturday nights use the
# "weekend" times, all others the "weekday" times.
NIGHT_TIME_KEYS = ("weekday_start", "weekday_end", "weekend_start", "weekend_end")
DEFAULT_NIGHT_TIMES = {
    "weekday_start": "20:30",
    "weekday_end": "05:00",
    "weekend_start": "21:30",
    "weekend_end": "05:00",
}
MAX_NIGHT_SHIFT_HOURS = 12
DEFAULT_PERIOD_START = (10, 1)  # 1 October
DEFAULT_PERIOD_END = (4, 30)  # 30 April

MIN_TEMP = 5.0
MAX_TEMP = 30.0

# Boost: a room is heated "full blast" for a while. The target is the highest
# setpoint Heat Pilot knows; each thermostat is capped at its own maximum.
BOOST_TEMP = MAX_TEMP
DEFAULT_BOOST_MINUTES = 30
MIN_BOOST_MINUTES = 5
MAX_BOOST_MINUTES = 240
BOOST_STEP_MINUTES = 5

# Per-room feature toggles (switch entities). Keys double as translation keys.
FEATURE_DOOR_WARNING = "door_warning"
FEATURE_OPENING_SHUTDOWN = "opening_shutdown"
FEATURE_ABSENCE_SHUTDOWN = "absence_shutdown"
FEATURE_MAX_LIMIT = "max_limit"
# Door warning only while the room is in its setback phase (e.g. a kitchen next
# to a room that is heated all day: an open door only matters when it is cold).
FEATURE_DOOR_WARNING_SETBACK_ONLY = "door_warning_setback_only"
# Door warning only while the room is being heated to comfort temperature
# (schedule in comfort phase, or setback skipped).
FEATURE_DOOR_WARNING_HEATING_ONLY = "door_warning_heating_only"
ROOM_FEATURES = (
    FEATURE_DOOR_WARNING,
    FEATURE_DOOR_WARNING_SETBACK_ONLY,
    FEATURE_DOOR_WARNING_HEATING_ONLY,
    FEATURE_OPENING_SHUTDOWN,
    FEATURE_ABSENCE_SHUTDOWN,
    FEATURE_MAX_LIMIT,
)

# Rooms heated only outside Home Assistant have no thermostat: only these apply.
ROOM_FEATURES_EXTERNAL = (FEATURE_DOOR_WARNING,)

# Features that are off until the user switches them on.
FEATURES_DEFAULT_OFF = (
    FEATURE_DOOR_WARNING_SETBACK_ONLY,
    FEATURE_DOOR_WARNING_HEATING_ONLY,
)

SERVICE_SET_HEATING_PERIOD = "set_heating_period"
SERVICE_PAIR_DOOR_SENSOR = "pair_door_sensor"
ATTR_START_MONTH = "start_month"
ATTR_START_DAY = "start_day"
ATTR_END_MONTH = "end_month"
ATTR_END_DAY = "end_day"

# Notification options (stored in the main entry's options).
CONF_ADMIN_NOTIFY = "admin_notify"
CONF_PERSON_NOTIFY = "person_notify"
CONF_VENTILATION_DELAY = "ventilation_delay"
CONF_UNAVAILABLE_DELAY = "unavailable_delay"
CONF_OVERHEAT_TEMP = "overheat_temp"
CONF_OVERHEAT_MINUTES = "overheat_hold_minutes"
CONF_DASHBOARD_PATH = "dashboard_path"

DEFAULT_VENTILATION_DELAY = 15  # minutes a window may stay open before the reminder
DEFAULT_UNAVAILABLE_DELAY = 30  # minutes a device may be unreachable before an alert
DEFAULT_OVERHEAT_TEMP = 25.0  # a thermostat measuring this much is suspect (stuck valve)
DEFAULT_OVERHEAT_MINUTES = 15  # ... if it does so for at least this long
DEFAULT_DASHBOARD_PATH = "/"

# Door warning: first after 5 minutes open, then every 3 minutes, max 3.
# (Independent of the room's shutdown delay.)
DOOR_WARNING_DELAY_MINUTES = 5
DOOR_WARNING_REPEAT_MINUTES = 3
DOOR_WARNING_MAX = 3
# Admin alerts repeat every 6 hours, but only between 08:00 and 22:00.
ADMIN_REPEAT_HOURS = 6
ADMIN_WINDOW = (8, 22)

# How long the ZHA network stays open for (re-)pairing a door sensor.
PAIRING_DURATION_SECONDS = 120

# Dispatcher signal (formatted with the entry id): the list of active alerts changed.
SIGNAL_ALERTS_UPDATED = f"{DOMAIN}_alerts_updated_" + "{}"

# Lovelace card, served from the integration's www folder.
CARD_FILENAME = "heat-pilot-card.js"
CARD_URL_PATH = f"/{DOMAIN}_static/{CARD_FILENAME}"


def heating_type_of(data: dict) -> str:
    """Heating type of a room's subentry data (migrates the pre-0.14 checkbox)."""
    value = data.get(CONF_HEATING_TYPE)
    if value in HEATING_TYPES:
        return value
    if not data.get(CONF_THERMOSTATS):
        return HEATING_EXTERNAL
    return HEATING_COMBINED if data.get(CONF_EXTERNAL_HEATING) else HEATING_THERMOSTAT
