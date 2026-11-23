from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

from docket import clock, ids
from docket.deadlines import make_deadline
from docket.domain import OPEN_STATES
from docket.notifier import Digest, DigestLine, Notice, Notifier, NotifierError
from docket.reminder_plan import LATE_MINUTES, PlannedReminder, plan_reminders
from docket.store import LoopStatus, Post, Store, StoreError, Task
from docket.views import deadline_text, digest_heading, notice_text

__all__ = ["LATE_MINUTES", "PlannedReminder", "plan_reminders", "notice_text", "digest_heading"]

CLAIM_MINUTES = 5


def send_due(store: Store, notifier: Notifier) -> int:
    return _send_due(store, notifier)[0]


def _send_due(store: Store, notifier: Notifier) -> tuple[int, tuple[str, ...]]:
    now = clock.now()
    stale_before = now - timedelta(minutes=CLAIM_MINUTES)
    claimed: list[tuple[Post, str]] = []
    skipped: list[str] = []
    for task_id in store.pending_task_ids(at=now, stale_before=stale_before):
        try:
            with store.transaction():
                due = store.due_reminders(now, task_id=task_id)
                if due:
                    store.queue_post(
                        task_id,
                        tuple(row.id for row in due),
                        key=ids.new_id(),
                        kind=due[-1].kind,
                        missed=sum(row.fire_at > row.planned_at for row in due),
                        at=now,
                    )
                posts = store.claim_posts(at=now, stale_before=stale_before, task_id=task_id)
                title = store.task(task_id).title
        except StoreError:
            skipped.append(task_id)
            continue
        claimed.extend((post, title) for post in posts)
    claimed.sort(key=lambda found: int(found[0].id[1:]))
    sent = 0
    for post, title in claimed:
        notice = Notice(post.key, post.task_id, title, notice_text(post.kind, post.missed))
        try:
            notifier.send(notice)
        except NotifierError:
            with store.transaction():
                store.release_post(post.id, claimed_at=now)
            continue
        with store.transaction():
            store.mark_post_sent(post.id, at=now)
        sent += 1
    return sent, tuple(skipped)


def digest_slot(now: datetime, zone: str, at: time) -> tuple[date, datetime]:
    home = now.astimezone(ZoneInfo(zone)).date()
    return home, make_deadline(home, at, zone).at


def _past_last_late(task: Task, slot: datetime) -> bool:
    deadline = task.deadline
    return (
        task.state in OPEN_STATES
        and deadline is not None
        and deadline.at + timedelta(minutes=LATE_MINUTES[-1]) <= slot
    )


def send_digest(store: Store, notifier: Notifier, *, zone: str, at: time) -> bool:
    now = clock.now()
    day, slot = digest_slot(now, zone, at)
    if now < slot:
        return False
    with store.transaction():
        if store.digest(day) is None:
            overdue = [task for task in store.tasks(OPEN_STATES) if _past_last_late(task, slot)]
            if overdue:
                store.queue_digest(
                    day,
                    tuple(task.id for task in overdue),
                    key=ids.new_id(),
                    at=now,
                )
        claimed = store.claim_digest(
            day,
            at=now,
            stale_before=now - timedelta(minutes=CLAIM_MINUTES),
            overdue_before=slot - timedelta(minutes=LATE_MINUTES[-1]),
        )
    if claimed is None:
        return False
    chosen = []
    for task_id in claimed.task_ids:
        task = store.task(task_id)
        if _past_last_late(task, slot):
            chosen.append(task)
    if not chosen:
        with store.transaction():
            store.mark_digest_sent(claimed.id, at=now)
        return False
    chosen.sort(key=lambda task: (task.deadline.at, int(task.id[1:])))
    lines = tuple(
        DigestLine(task.id, task.title, "Was due " + deadline_text(task.deadline, zone, now))
        for task in chosen
    )
    try:
        notifier.send_digest(Digest(claimed.key, digest_heading(len(lines)), lines))
    except NotifierError:
        with store.transaction():
            store.release_digest(claimed.id, claimed_at=now)
        return False
    with store.transaction():
        store.mark_digest_sent(claimed.id, at=now)
    return True


LOOP_SECONDS = 30


@dataclass(frozen=True)
class PassResult:
    sent: int
    digest: bool
    failed: tuple[str, ...]
    skipped: tuple[str, ...] = ()


class Stop(Protocol):
    def is_set(self) -> bool:
        """True when the caller wants the loop to return."""

    def wait(self, timeout: float) -> bool:
        """Pause up to timeout seconds. True means the loop should return."""


def run_pass(store: Store, notifier: Notifier, *, zone: str, at: time) -> PassResult:
    sent = 0
    sent_digest = False
    failed: list[str] = []
    skipped: tuple[str, ...] = ()
    try:
        sent, skipped = _send_due(store, notifier)
    except Exception:
        failed.append("reminders")
    try:
        sent_digest = send_digest(store, notifier, zone=zone, at=at)
    except Exception:
        failed.append("digest")
    return PassResult(sent, sent_digest, tuple(failed), skipped)


def next_status(previous: LoopStatus | None, result: PassResult, at: datetime) -> LoopStatus:
    reminders_before = 0 if previous is None else previous.reminders_failures
    digest_before = 0 if previous is None else previous.digest_failures
    reminders_failed = "reminders" in result.failed or bool(result.skipped)
    return LoopStatus(
        pass_at=at,
        sent=result.sent,
        digest=result.digest,
        reminders_failures=reminders_before + 1 if reminders_failed else 0,
        digest_failures=digest_before + 1 if "digest" in result.failed else 0,
        skipped=result.skipped,
    )


def _record(store: Store, result: PassResult) -> None:
    try:
        with store.transaction():
            try:
                previous = store.loop_status()
            except StoreError:
                previous = None
            store.save_loop_status(next_status(previous, result, clock.now()))
    except Exception:
        return


def run_loop(store: Store, notifier: Notifier, *, zone: str, at: time, stop: Stop) -> int:
    passes = 0
    while not stop.is_set():
        _record(store, run_pass(store, notifier, zone=zone, at=at))
        passes += 1
        if stop.wait(LOOP_SECONDS):
            return passes
    return passes
