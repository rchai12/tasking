"""Phase 6d: docket.writes turns an agent's write into one keyed core call."""

import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import pytest

from docket import core
from docket.deadlines import Deadline
from docket.store import Store
from tests.support import fixed_times
from tests.support import path as path
from tests.support import store as store

NY = "America/New_York"
NOW = "2026-11-14T14:00:00+00:00"
LATER = "2026-11-14T14:30:00+00:00"
AT_NOW = datetime(2026, 11, 14, 14, 0, tzinfo=UTC)
FRIDAY = {"date": "2026-11-20", "time": None, "time_zone": NY}
MARK = "Phase 6d given test: remove this marker when the write tools are built"


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


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        (FRIDAY, Deadline(datetime(2026, 11, 20, 22, 0, tzinfo=UTC), NY, False)),
        (
            {"date": "2026-11-20", "time": "09:15", "time_zone": NY},
            Deadline(datetime(2026, 11, 20, 14, 15, tzinfo=UTC), NY, True),
        ),
        (
            {"date": "2026-11-01", "time": "01:30", "time_zone": NY},
            Deadline(datetime(2026, 11, 1, 5, 30, tzinfo=UTC), NY, True),
        ),
        (
            {"date": "2027-03-14", "time": None, "time_zone": NY},
            Deadline(datetime(2027, 3, 14, 21, 0, tzinfo=UTC), NY, False),
        ),
        (
            {"date": "2026-11-20", "time": "17:00", "time_zone": "Europe/London"},
            Deadline(datetime(2026, 11, 20, 17, 0, tzinfo=UTC), "Europe/London", True),
        ),
    ],
    ids=["none", "date-only", "date-and-time", "repeated-hour", "after-dst-change", "london"],
)
def test_a_deadline_is_read_in_its_own_zone(value: object, expected: Deadline | None) -> None:
    assert writes().parse_deadline(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "2026-11-20",
        ["2026-11-20", None, NY],
        {"date": "2026-11-20", "time_zone": NY},
        {"date": "2026-11-20", "time": None, "time_zone": NY, "at": "2026-11-20T22:00:00Z"},
        {"date": "20261120", "time": None, "time_zone": NY},
        {"date": "2026-02-30", "time": None, "time_zone": NY},
        {"date": "2026-11-20", "time": "5pm", "time_zone": NY},
        {"date": "2026-11-20", "time": "17:00:30", "time_zone": NY},
        {"date": "2026-11-20", "time": "24:00", "time_zone": NY},
        {"date": "2026-11-20", "time": None, "time_zone": "Mars/Base"},
        {"date": "2026-11-20", "time": None, "time_zone": "america/new_york"},
        {"date": "2026-11-20", "time": None, "time_zone": 5},
        {"date": 20261120, "time": None, "time_zone": NY},
    ],
    ids=[
        "string",
        "list",
        "missing-time",
        "extra-field",
        "compact-date",
        "no-such-day",
        "words",
        "seconds",
        "hour-24",
        "unknown-zone",
        "zone-case",
        "number-zone",
        "number-date",
    ],
)
def test_a_bad_deadline_is_refused(value: object) -> None:
    refused("invalid_deadline", lambda: writes().parse_deadline(value))


