"""Phase 6e: docket.writes turns change_deadline and plan_work_time into one keyed core call."""

import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import pytest

from docket import core
from docket.deadlines import Deadline, WorkTime
from docket.store import Store
from tests.support import fixed_times
from tests.support import path as path
from tests.support import store as store

NY = "America/New_York"
NOW = "2026-11-14T14:00:00+00:00"
LATER = "2026-11-14T14:30:00+00:00"
FRIDAY_5PM = Deadline(datetime(2026, 11, 20, 22, 0, tzinfo=UTC), NY, False)
MONDAY = {"date": "2026-11-23", "time": None, "time_zone": NY}
TWO_PM = {"date": "2026-11-20", "time": "14:00", "time_zone": NY}
MARK = "Phase 6e given test: remove this marker when the edit tools are built"


def writes():
    from docket import writes as module

    return module


def dump(path: Path) -> list[str]:
    with closing(sqlite3.connect(path)) as connection:
        return list(connection.iterdump())


def refused(code: str, call) -> None:
    with pytest.raises(writes().WriteRefused) as raised:
        call()
    assert (raised.value.code, str(raised.value)) == (code, code)


def seeded(store: Store, monkeypatch: pytest.MonkeyPatch, *moments: str) -> None:
    fixed_times(monkeypatch, NOW, NOW, NOW)
    core.create_task(store, title="Pay rent", source="owner", deadline=FRIDAY_5PM)
    core.create_task(store, title="Call the bank", source="owner")
    core.change_state(store, "t2", "done", actor="owner")
    fixed_times(monkeypatch, *moments)


@pytest.mark.xfail(strict=True, reason=MARK)
@pytest.mark.parametrize(
    ("start", "minutes", "expected"),
    [
        (TWO_PM, 60, WorkTime(datetime(2026, 11, 20, 19, 0, tzinfo=UTC), 60, NY)),
        (
            {"date": "2026-11-01", "time": "01:30", "time_zone": NY},
            30,
            WorkTime(datetime(2026, 11, 1, 5, 30, tzinfo=UTC), 30, NY),
        ),
        (
            {"date": "2027-03-14", "time": "02:30", "time_zone": NY},
            30,
            WorkTime(datetime(2027, 3, 14, 7, 30, tzinfo=UTC), 30, NY),
        ),
        (
            {"date": "2027-03-14", "time": "09:00", "time_zone": NY},
            45,
            WorkTime(datetime(2027, 3, 14, 13, 0, tzinfo=UTC), 45, NY),
        ),
        (
            {"date": "2026-11-20", "time": "09:00", "time_zone": "Europe/London"},
            5,
            WorkTime(datetime(2026, 11, 20, 9, 0, tzinfo=UTC), 5, "Europe/London"),
        ),
        (
            {"date": "2026-11-20", "time": "09:00", "time_zone": NY},
            720,
            WorkTime(datetime(2026, 11, 20, 14, 0, tzinfo=UTC), 720, NY),
        ),
        (
            {"date": "2026-11-20", "time": "23:00", "time_zone": NY},
            60,
            WorkTime(datetime(2026, 11, 21, 4, 0, tzinfo=UTC), 60, NY),
        ),
    ],
    ids=[
        "afternoon",
        "repeated-hour",
        "skipped-hour",
        "after-dst-change",
        "london-shortest",
        "longest",
        "ends-at-midnight",
    ],
)
def test_a_work_time_is_read_in_its_own_zone(
    start: object, minutes: object, expected: WorkTime
) -> None:
    assert writes().parse_work_time(start, minutes) == expected


@pytest.mark.xfail(strict=True, reason=MARK)
@pytest.mark.parametrize(
    ("start", "minutes"),
    [
        (None, 60),
        ("2026-11-20T14:00", 60),
        (["2026-11-20", "14:00", NY], 60),
        ({"date": "2026-11-20", "time_zone": NY}, 60),
        ({"date": "2026-11-20", "time": None, "time_zone": NY}, 60),
        ({**TWO_PM, "minutes": 60}, 60),
        ({**TWO_PM, "date": "20261120"}, 60),
        ({**TWO_PM, "date": "2026-02-30"}, 60),
        ({**TWO_PM, "time": "2pm"}, 60),
        ({**TWO_PM, "time": "14:00:30"}, 60),
        ({**TWO_PM, "time_zone": "Mars/Base"}, 60),
        ({**TWO_PM, "time_zone": 5}, 60),
        (TWO_PM, 4),
        (TWO_PM, 721),
        (TWO_PM, 0),
        (TWO_PM, -60),
        (TWO_PM, "60"),
        (TWO_PM, 60.0),
        (TWO_PM, True),
        (TWO_PM, None),
        ({**TWO_PM, "time": "23:30"}, 45),
    ],
    ids=[
        "no-start",
        "string",
        "list",
        "missing-time",
        "no-time",
        "extra-field",
        "compact-date",
        "no-such-day",
        "words",
        "seconds",
        "unknown-zone",
        "number-zone",
        "too-short",
        "too-long",
        "zero",
        "negative",
        "string-minutes",
        "float-minutes",
        "boolean-minutes",
        "no-minutes",
        "past-midnight",
    ],
)
def test_a_bad_work_time_is_refused(start: object, minutes: object) -> None:
    refused("invalid_work", lambda: writes().parse_work_time(start, minutes))


