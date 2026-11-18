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
OPEN_STATES = STATES[:2]
ENDED_STATES = STATES[2:]
SOURCES = ("email", "agent", "proposal", "owner")
CORE_CLIENTS = ("email", "agent")
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


@functools.cache
def zone_names() -> frozenset[str]:
    return frozenset(zoneinfo.available_timezones())
