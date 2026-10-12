"""Stałe integracji eduVULCAN."""

DOMAIN = "vulcan_dom"
EVENT = "vulcan_dom_event"

CONF_AP_JSON = "ap_json"
CONF_CREDENTIAL = "credential"
CONF_TENANT = "tenant"

CONF_SCAN_INTERVAL = "scan_interval"
CONF_QUIET_START = "quiet_start"
CONF_QUIET_END = "quiet_end"
CONF_WRITE_LIMIT = "write_limit"

DEFAULT_SCAN_INTERVAL = 30  # minuty
DEFAULT_QUIET_START = 22  # godzina — bez odpytywania od
DEFAULT_QUIET_END = 6  # do
DEFAULT_WRITE_LIMIT = 10  # wysłanych wiadomości/usprawiedliwień na dobę

# okna pobierania (dni wstecz, dni naprzód)
WINDOW_SCHEDULE = (1, 14)
WINDOW_EXAMS = (7, 60)
WINDOW_HOMEWORK = (7, 30)

EVENT_TEXT_LIMIT = 500
PLATFORMS = ["sensor", "calendar"]
