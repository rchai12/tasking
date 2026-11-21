"""Phase 6e: a keyed deadline or work-time edit is applied once, and its key is kept."""

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
from tests.support import refused as refused
from tests.support import store as store

NY = "America/New_York"
NOW = "2026-11-14T14:00:00+00:00"
LATER = "2026-11-14T14:30:00+00:00"
LAST = "2026-11-14T15:00:00+00:00"
AT_LATER = datetime(2026, 11, 14, 14, 30, tzinfo=UTC)
FRIDAY_5PM = Deadline(datetime(2026, 11, 20, 22, 0, tzinfo=UTC), NY, False)
MONDAY_5PM = Deadline(datetime(2026, 11, 23, 22, 0, tzinfo=UTC), NY, False)
FRIDAY_2PM = WorkTime(datetime(2026, 11, 20, 19, 0, tzinfo=UTC), 60, NY)
MONDAY = {"date": "2026-11-23", "time": None, "time_zone": NY}
MOVE = {"tool": "change_deadline", "id": "t1", "deadline": MONDAY}
PLAN = {
    "tool": "plan_work_time",
    "id": "t1",
    "start": {"date": "2026-11-20", "time": "14:00", "time_zone": NY},
    "minutes": 60,
}
MARK = "Phase 6e given test: remove this marker when the edit tools are built"


def dump(path: Path) -> list[str]:
    with closing(sqlite3.connect(path)) as connection:
        return list(connection.iterdump())


def seeded(store: Store, monkeypatch: pytest.MonkeyPatch, *moments: str) -> None:
    fixed_times(monkeypatch, NOW)
    core.create_task(store, title="Pay rent", source="owner", deadline=FRIDAY_5PM)
    fixed_times(monkeypatch, *moments)


def once(store: Store, key: str, request: dict, task_id: str = "t1", **fields):
    return core.edit_task_once(store, task_id, client="agent", key=key, request=request, **fields)


def pending(store: Store) -> list[str]:
    return [r.kind for r in store.reminders("t1") if r.voided_at is None and r.sent_at is None]