def test_create_task_makes_an_agent_task_once_per_key(
    store: Store, path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_times(monkeypatch, NOW, LATER)
    first = writes().create_task(store, title="Pay rent", deadline=FRIDAY, request_key="r1:s1")
    task = first.task
    assert (task.id, task.title, task.state, task.source, first.changed) == (
        "t1",
        "Pay rent",
        "open",
        "agent",
        True,
    )
    assert task.deadline == Deadline(datetime(2026, 11, 20, 22, 0, tzinfo=UTC), NY, False)
    assert [(e.action, e.actor) for e in store.audit("t1")] == [("create", "agent")]
    found = store.request_key("agent", "r1:s1")
    assert found is not None
    assert (found.request, found.task_id, found.created_at) == (
        {"tool": "create_task", "title": "Pay rent", "deadline": FRIDAY},
        "t1",
        AT_NOW,
    )
    before = dump(path)
    again = writes().create_task(store, title="Pay rent", deadline=FRIDAY, request_key="r1:s1")
    assert (again.task.id, again.changed) == ("t1", False)
    assert dump(path) == before


@pytest.mark.parametrize(
    ("title", "deadline"),
    [("Pay the rent", FRIDAY), ("Pay rent", None)],
    ids=["other-title", "other-deadline"],
)
def test_create_task_refuses_a_key_reused_with_other_arguments(
    store: Store, path: Path, monkeypatch: pytest.MonkeyPatch, title: str, deadline: object
) -> None:
    fixed_times(monkeypatch, NOW, LATER)
    writes().create_task(store, title="Pay rent", deadline=FRIDAY, request_key="r1:s1")
    before = dump(path)
    refused(
        "key_reused",
        lambda: writes().create_task(store, title=title, deadline=deadline, request_key="r1:s1"),
    )
    assert dump(path) == before


@pytest.mark.parametrize(
    ("title", "deadline", "key", "code"),
    [
        ("Pay rent", "2026-11-20", "", "invalid_deadline"),
        ("", FRIDAY, "", "invalid_key"),
        ("", FRIDAY, "r1:s1", "invalid_title"),
        ("Pay rent\nnow", None, "r1:s1", "invalid_title"),
        ("x" * 101, None, "r1:s1", "invalid_title"),
        ("Pay rent", None, "k" * 201, "invalid_key"),
    ],
    ids=["deadline-first", "then-key", "then-title", "two-lines", "long-title", "long-key"],
)
def test_create_task_refusals_come_before_the_clock(
    store: Store,
    path: Path,
    monkeypatch: pytest.MonkeyPatch,
    title: str,
    deadline: object,
    key: str,
    code: str,
) -> None:
    fixed_times(monkeypatch)
    before = dump(path)
    refused(
        code, lambda: writes().create_task(store, title=title, deadline=deadline, request_key=key)
    )
    assert dump(path) == before


@pytest.mark.parametrize(
    ("tool", "state", "action"),
    [("complete_task", "done", "done"), ("cancel_task", "cancelled", "cancel")],
    ids=["complete", "cancel"],
)
def test_complete_and_cancel_are_keyed_state_changes(
    store: Store, path: Path, monkeypatch: pytest.MonkeyPatch, tool: str, state: str, action: str
) -> None:
    fixed_times(monkeypatch, NOW, LATER, LATER)
    core.create_task(store, title="Pay rent", source="owner")
    first = getattr(writes(), tool)(store, "t1", request_key="r1:s2")
    assert (first.task.state, first.changed) == (state, True)
    found = store.request_key("agent", "r1:s2")
    assert found is not None
    assert (found.request, found.task_id) == ({"tool": tool, "id": "t1"}, "t1")
    assert [(e.action, e.actor) for e in store.audit("t1")] == [
        ("create", "owner"),
        (action, "agent"),
    ]
    before = dump(path)
    again = getattr(writes(), tool)(store, "t1", request_key="r1:s2")
    assert (again.task.state, again.changed) == (state, False)
    assert dump(path) == before


@pytest.mark.parametrize(
    ("tool", "task_id", "key", "code", "moments"),
    [
        ("complete_task", "t99", "r1:s2", "unknown_task", (LATER,)),
        ("cancel_task", "T1", "r1:s2", "unknown_task", (LATER,)),
        ("complete_task", 1, "r1:s2", "unknown_task", ()),
        ("cancel_task", None, "", "unknown_task", ()),
        ("complete_task", "t1", "", "invalid_key", ()),
        ("cancel_task", "t2", "r1:s2", "task_ended", (LATER,)),
    ],
    ids=["beyond-every-id", "capital", "number-id", "id-before-key", "empty-key", "ended"],
)
def test_state_change_refusals(
    store: Store,
    path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tool: str,
    task_id: object,
    key: str,
    code: str,
    moments: tuple[str, ...],
) -> None:
    fixed_times(monkeypatch, NOW, NOW, NOW)
    core.create_task(store, title="Pay rent", source="owner")
    core.create_task(store, title="Call the bank", source="owner")
    core.change_state(store, "t2", "done", actor="owner")
    fixed_times(monkeypatch, *moments)
    before = dump(path)
    refused(code, lambda: getattr(writes(), tool)(store, task_id, request_key=key))
    assert dump(path) == before
