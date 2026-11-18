import ast
import importlib
import inspect
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

from docket import core
from docket import store as store_module
from docket.store import UNCHANGED, AuditEntry, Link, RequestKey, Store, StoreError, Task
from tests.store_boundary_cases import (
    TABLE_MODULES,
    InjectedSqlFailure,
    add_email,
    create_agent,
    record_connections,
    snapshot,
)
from tests.support import fixed_times

NOW = "2026-11-17T14:00:00+00:00"
AT = datetime(2026, 11, 17, 14, tzinfo=UTC)
STAMP = "2026-11-17T14:00:00.000000+00:00"


@pytest.mark.parametrize("table", ["audit_log", "links", "request_keys"])
def test_table_modules_are_sql_only_and_use_the_supplied_connection(table: str) -> None:
    module = importlib.import_module(TABLE_MODULES[table])
    tree = ast.parse(inspect.getsource(module))
    entry_points = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.args.args
        and node.args.args[0].arg == "connection"
    ]
    assert entry_points, "SQL entry points take connection as their first positional argument"
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in {
                "connect",
                "commit",
                "rollback",
                "close",
                "cursor",
                "executescript",
                "now",
            }
        if isinstance(node, ast.ImportFrom):
            assert node.module != "docket" and not (node.module or "").startswith("docket.")
        if isinstance(node, ast.Import):
            assert all(
                name.name != "docket" and not name.name.startswith("docket.") for name in node.names
            )
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "execute"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            assert (
                re.match(r"\s*(BEGIN|COMMIT|ROLLBACK|PRAGMA)\b", node.args[0].value, re.I) is None
            )


def test_normal_table_sql_runs_in_its_table_module_on_one_connection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened = record_connections(monkeypatch)
    fixed_times(monkeypatch, NOW, NOW, NOW, NOW)
    with Store(tmp_path / "docket.sqlite3") as store:
        connection = opened[0]
        connection.recording = True
        assert create_agent(store).changed
        assert add_email(store).changed
        assert not create_agent(store).changed
        assert not add_email(store).changed
        assert len(store.audit("t1")) == len(store.links("t1")) == 1
        assert len(opened) == 1
        assert set(table for table, _, _ in connection.events) == {
            "audit_log",
            "links",
            "request_keys",
        }
        for table, caller, _ in connection.events:
            assert caller == TABLE_MODULES[table], (
                f"{table} SQL belongs to {TABLE_MODULES[table]}; got {caller}"
            )
        assert any(table == "links" and writing for table, _, writing in connection.events)
        assert any(table == "request_keys" and writing for table, _, writing in connection.events)


def test_facade_keeps_literal_records_json_and_per_client_keys_after_reopen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened = record_connections(monkeypatch)
    fixed_times(monkeypatch, NOW, NOW)
    path = tmp_path / "docket.sqlite3"
    with Store(path) as store:
        create_agent(store)
        add_email(store)
        with store.transaction():
            store.insert_request_key(
                client="email",
                key="synthetic-create",
                request={"same": "key"},
                task_id="t1",
                link_id="l1",
                at=AT,
            )
        raw = snapshot(opened[0])
        assert raw["audit_log"] == [
            (
                1,
                1,
                STAMP,
                "create",
                "agent",
                "{}",
                '{"deadline":null,"link":null,"message_id":null,"provider":null,'
                '"source":"agent","state":"open","title":"Synthetic \' task","work":null}',
            )
        ]
        assert raw["links"] == [(1, 1, "gmail", "synthetic/'1", "https://mail.example/'1", STAMP)]
        assert raw["request_keys"] == [
            ("agent", "synthetic-create", '{"a":"雪","z":null}', 1, None, STAMP),
            ("email", "synthetic-create", '{"same":"key"}', 1, 1, STAMP),
            ("email", "synthetic-link", '{"a":"雪","z":null}', 1, 1, STAMP),
        ]
    with Store(path) as store:
        assert store.links("t1") == [
            Link(
                id="l1",
                task_id="t1",
                provider="gmail",
                message_id="synthetic/'1",
                link="https://mail.example/'1",
                created_at=AT,
            )
        ]
        assert store.request_key("agent", "synthetic-create") == RequestKey(
            client="agent",
            key="synthetic-create",
            request={"a": "雪", "z": None},
            task_id="t1",
            link_id=None,
            created_at=AT,
        )
        assert store.audit("t1") == [
            AuditEntry(
                task_id="t1",
                at=AT,
                action="create",
                actor="agent",
                before={},
                after={
                    "title": "Synthetic ' task",
                    "state": "open",
                    "deadline": None,
                    "work": None,
                    "source": "agent",
                    "provider": None,
                    "message_id": None,
                    "link": None,
                },
            )
        ]
        assert snapshot(opened[1]) == raw


