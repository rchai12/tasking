import inspect
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from docket import _store_tasks, core
from docket.deadlines import Deadline, WorkTime
from docket.store import Store, StoreError
from tests.reference_cases import version_two
from tests.store_boundary_cases import InjectedSqlFailure
from tests.support import fixed_times
from tests.task_boundary_cases import record_task_connections

NOW = "2026-11-17T14:00:00+00:00"
AT = datetime(2026, 11, 17, 14, tzinfo=UTC)
LATER = datetime(2026, 11, 17, 15, tzinfo=UTC)
AFTER = datetime(2026, 11, 17, 16, tzinfo=UTC)
DUE = Deadline(datetime(2026, 11, 1, 22, tzinfo=UTC), "America/New_York", False)
WORK = WorkTime(datetime(2026, 11, 1, 21, tzinfo=UTC), 30, "America/New_York")
REPLACEMENT = WorkTime(datetime(2027, 3, 14, 20, tzinfo=UTC), 45, "America/New_York")
TITLE = "Synthetic ' task"


def _insert(store: Store, **fields: object):
    values = {
        "title": "Synthetic task",
        "state": "open",
        "deadline": None,
        "work": None,
        "source": "owner",
        "provider": None,
        "message_id": None,
        "link": None,
        "at": AT,
    }
    values.update(fields)
    return store.insert_task(**values)


def test_one_update_combines_changes_clears_and_a_quoted_title(tmp_path: Path) -> None:
    with Store(tmp_path / "docket.sqlite3") as store:
        assert store.task("t1") is None
        assert store.tasks() == []
        assert store.tasks(()) == []
        with store.transaction():
            made = _insert(store, title=TITLE, deadline=DUE, work=WORK)
        assert (made.id, made.title, made.created_at, made.updated_at) == ("t1", TITLE, AT, AT)
        assert made.deadline == DUE and made.work == WORK
        with store.transaction():
            changed = store.update_task(
                "t1",
                at=LATER,
                title=TITLE,
                state="done",
                deadline=None,
                work=REPLACEMENT,
            )
        assert (changed.title, changed.state, changed.deadline, changed.work) == (
            TITLE,
            "done",
            None,
            REPLACEMENT,
        )
        assert (changed.created_at, changed.updated_at) == (AT, LATER)
        with store.transaction():
            cleared = store.update_task("t1", at=AFTER, work=None)
        assert (cleared.title, cleared.state, cleared.deadline, cleared.work) == (
            TITLE,
            "done",
            None,
            None,
        )
        assert (cleared.created_at, cleared.updated_at) == (AT, AFTER)
        assert [item.id for item in store.tasks()] == ["t1"]
        assert [item.title for item in store.tasks(("done",))] == [TITLE]
        assert store.tasks(("cancelled",)) == []
        assert store.tasks(("open",)) == []
        assert store.task("t99") is None


def test_only_a_well_formed_id_reaches_existence_sql(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[int] = []
    original = _store_tasks.select_existence

    def watch(connection, number: int):
        seen.append(number)
        return original(connection, number)

    monkeypatch.setattr(_store_tasks, "select_existence", watch)
    with Store(tmp_path / "docket.sqlite3") as store:
        with pytest.raises(StoreError, match="^a write needs a transaction$"):
            store.update_task("t99", at=AT, title=TITLE)
        with store.transaction():
            for at in (
                datetime(2026, 11, 17, 14),
                datetime(2026, 11, 17, 14, tzinfo=ZoneInfo("UTC")),
                datetime(2026, 11, 17, 9, tzinfo=timezone(timedelta(hours=-5))),
            ):
                with pytest.raises(StoreError, match="^an instant must be in UTC$"):
                    store.update_task("t99", at=at, title=TITLE)
        assert seen == []
        with store.transaction():
            for task_id in ("t0", "T1", "t1' OR 1=1 --"):
                with pytest.raises(StoreError, match="^unknown task$"):
                    store.update_task(task_id, at=AT, title=TITLE)
            assert seen == []
            with pytest.raises(StoreError, match="^unknown task$"):
                store.update_task("t99", at=AT, title=TITLE)
            assert seen == [99]


def test_a_helper_failure_before_sql_leaves_every_table_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_times(monkeypatch, NOW, NOW)

    def fail_before_sql(_connection, _values):
        raise InjectedSqlFailure

    original = _store_tasks.insert_task
    monkeypatch.setattr(_store_tasks, "insert_task", fail_before_sql)
    with Store(tmp_path / "docket.sqlite3") as store:
        with pytest.raises(InjectedSqlFailure) as raised:
            core.create_task_once(
                store,
                client="agent",
                key="synthetic",
                request={"a": "雪", "z": None},
                title="Synthetic task",
                source="agent",
            )
        assert type(raised.value) is InjectedSqlFailure
        assert raised.value.__cause__ is None
        assert store.tasks() == []
        assert store.audit("t1") == []
        assert store.request_key("agent", "synthetic") is None
        monkeypatch.setattr(_store_tasks, "insert_task", original)
        made = core.create_task_once(
            store,
            client="agent",
            key="synthetic",
            request={"a": "雪", "z": None},
            title="Synthetic task",
            source="agent",
        )
        assert (made.changed, made.task.id) == (True, "t1")
        assert len(store.audit("t1")) == 1
        assert store.request_key("agent", "synthetic") is not None


def test_legacy_upgrade_does_not_call_task_helpers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "docket.sqlite3"
    version_two(path)
    opened = record_task_connections(monkeypatch)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("task helper called during startup")

    originals = []
    for name, function in inspect.getmembers(_store_tasks, inspect.isfunction):
        if list(inspect.signature(function).parameters)[:1] == ["connection"]:
            originals.append((name, function))
            monkeypatch.setattr(_store_tasks, name, forbidden)
    with Store(path) as store:
        for name, function in originals:
            monkeypatch.setattr(_store_tasks, name, function)
        assert len(opened) == 1
        task = store.task("t1")
        assert task is not None
        assert (task.id, task.title, task.message_id) == (
            "t1",
            "Synthetic reference task",
            "synthetic/1",
        )
        assert [item.id for item in store.tasks()] == ["t1"]
        assert store.audit("t1")[0].actor == "email"
        assert [item.message_id for item in store.links("t1")] == ["synthetic/2"]
        task_key = store.request_key("email", "task-key")
        link_key = store.request_key("email", "link-key")
        assert task_key is not None and link_key is not None
        assert (task_key.task_id, task_key.link_id) == ("t1", None)
        assert link_key.link_id == "l1"
        assert len(opened) == 1
