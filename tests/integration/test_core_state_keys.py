"""Phase 6d: a keyed state change is applied once, and its key is kept with the request."""

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
from tests.support import refused as refused
from tests.support import store as store

NY = "America/New_York"
NOW = "2026-11-14T14:00:00+00:00"
LATER = "2026-11-14T14:30:00+00:00"
LAST = "2026-11-14T15:00:00+00:00"
AT_NOW = datetime(2026, 11, 14, 14, 0, tzinfo=UTC)
AT_LATER = datetime(2026, 11, 14, 14, 30, tzinfo=UTC)
FRIDAY_5PM = Deadline(datetime(2026, 11, 20, 22, 0, tzinfo=UTC), NY, False)
DONE = {"tool": "complete_task", "id": "t1"}
CANCEL = {"tool": "cancel_task", "id": "t1"}
MARK = "Phase 6d given test: remove this marker when the write tools are built"


def dump(path: Path) -> list[str]:
    with closing(sqlite3.connect(path)) as connection:
        return list(connection.iterdump())


def seeded(store: Store, monkeypatch: pytest.MonkeyPatch, *moments: str) -> None:
    fixed_times(monkeypatch, NOW)
    core.create_task(store, title="Pay rent", source="owner", deadline=FRIDAY_5PM)
    fixed_times(monkeypatch, *moments)


def once(store: Store, action: str, key: str, request: dict, task_id: str = "t1", **fields):
    values: dict[str, object] = {"client": "agent", "key": key, "request": request}
    values.update(fields)
    return core.change_state_once(store, task_id, action, **values)


def pending(store: Store) -> list[str]:
    return [r.kind for r in store.reminders("t1") if r.voided_at is None and r.sent_at is None]


