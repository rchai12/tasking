"""Synthetic v3 upgrade inputs and literal durable reminder projections."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from docket import schema
from docket.deadlines import Deadline, WorkTime

NOW = "2026-11-20T16:00:00+00:00"
LATER = "2026-11-20T16:15:00+00:00"
AT = datetime(2026, 11, 20, 16, tzinfo=UTC)
NEXT = datetime(2026, 11, 20, 16, 15, tzinfo=UTC)
DUE = Deadline(datetime(2026, 11, 20, 18, tzinfo=UTC), "UTC", True)
WORK = WorkTime(datetime(2026, 11, 20, 16, 30, tzinfo=UTC), 5, "UTC")
PLAN = [
    ["before", "2026-11-20T17:00:00+00:00"],
    ["due", "2026-11-20T18:00:00+00:00"],
    ["late", "2026-11-20T18:30:00+00:00"],
    ["late", "2026-11-20T19:00:00+00:00"],
    ["late", "2026-11-20T20:00:00+00:00"],
    ["late", "2026-11-20T21:00:00+00:00"],
    ["late", "2026-11-20T22:00:00+00:00"],
    ["late", "2026-11-21T02:00:00+00:00"],
    ["late", "2026-11-21T06:00:00+00:00"],
]
WITH_WORK = [["start", "2026-11-20T16:30:00+00:00"], *PLAN]


class InterruptedWrite(Exception):
    pass


def project(rows: list) -> list[list[str]]:
    return [[row.kind, row.fire_at.isoformat()] for row in rows]


def snapshot(path: Path) -> dict:
    with sqlite3.connect(path) as db:
        names = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        return {name: db.execute(f'SELECT * FROM "{name}" ORDER BY 1').fetchall() for name in names}


def version_three(path: Path, *, overflow: bool = False) -> None:
    with sqlite3.connect(path) as db:
        db.executescript("".join(schema.MIGRATIONS[:3]))
        for state in ("open", "in_progress", "done", "cancelled"):
            due = "9999-12-31T23:59:00+00:00" if overflow else "2026-11-20T18:00:00+00:00"
            db.execute(
                "INSERT INTO tasks(title,state,deadline_at,deadline_zone,deadline_time_given,"
                "work_start,work_minutes,work_zone,source,created_at,updated_at) "
                "VALUES ('Synthetic task',?,?,'UTC',1,'2026-11-20T16:30:00+00:00',5,'UTC',"
                "'owner','2026-11-19T16:00:00+00:00','2026-11-20T16:00:00+00:00')",
                (state, due),
            )
        db.execute("PRAGMA user_version = 3")


def open_upgraded(path: str, start, messages) -> None:
    from docket.store import Store

    try:
        assert start.wait(10)
        with Store(Path(path)) as opened:
            messages.put(("ok", len(opened.reminders("t1")), len(opened.reminders("t2"))))
    except BaseException as error:
        messages.put(("error", type(error).__name__))
