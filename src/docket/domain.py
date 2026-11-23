"""Shared domain lists, bounds and the exact time-zone name set."""

import functools
import zoneinfo
from types import MappingProxyType

STATE_LABELS: MappingProxyType[str, str] = MappingProxyType(
    {
        "open": "open",
        "in_progress": "in progress",
        "done": "done",
        "cancelled": "cancelled",
    }
)
STATES = tuple(STATE_LABELS)
OPEN_STATES = ("open", "in_progress")
ENDED_STATES = ("done", "cancelled")
SOURCES = ("email", "agent", "proposal", "owner")
EMAIL_CLIENT = "email"
API_CLIENTS = (EMAIL_CLIENT,)
CORE_CLIENTS = (EMAIL_CLIENT, "agent")
ACTORS = ("owner", "agent", "email")
STATE_ACTIONS = ("start", "done", "cancel", "reopen")
AUDIT_ACTIONS = (
    "create",
    "start",
    "done",
    "cancel",
    "reopen",
    "retitle",
    "deadline",
    "work_time",
)
PROVIDERS = ("gmail", "outlook", "yahoo")
SOURCE_ACTORS: MappingProxyType[str, str] = MappingProxyType(
    {"email": "email", "agent": "agent", "proposal": "owner", "owner": "owner"}
)
FORBIDDEN_TEXT_CATEGORIES = frozenset({"Cc", "Cf", "Zl", "Zp"})
TITLE_MAX = 100
REQUEST_KEY_MAX = 200
WORK_MINUTES_MIN = 5
WORK_MINUTES_MAX = 720


def valid_request_key(key: object) -> bool:
    return isinstance(key, str) and 1 <= len(key) <= REQUEST_KEY_MAX


@functools.cache
def zone_names() -> frozenset[str]:
    return frozenset(zoneinfo.available_timezones())


WORK_KINDS = ("start",)
DEADLINE_KINDS = ("before", "due_soon", "due", "late")
REMINDER_KINDS = WORK_KINDS + DEADLINE_KINDS
DUE_WINDOW_MINUTES = 30
LOOP_STALE_MINUTES = 5
