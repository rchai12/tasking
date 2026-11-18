"""A fake notifier, synthetic sending inputs and helpers for the Phase 3c tests."""

import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from docket.deadlines import Deadline, WorkTime
from docket.notifier import Notice, NotifierError

NOW = datetime(2026, 11, 20, 16, tzinfo=UTC)


def at(minutes: float) -> str:
    """The ISO instant `minutes` after NOW, for fixed_times."""
    return (NOW + timedelta(minutes=minutes)).isoformat()


def due_in(minutes: float) -> Deadline:
    return Deadline(NOW + timedelta(minutes=minutes), "UTC", True)


def work_in(minutes: float) -> WorkTime:
    return WorkTime(NOW + timedelta(minutes=minutes), 30, "UTC")


class Killed(BaseException):
    """Stands for the process dying mid-send: nothing after it runs."""


class SyntheticBug(Exception):
    """An unexpected notifier failure that is not a NotifierError."""


class FakeNotifier:
    """Delivers each key at most once, as the shared Discord service's keyed request does.

    `attempts` records every send. `fail` is how many next sends raise NotifierError before
    delivering. `before` is raised before delivering, `after` after delivering, each once.
    `during` runs once inside the next send, before anything else, to interleave a second loop.
    """

    def __init__(self) -> None:
        self.attempts: list[Notice] = []
        self.delivered: list[Notice] = []
        self.fail = 0
        self.before: BaseException | None = None
        self.after: BaseException | None = None
        self.during: Callable[[], None] | None = None

    def send(self, notice: Notice) -> None:
        self.attempts.append(notice)
        if self.during is not None:
            hook, self.during = self.during, None
            hook()
        if self.fail:
            self.fail -= 1
            raise NotifierError("synthetic delivery failure")
        if self.before is not None:
            error, self.before = self.before, None
            raise error
        if all(sent.key != notice.key for sent in self.delivered):
            self.delivered.append(notice)
        if self.after is not None:
            error, self.after = self.after, None
            raise error


def rows(path: Path, table: str) -> list[tuple]:
    with sqlite3.connect(path) as db:
        return db.execute(f'SELECT * FROM "{table}" ORDER BY 1').fetchall()


def send_in_child(path: str, moment: str, prefix: str, start, messages) -> None:
    """One loop pass in its own process with its own fake, clock and ids."""
    from docket import clock, ids, reminders
    from docket.store import Store

    counter = iter(range(1, 100))
    clock.now = lambda: datetime.fromisoformat(moment)
    ids.new_id = lambda: f"{prefix}{next(counter)}"
    try:
        assert start.wait(10)
        notifier = FakeNotifier()
        with Store(Path(path)) as opened:
            sent = reminders.send_due(opened, notifier)
        messages.put(("ok", sent, [notice.key for notice in notifier.delivered]))
    except BaseException as error:
        messages.put(("error", type(error).__name__))
