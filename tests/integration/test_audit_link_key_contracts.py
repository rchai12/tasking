import inspect
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from docket import _store_audit, _store_keys, _store_links, core, serialization
from docket.store import Store, StoreError
from tests.reference_cases import BODY, version_two
from tests.store_boundary_cases import InjectedSqlFailure, record_connections
from tests.support import fixed_times

NOW = "2026-11-17T14:00:00+00:00"
AT = datetime(2026, 11, 17, 14, tzinfo=UTC)
OFF = datetime(2026, 11, 17, 9, tzinfo=timezone(timedelta(hours=-5)))
KEY = "synthetic'key"
REQUEST = {"note": "a'b", "nested": {"q": "雪"}}
OTHER = {"note": "other"}


def _table_functions() -> list[tuple[object, str, object]]:
    found = []
    for module in (_store_audit, _store_links, _store_keys):
        for name, function in inspect.getmembers(module, inspect.isfunction):
            parameters = list(inspect.signature(function).parameters)
            if parameters and parameters[0] == "connection":
                found.append((module, name, function))
    return found


def _insert_task(store: Store, title: str = "Synthetic task"):
    return store.insert_task(
        title=title,
        state="open",
        deadline=None,
        work=None,
        source="owner",
        provider=None,
        message_id=None,
        link=None,
        at=AT,
    )


def test_non_utc_link_and_key_writes_stop_before_lookup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[str] = []

    def forbidden(*_args, **_kwargs):
        seen.append("called")
        raise AssertionError("table helper called")

    originals = _table_functions()
    for module, name, _function in originals:
        monkeypatch.setattr(module, name, forbidden)
    with Store(tmp_path / "docket.sqlite3") as store:
        with store.transaction():
            for call in (
                lambda: store.insert_link(
                    "t99", provider="gmail", message_id="synthetic", link="synthetic", at=OFF
                ),
                lambda: store.insert_request_key(
                    client="email",
                    key="synthetic",
                    request={},
                    task_id="t99",
                    link_id="l99",
                    at=OFF,
                ),
            ):
                with pytest.raises(StoreError, match="^an instant must be in UTC$"):
                    call()
        assert seen == []
        for module, name, function in originals:
            monkeypatch.setattr(module, name, function)
        looked: list[int] = []
        original = _store_links.select_existence

        def watch(connection, number: int):
            looked.append(number)
            return original(connection, number)

        monkeypatch.setattr(_store_links, "select_existence", watch)
        with store.transaction():
            with pytest.raises(StoreError, match="^unknown task$"):
                store.insert_link(
                    "t99", provider="gmail", message_id="synthetic", link="synthetic", at=AT
                )
            with pytest.raises(StoreError, match="^unknown task$"):
                store.insert_request_key(
                    client="email",
                    key="synthetic",
                    request={},
                    task_id="t99",
                    link_id="l99",
                    at=AT,
                )
            assert looked == []
            made = _insert_task(store)
            with pytest.raises(StoreError, match="^unknown link$"):
                store.insert_request_key(
                    client="email",
                    key="synthetic",
                    request={},
                    task_id=made.id,
                    link_id="l99",
                    at=AT,
                )
            with pytest.raises(StoreError, match="^unknown link$"):
                store.insert_request_key(
                    client="email",
                    key="synthetic",
                    request={},
                    task_id=made.id,
                    link_id="l0",
                    at=AT,
                )
            assert looked == [99]
            assert store.tasks() == [made]


def test_quote_key_and_nested_request_round_trip_and_conflicts_write_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_times(monkeypatch, *([NOW] * 9))
    path = tmp_path / "docket.sqlite3"
    with Store(path) as store:
        made = core.create_task_once(
            store,
            client="agent",
            key=KEY,
            request=REQUEST,
            title="Synthetic ' task",
            source="agent",
        )
        assert made.changed is True
        again = core.create_task_once(
            store,
            client="agent",
            key=KEY,
            request=REQUEST,
            title="Synthetic ' task",
            source="agent",
        )
        assert (again.changed, again.task.id) == (False, made.task.id)
        before = (store.tasks(), store.audit(made.task.id), store.request_key("agent", KEY))
        with pytest.raises(core.CoreError, match="^key_reused$"):
            core.create_task_once(
                store,
                client="agent",
                key=KEY,
                request=OTHER,
                title="Synthetic ' task",
                source="agent",
            )
        assert (store.tasks(), store.audit(made.task.id), store.request_key("agent", KEY)) == before
        mailed = core.create_task_once(
            store,
            client="email",
            key=KEY,
            request=REQUEST,
            title="Synthetic email",
            source="email",
            provider="gmail",
            message_id="synthetic/'1",
            link="https://mail.example/'1",
        )
        assert mailed.changed is True and mailed.task.id != made.task.id
        replayed = core.create_task_once(
            store,
            client="email",
            key=KEY,
            request=REQUEST,
            title="Synthetic email",
            source="email",
            provider="gmail",
            message_id="synthetic/'1",
            link="https://mail.example/'1",
        )
        assert (replayed.changed, replayed.task.id) == (False, mailed.task.id)
        with pytest.raises(core.CoreError, match="^key_reused$"):
            core.create_task_once(
                store,
                client="email",
                key=KEY,
                request=OTHER,
                title="Synthetic email",
                source="email",
                provider="gmail",
                message_id="synthetic/'1",
                link="https://mail.example/'1",
            )
        linked = core.add_link(
            store,
            made.task.id,
            client="email",
            key="link'key",
            request=REQUEST,
            provider="gmail",
            message_id="synthetic/'2",
            link="https://mail.example/'2",
        )
        assert linked.changed is True
        same_link = core.add_link(
            store,
            made.task.id,
            client="email",
            key="link'key",
            request=REQUEST,
            provider="gmail",
            message_id="synthetic/'2",
            link="https://mail.example/'2",
        )
        assert (same_link.changed, same_link.link.id) == (False, linked.link.id)
        held = (store.links(made.task.id), store.request_key("email", "link'key"))
        with pytest.raises(core.CoreError, match="^key_reused$"):
            core.add_link(
                store,
                made.task.id,
                client="email",
                key="link'key",
                request=OTHER,
                provider="gmail",
                message_id="synthetic/'2",
                link="https://mail.example/'2",
            )
        assert (store.links(made.task.id), store.request_key("email", "link'key")) == held
        assert len(store.tasks()) == 2
    with Store(path) as store:
        agent = store.request_key("agent", KEY)
        email = store.request_key("email", KEY)
        assert agent is not None and email is not None
        assert agent.request == REQUEST and email.request == REQUEST
        assert agent.task_id != email.task_id
        assert agent.link_id is None
        assert store.request_key("agent", "synthetic") is None
        assert store.request_key("email", "synthetic") is None
        raw = store._connection.execute(
            "SELECT request FROM request_keys WHERE client = ? AND key = ?",
            ("agent", KEY),
        ).fetchone()
        assert raw["request"] == serialization.canonical_json(REQUEST)