@pytest.mark.xfail(strict=True, reason=MARK)
def test_change_deadline_moves_and_removes_it_once_per_key(
    store: Store, path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seeded(store, monkeypatch, LATER, LATER, LATER, LATER)
    moved = writes().change_deadline(store, "t1", deadline=MONDAY, request_key="r1:s2")
    monday = Deadline(datetime(2026, 11, 23, 22, 0, tzinfo=UTC), NY, False)
    assert (moved.task.deadline, moved.changed) == (monday, True)
    found = store.request_key("agent", "r1:s2")
    assert found is not None
    assert (found.request, found.task_id) == (
        {"tool": "change_deadline", "id": "t1", "deadline": MONDAY},
        "t1",
    )
    before = dump(path)
    again = writes().change_deadline(store, "t1", deadline=MONDAY, request_key="r1:s2")
    assert (again.task.deadline, again.changed) == (monday, False)
    assert dump(path) == before
    refused(
        "key_reused",
        lambda: writes().change_deadline(store, "t1", deadline=None, request_key="r1:s2"),
    )
    removed = writes().change_deadline(store, "t1", deadline=None, request_key="r1:s3")
    assert (removed.task.deadline, removed.changed) == (None, True)
    assert [(e.action, e.actor) for e in store.audit("t1")] == [
        ("create", "owner"),
        ("deadline", "agent"),
        ("deadline", "agent"),
    ]


@pytest.mark.xfail(strict=True, reason=MARK)
def test_plan_work_time_plans_once_per_key(
    store: Store, path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seeded(store, monkeypatch, LATER, LATER, LATER, LATER)
    first = writes().plan_work_time(store, "t1", start=TWO_PM, minutes=60, request_key="r1:s3")
    work = WorkTime(datetime(2026, 11, 20, 19, 0, tzinfo=UTC), 60, NY)
    assert (first.task.work, first.changed) == (work, True)
    found = store.request_key("agent", "r1:s3")
    assert found is not None
    assert found.request == {"tool": "plan_work_time", "id": "t1", "start": TWO_PM, "minutes": 60}
    before = dump(path)
    again = writes().plan_work_time(store, "t1", start=TWO_PM, minutes=60, request_key="r1:s3")
    assert (again.task.work, again.changed) == (work, False)
    assert dump(path) == before
    refused(
        "key_reused",
        lambda: writes().plan_work_time(store, "t1", start=TWO_PM, minutes=90, request_key="r1:s3"),
    )
    moved = writes().plan_work_time(
        store, "t1", start={**TWO_PM, "time": "09:30"}, minutes=90, request_key="r1:s4"
    )
    assert (moved.task.work, moved.changed) == (
        WorkTime(datetime(2026, 11, 20, 14, 30, tzinfo=UTC), 90, NY),
        True,
    )
    assert [(e.action, e.actor) for e in store.audit("t1")][1:] == [
        ("work_time", "agent"),
        ("work_time", "agent"),
    ]


@pytest.mark.xfail(strict=True, reason=MARK)
@pytest.mark.parametrize(
    ("tool", "task_id", "value", "key", "code", "moments"),
    [
        ("change_deadline", 1, "Friday", "", "unknown_task", ()),
        ("plan_work_time", None, None, "", "unknown_task", ()),
        ("change_deadline", "t1", "Friday", "", "invalid_deadline", ()),
        ("plan_work_time", "t1", None, "", "invalid_work", ()),
        ("change_deadline", "t1", MONDAY, "", "invalid_key", ()),
        ("plan_work_time", "t1", TWO_PM, "k" * 201, "invalid_key", ()),
        ("change_deadline", "t99", MONDAY, "r1:s2", "unknown_task", (LATER,)),
        ("plan_work_time", "T1", TWO_PM, "r1:s2", "unknown_task", (LATER,)),
        ("change_deadline", "t2", MONDAY, "r1:s2", "task_ended", (LATER,)),
        ("plan_work_time", "t2", TWO_PM, "r1:s2", "task_ended", (LATER,)),
        (
            "plan_work_time",
            "t1",
            {**TWO_PM, "time": "16:30"},
            "r1:s2",
            "work_after_deadline",
            (LATER,),
        ),
    ],
    ids=[
        "number-id-first",
        "no-id-first",
        "deadline-before-key",
        "work-before-key",
        "empty-key",
        "long-key",
        "beyond-every-id",
        "capital",
        "ended-deadline",
        "ended-work",
        "after-the-deadline",
    ],
)
def test_edit_refusals(
    store: Store,
    path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tool: str,
    task_id: object,
    value: object,
    key: str,
    code: str,
    moments: tuple[str, ...],
) -> None:
    seeded(store, monkeypatch, *moments)
    before = dump(path)
    fields = {"deadline": value} if tool == "change_deadline" else {"start": value, "minutes": 60}
    refused(code, lambda: getattr(writes(), tool)(store, task_id, request_key=key, **fields))
    assert dump(path) == before