@pytest.mark.xfail(strict=True, reason=MARK)
def test_a_keyed_done_changes_the_task_once_and_keeps_its_key(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    seeded(store, monkeypatch, LATER, LAST)
    first = once(store, "done", "run-1:step-2", DONE)
    assert (first.task.state, first.task.updated_at, first.changed) == ("done", AT_LATER, True)
    found = store.request_key("agent", "run-1:step-2")
    assert found is not None
    assert (found.request, found.task_id, found.link_id, found.created_at) == (
        DONE,
        "t1",
        None,
        AT_LATER,
    )
    assert [(e.action, e.actor, e.before, e.after) for e in store.audit("t1")][1:] == [
        ("done", "agent", {"state": "open"}, {"state": "done"})
    ]
    assert pending(store) == []
    again = once(store, "done", "run-1:step-2", DONE)
    assert (again.task.state, again.task.updated_at, again.changed) == ("done", AT_LATER, False)
    assert len(store.audit("t1")) == 2


@pytest.mark.xfail(strict=True, reason=MARK)
def test_a_retried_step_changes_nothing_after_the_owner_reopens(
    store: Store, path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seeded(store, monkeypatch, LATER, LAST, LAST)
    once(store, "cancel", "run-1:step-2", CANCEL)
    core.change_state(store, "t1", "reopen", actor="owner")
    before = dump(path)
    again = once(store, "cancel", "run-1:step-2", CANCEL)
    assert (again.task.state, again.changed) == ("open", False)
    assert dump(path) == before


@pytest.mark.xfail(strict=True, reason=MARK)
def test_a_new_key_on_a_finished_task_is_no_change_and_is_kept(
    store: Store, path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seeded(store, monkeypatch, LATER, LAST, LAST)
    once(store, "done", "run-1:step-2", DONE)
    outcome = once(store, "done", "run-2:step-1", DONE)
    assert (outcome.task.state, outcome.task.updated_at, outcome.changed) == (
        "done",
        AT_LATER,
        False,
    )
    assert len(store.audit("t1")) == 2
    found = store.request_key("agent", "run-2:step-1")
    assert found is not None
    assert (found.request, found.task_id) == (DONE, "t1")
    before = dump(path)
    assert once(store, "done", "run-2:step-1", DONE).changed is False
    assert dump(path) == before


@pytest.mark.xfail(strict=True, reason=MARK)
@pytest.mark.parametrize(
    ("key", "request_body"),
    [
        ("run-1:step-2", CANCEL),
        ("run-1:step-2", {"tool": "complete_task", "id": "t2"}),
        ("run-0:step-1", DONE),
    ],
    ids=["other-action", "other-task", "a-create-key"],
)
def test_a_key_used_for_another_request_is_refused_and_writes_nothing(
    store: Store, path: Path, monkeypatch: pytest.MonkeyPatch, key: str, request_body: dict
) -> None:
    seeded(store, monkeypatch, NOW, LATER, LAST, LAST)
    core.create_task(store, title="Call the bank", source="owner")
    core.create_task_once(
        store,
        client="agent",
        key="run-0:step-1",
        request={"tool": "create_task", "title": "Book a dentist", "deadline": None},
        title="Book a dentist",
        source="agent",
    )
    once(store, "done", "run-1:step-2", DONE)
    before = dump(path)
    action = "cancel" if request_body is CANCEL else "done"
    task_id = str(request_body["id"])
    refused("key_reused", lambda: once(store, action, key, request_body, task_id=task_id))
    assert dump(path) == before


@pytest.mark.xfail(strict=True, reason=MARK)
@pytest.mark.parametrize(
    ("fields", "code"),
    [
        ({"client": "conductor"}, "invalid_client"),
        ({"client": None}, "invalid_client"),
        ({"key": ""}, "invalid_key"),
        ({"key": "k" * 201}, "invalid_key"),
        ({"key": 7}, "invalid_key"),
    ],
    ids=["unknown-client", "no-client", "empty-key", "long-key", "number-key"],
)
def test_a_bad_client_or_key_is_refused_before_the_clock(
    store: Store, path: Path, monkeypatch: pytest.MonkeyPatch, fields: dict, code: str
) -> None:
    seeded(store, monkeypatch)
    before = dump(path)
    values: dict[str, object] = {"client": "agent", "key": "run-1:step-2", "request": DONE}
    values.update(fields)
    refused(code, lambda: core.change_state_once(store, "t1", "done", **values))
    assert dump(path) == before


@pytest.mark.xfail(strict=True, reason=MARK)
def test_a_bad_action_is_refused_first(store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    seeded(store, monkeypatch)
    refused("invalid_action", lambda: once(store, "finish", "", DONE, client="conductor"))


@pytest.mark.xfail(strict=True, reason=MARK)
def test_an_unknown_or_ended_task_keeps_the_key_free(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    seeded(store, monkeypatch, LATER, LAST, LAST, LAST)
    missing = {"tool": "complete_task", "id": "t99"}
    refused("unknown_task", lambda: once(store, "done", "run-1:step-1", missing, task_id="t99"))
    assert store.request_key("agent", "run-1:step-1") is None
    once(store, "done", "run-1:step-2", DONE)
    refused("task_ended", lambda: once(store, "cancel", "run-1:step-3", CANCEL))
    assert store.request_key("agent", "run-1:step-3") is None
    reopened = once(store, "reopen", "run-1:step-3", {"tool": "reopen", "id": "t1"})
    assert (reopened.task.state, reopened.changed) == ("open", True)
    assert pending(store) != []


@pytest.mark.xfail(strict=True, reason=MARK)
def test_keys_are_per_client(store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    seeded(store, monkeypatch, LATER, LAST)
    assert once(store, "start", "shared-key", {"tool": "start", "id": "t1"}).changed is True
    outcome = once(store, "done", "shared-key", DONE, client="email")
    assert (outcome.task.state, outcome.changed) == ("done", True)
    assert [(e.action, e.actor) for e in store.audit("t1")][1:] == [
        ("start", "agent"),
        ("done", "email"),
    ]