@pytest.mark.xfail(strict=True, reason=MARK)
def test_a_keyed_deadline_change_is_made_once_and_keeps_its_key(
    store: Store, path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seeded(store, monkeypatch, LATER, LAST)
    first = once(store, "run-1:step-2", MOVE, deadline=MONDAY_5PM)
    assert (first.task.deadline, first.task.updated_at, first.changed) == (
        MONDAY_5PM,
        AT_LATER,
        True,
    )
    found = store.request_key("agent", "run-1:step-2")
    assert found is not None
    assert (found.request, found.task_id, found.link_id, found.created_at) == (
        MOVE,
        "t1",
        None,
        AT_LATER,
    )
    assert [(e.action, e.actor) for e in store.audit("t1")] == [
        ("create", "owner"),
        ("deadline", "agent"),
    ]
    before = dump(path)
    again = once(store, "run-1:step-2", MOVE, deadline=MONDAY_5PM)
    assert (again.task.deadline, again.changed) == (MONDAY_5PM, False)
    assert dump(path) == before


@pytest.mark.xfail(strict=True, reason=MARK)
def test_a_retried_step_changes_nothing_after_the_owner_moves_the_deadline_back(
    store: Store, path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seeded(store, monkeypatch, LATER, LAST, LAST)
    once(store, "run-1:step-2", MOVE, deadline=MONDAY_5PM)
    core.edit_task(store, "t1", actor="owner", deadline=FRIDAY_5PM)
    before = dump(path)
    again = once(store, "run-1:step-2", MOVE, deadline=MONDAY_5PM)
    assert (again.task.deadline, again.changed) == (FRIDAY_5PM, False)
    assert dump(path) == before


@pytest.mark.xfail(strict=True, reason=MARK)
def test_a_keyed_work_time_is_planned_once(
    store: Store, path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seeded(store, monkeypatch, LATER, LAST, LAST)
    first = once(store, "run-1:step-3", PLAN, work=FRIDAY_2PM)
    assert (first.task.work, first.task.deadline, first.changed) == (FRIDAY_2PM, FRIDAY_5PM, True)
    assert [(e.action, e.actor) for e in store.audit("t1")][1:] == [("work_time", "agent")]
    assert "start" in pending(store)
    same = once(store, "run-2:step-1", PLAN, work=FRIDAY_2PM)
    assert (same.task.work, same.changed) == (FRIDAY_2PM, False)
    found = store.request_key("agent", "run-2:step-1")
    assert found is not None
    assert (found.request, found.task_id) == (PLAN, "t1")
    before = dump(path)
    assert once(store, "run-1:step-3", PLAN, work=FRIDAY_2PM).changed is False
    assert dump(path) == before


@pytest.mark.xfail(strict=True, reason=MARK)
@pytest.mark.parametrize(
    ("key", "request_body", "fields"),
    [
        ("run-1:step-2", {**MOVE, "deadline": None}, {"deadline": None}),
        ("run-1:step-2", PLAN, {"work": FRIDAY_2PM}),
        ("run-0:step-1", MOVE, {"deadline": MONDAY_5PM}),
        ("run-0:step-2", PLAN, {"work": FRIDAY_2PM}),
    ],
    ids=["other-deadline", "other-tool", "a-create-key", "a-done-key"],
)
def test_a_key_used_for_another_request_is_refused_and_writes_nothing(
    store: Store,
    path: Path,
    monkeypatch: pytest.MonkeyPatch,
    key: str,
    request_body: dict,
    fields: dict,
) -> None:
    seeded(store, monkeypatch, NOW, NOW, LATER, LAST)
    core.create_task_once(
        store,
        client="agent",
        key="run-0:step-1",
        request={"tool": "create_task", "title": "Book a dentist", "deadline": None},
        title="Book a dentist",
        source="agent",
    )
    core.change_state_once(
        store,
        "t2",
        "done",
        client="agent",
        key="run-0:step-2",
        request={"tool": "complete_task", "id": "t2"},
    )
    once(store, "run-1:step-2", MOVE, deadline=MONDAY_5PM)
    before = dump(path)
    refused("key_reused", lambda: once(store, key, request_body, **fields))
    assert dump(path) == before


@pytest.mark.xfail(strict=True, reason=MARK)
@pytest.mark.parametrize(
    ("values", "code"),
    [
        ({"client": "conductor", "deadline": "Friday"}, "invalid_client"),
        ({"client": None}, "invalid_client"),
        ({"key": "", "deadline": "Friday"}, "invalid_key"),
        ({"key": "k" * 201}, "invalid_key"),
        ({"key": 7}, "invalid_key"),
        ({"deadline": "2026-11-23"}, "invalid_deadline"),
        ({"deadline": FRIDAY_2PM, "work": MONDAY_5PM}, "invalid_deadline"),
        ({"work": {"minutes": 60}}, "invalid_work"),
    ],
    ids=[
        "client-first",
        "no-client",
        "key-before-values",
        "long-key",
        "number-key",
        "string-deadline",
        "swapped",
        "dict-work",
    ],
)
def test_bad_input_is_refused_before_the_clock(
    store: Store, path: Path, monkeypatch: pytest.MonkeyPatch, values: dict, code: str
) -> None:
    seeded(store, monkeypatch)
    before = dump(path)
    arguments: dict[str, object] = {"client": "agent", "key": "run-1:step-2", "request": MOVE}
    arguments.update(values)
    refused(code, lambda: core.edit_task_once(store, "t1", **arguments))
    assert dump(path) == before


@pytest.mark.xfail(strict=True, reason=MARK)
def test_a_refused_edit_keeps_the_key_free(
    store: Store, path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seeded(store, monkeypatch, LATER, LAST, LAST, LAST)
    missing = {**MOVE, "id": "t99"}
    refused("unknown_task", lambda: once(store, "k1", missing, task_id="t99", deadline=None))
    early = {**PLAN, "start": {"date": "2026-11-20", "time": "17:30", "time_zone": NY}}
    late = WorkTime(datetime(2026, 11, 20, 22, 30, tzinfo=UTC), 60, NY)
    refused("work_after_deadline", lambda: once(store, "k2", early, work=late))
    assert [store.request_key("agent", key) for key in ("k1", "k2")] == [None, None]
    core.change_state(store, "t1", "done", actor="owner")
    before = dump(path)
    refused("task_ended", lambda: once(store, "k3", MOVE, deadline=MONDAY_5PM))
    assert store.request_key("agent", "k3") is None
    assert dump(path) == before


@pytest.mark.xfail(strict=True, reason=MARK)
def test_moving_the_deadline_before_the_work_time_is_refused(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    seeded(store, monkeypatch, LATER, LAST, LAST)
    once(store, "run-1:step-3", PLAN, work=FRIDAY_2PM)
    early = Deadline(datetime(2026, 11, 20, 19, 30, tzinfo=UTC), NY, True)
    moved = {**MOVE, "deadline": {"date": "2026-11-20", "time": "14:30", "time_zone": NY}}
    refused("work_after_deadline", lambda: once(store, "run-1:step-4", moved, deadline=early))
    removed = once(store, "run-1:step-5", {**MOVE, "deadline": None}, deadline=None)
    assert (removed.task.deadline, removed.task.work, removed.changed) == (None, FRIDAY_2PM, True)