def test_a_helper_failure_before_sql_rolls_the_transaction_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_before_sql(_connection, *_args, **_kwargs):
        raise InjectedSqlFailure

    monkeypatch.setattr(_store_keys, "insert_request_key", fail_before_sql)
    with Store(tmp_path / "docket.sqlite3") as store:
        with pytest.raises(InjectedSqlFailure):
            with store.transaction():
                made = _insert_task(store)
                store.append_audit(
                    made.id, at=AT, action="create", actor="owner", before={}, after={}
                )
                store.insert_request_key(
                    client="agent",
                    key="synthetic",
                    request=REQUEST,
                    task_id=made.id,
                    link_id=None,
                    at=AT,
                )
        assert store._in_transaction is False
        assert store.tasks() == []
        assert store.audit("t1") == []
        assert store.request_key("agent", "synthetic") is None
        with store.transaction():
            retried = _insert_task(store)
        assert retried.id == "t1"
        assert [item.id for item in store.tasks()] == ["t1"]


def test_extracted_reads_cover_empty_rows_and_both_key_targets(tmp_path: Path) -> None:
    with Store(tmp_path / "docket.sqlite3") as store:
        with store.transaction():
            made = _insert_task(store)
            other = _insert_task(store, "Synthetic other")
        assert store.audit(made.id) == []
        assert store.links(made.id) == []
        assert store.links(other.id) == []
        assert store.request_key("agent", "task'key") is None
        with store.transaction():
            made_link = store.insert_link(
                made.id,
                provider="gmail",
                message_id="synthetic/'1",
                link="https://mail.example/'1",
                at=AT,
            )
            store.insert_request_key(
                client="agent",
                key="task'key",
                request=REQUEST,
                task_id=made.id,
                link_id=None,
                at=AT,
            )
            store.insert_request_key(
                client="email",
                key="link'key",
                request=REQUEST,
                task_id=made.id,
                link_id=made_link.id,
                at=AT,
            )
        assert (made_link.id, made_link.task_id, made_link.message_id) == (
            "l1",
            "t1",
            "synthetic/'1",
        )
        assert [item.id for item in store.links("t1")] == ["l1"]
        assert store.links("t2") == []
        task_key = store.request_key("agent", "task'key")
        link_key = store.request_key("email", "link'key")
        assert task_key is not None and link_key is not None
        assert (task_key.task_id, task_key.link_id, task_key.request) == ("t1", None, REQUEST)
        assert (link_key.task_id, link_key.link_id, link_key.request) == ("t1", "l1", REQUEST)
        assert store.request_key("email", "task'key") is None
        assert store.audit("t99") == []
        assert store.links("t1' OR 1=1 --") == []


def test_legacy_reference_upgrade_keeps_the_store_preflight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "docket.sqlite3"
    version_two(path)
    opened = record_connections(monkeypatch)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("table helper called during startup")

    originals = _table_functions()
    for module, name, _function in originals:
        monkeypatch.setattr(module, name, forbidden)
    with Store(path) as store:
        for module, name, function in originals:
            monkeypatch.setattr(module, name, function)
        assert len(opened) == 1
        connection = opened[0]
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 6
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
        assert str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower() == "wal"
        assert [item.message_id for item in store.links("t1")] == ["synthetic/2"]
        assert store.audit("t1")[0].after == {"title": "Synthetic reference task"}
        task_key = store.request_key("email", "task-key")
        link_key = store.request_key("email", "link-key")
        assert task_key is not None and link_key is not None
        assert (task_key.task_id, task_key.link_id, task_key.request) == ("t1", None, BODY)
        assert link_key.link_id == "l1"
        assert len(opened) == 1
