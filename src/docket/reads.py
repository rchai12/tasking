"""Read-only task queries for the MCP read tools."""

import re
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from docket import clock, domain
from docket.store import Reminder, Store, Task

STATUSES = ("open", "in_progress", "due", "overdue", "done", "cancelled")
PAGE_SIZE = 50
INVALID_STATUS = "invalid_status"
INVALID_CURSOR = "invalid_cursor"
UNKNOWN_TASK = "unknown_task"

_ID = re.compile(r"t[1-9][0-9]*")


class ReadRefused(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class TaskPage:
    tasks: tuple[Task, ...]
    next_after: str | None


@dataclass(frozen=True)
class TaskRecord:
    task: Task
    reminders: tuple[Reminder, ...]


def _matcher(status: str, zone: str):
    if status in ("due", "overdue"):
        now = clock.now()
        today = now.astimezone(ZoneInfo(zone)).date()

        def matches(task: Task) -> bool:
            if task.deadline is None:
                return False
            if status == "overdue":
                return task.deadline.at <= now
            return (
                now < task.deadline.at
                and task.deadline.at.astimezone(ZoneInfo(zone)).date() == today
            )

        return matches
    return lambda task: True


def list_tasks(store: Store, status: object, after: object, *, zone: str) -> TaskPage:
    if not isinstance(status, str) or status not in STATUSES:
        raise ReadRefused(INVALID_STATUS)
    cursor = 0
    if after is not None:
        if not isinstance(after, str) or _ID.fullmatch(after) is None:
            raise ReadRefused(INVALID_CURSOR)
        cursor = int(after[1:])
    states = domain.OPEN_STATES if status in ("due", "overdue") else (status,)
    matches = _matcher(status, zone)
    found = [task for task in store.tasks(states) if int(task.id[1:]) > cursor and matches(task)]
    page = found[:PAGE_SIZE]
    more = len(found) > PAGE_SIZE
    return TaskPage(tuple(page), page[-1].id if more else None)


def task_record(store: Store, task_id: object) -> TaskRecord:
    task = store.task(task_id) if isinstance(task_id, str) else None
    if task is None:
        raise ReadRefused(UNKNOWN_TASK)
    reminders = tuple(r for r in store.reminders(task.id) if r.voided_at is None)
    return TaskRecord(task, reminders)
