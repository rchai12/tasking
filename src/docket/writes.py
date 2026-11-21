"""Write tools for the MCP server: each call becomes one keyed core call."""

from docket import core, deadlines, parsing
from docket.core import CoreError, Outcome
from docket.deadlines import Deadline
from docket.store import Store

INVALID_DEADLINE = "invalid_deadline"
UNKNOWN_TASK = "unknown_task"
_DEADLINE_KEYS = {"date", "time", "time_zone"}


class WriteRefused(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def parse_deadline(value: object) -> Deadline | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != _DEADLINE_KEYS:
        raise WriteRefused(INVALID_DEADLINE)
    try:
        day = parsing.parse_date(value["date"])
        at = None if value["time"] is None else parsing.parse_time(value["time"])
        return deadlines.make_deadline(day, at, value["time_zone"])
    except (parsing.ParseError, deadlines.DeadlineError):
        raise WriteRefused(INVALID_DEADLINE) from None


def create_task(store: Store, *, title: object, deadline: object, request_key: object) -> Outcome:
    parsed = parse_deadline(deadline)
    try:
        return core.create_task_once(
            store,
            client="agent",
            key=request_key,
            request={"tool": "create_task", "title": title, "deadline": deadline},
            title=title,
            source="agent",
            deadline=parsed,
        )
    except CoreError as error:
        raise WriteRefused(error.code) from None


def _change(store: Store, tool: str, action: str, task_id: object, request_key: object) -> Outcome:
    if not isinstance(task_id, str):
        raise WriteRefused(UNKNOWN_TASK)
    try:
        return core.change_state_once(
            store,
            task_id,
            action,
            client="agent",
            key=request_key,
            request={"tool": tool, "id": task_id},
        )
    except CoreError as error:
        raise WriteRefused(error.code) from None


def complete_task(store: Store, task_id: object, *, request_key: object) -> Outcome:
    return _change(store, "complete_task", "done", task_id, request_key)


def cancel_task(store: Store, task_id: object, *, request_key: object) -> Outcome:
    return _change(store, "cancel_task", "cancel", task_id, request_key)