@pytest.mark.parametrize(
    ("operation", "table"),
    [
        ("create", "audit_log"),
        ("create", "request_keys"),
        ("link", "links"),
        ("link", "request_keys"),
    ],
    ids=["create-after-audit", "create-after-key", "link-after-link", "link-after-key"],
)
def test_sql_failure_rolls_back_all_tables_and_sequences_together(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str, table: str
) -> None:
    opened = record_connections(monkeypatch)
    fixed_times(monkeypatch, NOW, NOW, NOW)
    with Store(tmp_path / "docket.sqlite3") as store:
        if operation == "link":
            create_agent(store)
        connection = opened[0]
        before = snapshot(connection)
        connection.recording = True
        connection.interrupt_table = table
        call = create_agent if operation == "create" else add_email
        with pytest.raises(InjectedSqlFailure):
            call(store)
        connection.interrupt_table = None
        assert snapshot(connection) == before
        result = call(store)
        assert result.changed
        if operation == "create":
            assert result.task.id == "t1"
            assert len(store.audit("t1")) == 1
        else:
            assert result.link.id == "l1"
            assert len(store.links("t1")) == len(store.audit("t1")) == 1
        assert len(opened) == 1


@pytest.mark.parametrize("operation", ["audit", "link", "key"])
def test_facade_refuses_writes_before_any_table_helper_is_called(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    modules = [importlib.import_module(name) for name in TABLE_MODULES.values()]

    def forbidden(*_args, **_kwargs):
        raise AssertionError("an unguarded write reached a table helper")

    with Store(tmp_path / "docket.sqlite3") as store:
        for module in modules:
            for name, function in inspect.getmembers(module, inspect.isfunction):
                parameters = list(inspect.signature(function).parameters)
                if parameters and parameters[0] == "connection":
                    monkeypatch.setattr(module, name, forbidden)
        with pytest.raises(StoreError, match="^a write needs a transaction$"):
            if operation == "audit":
                store.append_audit(
                    "t99", at=AT, action="create", actor="owner", before={}, after={}
                )
            elif operation == "link":
                store.insert_link(
                    "t99", at=AT, provider="gmail", message_id="synthetic", link="synthetic"
                )
            else:
                store.insert_request_key(
                    client="email", key="synthetic", request={}, task_id="t99", link_id=None, at=AT
                )


def test_nested_transaction_refusal_does_not_end_the_outer_transaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_times(monkeypatch, NOW)
    with Store(tmp_path / "docket.sqlite3") as store:
        with store.transaction():
            with pytest.raises(StoreError, match="^a transaction is already open$"):
                with store.transaction():
                    pytest.fail("nested transaction entered")
            task = store.insert_task(
                title="Synthetic task",
                state="open",
                deadline=None,
                work=None,
                source="owner",
                provider=None,
                message_id=None,
                link=None,
                at=AT,
            )
            store.append_audit(task.id, at=AT, action="create", actor="owner", before={}, after={})
            store.insert_link(
                task.id, at=AT, provider="gmail", message_id="synthetic", link="synthetic"
            )
        assert len(store.tasks()) == len(store.audit("t1")) == len(store.links("t1")) == 1


@pytest.mark.parametrize("operation", ["task-delete", "audit-update", "audit-delete"])
def test_table_refactor_keeps_sql_immutability_triggers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    import sqlite3

    opened = record_connections(monkeypatch)
    fixed_times(monkeypatch, NOW)
    with Store(tmp_path / "docket.sqlite3") as store:
        create_agent(store)
        before = snapshot(opened[0])
        command = {
            "task-delete": "DELETE FROM tasks WHERE number = 1",
            "audit-update": "UPDATE audit_log SET actor = 'owner' WHERE number = 1",
            "audit-delete": "DELETE FROM audit_log WHERE number = 1",
        }[operation]
        with pytest.raises(sqlite3.IntegrityError):
            with store.transaction():
                opened[0].execute(command)
        assert snapshot(opened[0]) == before


def test_public_records_sentinel_and_error_remain_owned_by_store() -> None:
    for value in (Task, AuditEntry, Link, RequestKey, StoreError):
        assert value.__module__ == "docket.store"
    assert inspect.signature(Store.update_task).parameters["title"].default is UNCHANGED
    assert core.UNCHANGED is store_module.UNCHANGED


def test_reads_keep_task_filtering_order_and_missing_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_times(monkeypatch, NOW, NOW)
    with Store(tmp_path / "docket.sqlite3") as store:
        core.create_task(store, title="Synthetic one", source="owner")
        core.create_task(store, title="Synthetic two", source="owner")
        with store.transaction():
            for task_id, provider in (("t1", "gmail"), ("t2", "outlook"), ("t1", "yahoo")):
                store.insert_link(
                    task_id, at=AT, provider=provider, message_id="synthetic", link="synthetic"
                )
            store.append_audit("t1", at=AT, action="retitle", actor="owner", before={}, after={})
        assert [item.id for item in store.links("t1")] == ["l1", "l3"]
        assert [item.id for item in store.links("t2")] == ["l2"]
        assert [item.action for item in store.audit("t1")] == ["create", "retitle"]
        assert [item.action for item in store.audit("t2")] == ["create"]
        for missing in ("t99", "t0", "T1", "t1' OR 1=1 --"):
            assert store.links(missing) == []
            assert store.audit(missing) == []
        assert store.request_key("agent", "missing") is None
