from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from docket import clock, ids
from docket.deadlines import INSTANT_MESSAGE, DeadlineError
from docket.domain import OPEN_STATES
from docket.notifier import Notice, Notifier, NotifierError
from docket.store import Store, Task

LATE_MINUTES = (30, 60, 120, 180, 240, 480, 720)
CLAIM_MINUTES = 5
_HOUR = timedelta(hours=1)
_KIND_ORDER = {"start": 0, "before": 1, "due_soon": 2, "due": 3, "late": 4}
_NOTICE = {
    "start": "Time to start.",
    "before": "Are you working on this?",
    "due_soon": "This is due soon.",
    "due": "This is now due.",
    "late": "This is late.",
}


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


def notice_text(kind: str, missed: int) -> str:
    line = _NOTICE[kind]
    if missed >= 2:
        return f"Missed while docket was offline: {missed} reminders.\n{line}"
    return line


def send_due(store: Store, notifier: Notifier) -> int:
    now = clock.now()
    with store.transaction():
        grouped: dict[str, list] = {}
        order: list[str] = []
        for row in store.due_reminders(now):
            if row.task_id not in grouped:
                order.append(row.task_id)
                grouped[row.task_id] = []
            grouped[row.task_id].append(row)
        for task_id in order:
            due = grouped[task_id]
            store.queue_post(
                task_id,
                tuple(row.id for row in due),
                key=ids.new_id(),
                kind=due[-1].kind,
                missed=sum(row.fire_at > row.planned_at for row in due),
                at=now,
            )
        claimed = store.claim_posts(at=now, stale_before=now - timedelta(minutes=CLAIM_MINUTES))
    sent = 0
    for post in claimed:
        task = store.task(post.task_id)
        notice = Notice(post.key, post.task_id, task.title, notice_text(post.kind, post.missed))
        try:
            notifier.send(notice)
        except NotifierError:
            with store.transaction():
                store.release_post(post.id, claimed_at=now)
            continue
        with store.transaction():
            store.mark_post_sent(post.id, at=now)
        sent += 1
    return sent
