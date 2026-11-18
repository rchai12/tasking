from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from docket.deadlines import INSTANT_MESSAGE, DeadlineError
from docket.domain import OPEN_STATES
from docket.store import Task

LATE_MINUTES = (30, 60, 120, 180, 240, 480, 720)
_HOUR = timedelta(hours=1)
_KIND_ORDER = {"start": 0, "before": 1, "due_soon": 2, "due": 3, "late": 4}


@dataclass(frozen=True)
class PlannedReminder:
    kind: Literal["start", "before", "due_soon", "due", "late"]
    fire_at: datetime


def plan_reminders(task: Task, now: datetime) -> tuple[PlannedReminder, ...]:
    if now.tzinfo is not UTC:
        raise DeadlineError(INSTANT_MESSAGE)
    if task.state not in OPEN_STATES or (task.deadline is None and task.work is None):
        return ()
    rows: list[PlannedReminder] = []
    if task.work is not None:
        rows.append(PlannedReminder("start", task.work.start))
    deadline = task.deadline
    if deadline is not None:
        remaining = deadline.at - now
        if remaining >= _HOUR:
            rows.append(PlannedReminder("before", deadline.at - _HOUR))
        elif remaining > timedelta(0):
            rows.append(PlannedReminder("due_soon", now))
        rows.append(PlannedReminder("due", deadline.at))
        for minutes in LATE_MINUTES:
            rows.append(PlannedReminder("late", deadline.at + timedelta(minutes=minutes)))
    rows.sort(key=lambda row: (row.fire_at, _KIND_ORDER[row.kind]))
    return tuple(rows)
