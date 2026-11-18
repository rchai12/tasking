import ast
import inspect
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from docket import core
from docket import store as store_module
from docket.deadlines import Deadline, WorkTime
from docket.store import Store
from tests.support import fixed_times

NOW = "2026-11-17T14:00:00+00:00"
STAMP = "2026-11-17T14:00:00.000000+00:00"
REQUEST = {"z": None, "a": {"y": "雪", "x": True}}


def create(store: Store, keyed: bool, source: str = "agent", **fields):
    values = {"title": "Café 雪", "source": source, **fields}
    if keyed:
        return core.create_task_once(
            store, client=source, key="synthetic-create", request=REQUEST, **values
        ).task
    return core.create_task(store, **values)


def rows(path: Path, table: str):
    # Table names are fixed test inputs, never a request or configuration value.
    with sqlite3.connect(path) as connection:
        return connection.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()


@pytest.mark.parametrize(
    ("keyed", "source", "actor"),
    [
        (False, "owner", "owner"),
        (False, "proposal", "owner"),
        (False, "agent", "agent"),
        (True, "agent", "agent"),
        (False, "email", "email"),
        (True, "email", "email"),
    ],
    ids=["owner", "proposal", "agent", "keyed-agent", "email", "keyed-email"],
)
def test_both_paths_keep_literal_task_and_audit_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, keyed: bool, source: str, actor: str
) -> None:
    fixed_times(monkeypatch, NOW)
    path = tmp_path / "docket.sqlite3"
    reference = {}
    provider = message = link = None
    if source == "email":
        reference = {
            "provider": "gmail",
            "message_id": "synthetic/雪",
            "link": "https://mail.example/雪",
        }
        provider, message, link = "gmail", "synthetic/雪", "https://mail.example/雪"
    with Store(path) as store:
        task = create(store, keyed, source, **reference)
        assert (task.id, task.title, task.state) == ("t1", "Café 雪", "open")
        audit = store.audit("t1")
        assert len(audit) == 1
        assert (audit[0].action, audit[0].actor, audit[0].before, audit[0].after) == (
            "create",
            actor,
            {},
            {
                "title": "Café 雪",
                "state": "open",
                "deadline": None,
                "work": None,
                "source": source,
                "provider": provider,
                "message_id": message,
                "link": link,
            },
        )
    assert rows(path, "tasks") == [
        (
            1,
            "Café 雪",
            "open",
            None,
            None,
            None,
            None,
            None,
            None,
            source,
            provider,
            message,
            link,
            STAMP,
            STAMP,
        )
    ]
    assert [(row[0:6]) for row in rows(path, "audit_log")] == [(1, 1, STAMP, "create", actor, "{}")]
    if keyed:
        assert rows(path, "request_keys") == [
            (source, "synthetic-create", '{"a":{"x":true,"y":"雪"},"z":null}', 1, None, STAMP)
        ]
    else:
        assert rows(path, "request_keys") == []


@pytest.mark.parametrize("keyed", [False, True], ids=["plain", "keyed"])
def test_time_snapshots_keep_exact_instants_and_shapes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, keyed: bool
) -> None:
    fixed_times(monkeypatch, NOW)
    path = tmp_path / "docket.sqlite3"
    with Store(path) as store:
        create(
            store,
            keyed,
            deadline=Deadline(datetime(2026, 11, 20, 22, tzinfo=UTC), "America/New_York", False),
            work=WorkTime(datetime(2026, 11, 20, 20, tzinfo=UTC), 30, "America/New_York"),
        )
    assert rows(path, "audit_log") == [
        (
            1,
            1,
            STAMP,
            "create",
            "agent",
            "{}",
            '{"deadline":{"at":"2026-11-20T22:00:00.000000+00:00",'
            '"time_given":false,"zone":"America/New_York"},"link":null,"message_id":null,'
            '"provider":null,"source":"agent","state":"open","title":"Café 雪",'
            '"work":{"minutes":30,"start":"2026-11-20T20:00:00.000000+00:00",'
            '"zone":"America/New_York"}}',
        )
    ]


class InjectedWriteFailure(Exception):
    pass


@pytest.mark.parametrize(
    ("keyed", "method"),
    [
        (False, "insert_task"),
        (False, "append_audit"),
        (True, "insert_task"),
        (True, "append_audit"),
        (True, "insert_request_key"),
    ],
    ids=["plain-task", "plain-audit", "keyed-task", "keyed-audit", "keyed-key"],
)
def test_each_partial_create_rolls_back_every_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, keyed: bool, method: str
) -> None:
    fixed_times(monkeypatch, NOW, NOW)
    path = tmp_path / "docket.sqlite3"
    original = getattr(Store, method)

    def fail_after_write(self, *args, **kwargs):
        original(self, *args, **kwargs)
        raise InjectedWriteFailure

    with Store(path) as store:
        with monkeypatch.context() as patch:
            patch.setattr(Store, method, fail_after_write)
            with pytest.raises(InjectedWriteFailure):
                create(store, keyed)
        for table in ("tasks", "audit_log", "request_keys"):
            assert rows(path, table) == []
        assert create(store, keyed).id == "t1"
    assert len(rows(path, "tasks")) == len(rows(path, "audit_log")) == 1


def test_replays_compare_canonical_json_and_return_current_task_without_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_times(monkeypatch, NOW, NOW, NOW, NOW, NOW)
    path = tmp_path / "docket.sqlite3"
    with Store(path) as store:
        create(store, True)
        core.change_state(store, "t1", "done", actor="owner")
        before = {table: rows(path, table) for table in ("tasks", "audit_log", "request_keys")}
        reordered = {"a": {"x": True, "y": "雪"}, "z": None}
        outcome = core.create_task_once(
            store,
            client="agent",
            key="synthetic-create",
            request=reordered,
            title="Café 雪",
            source="agent",
        )
        assert (outcome.task.id, outcome.task.state, outcome.changed) == ("t1", "done", False)
        for changed in ({"a": {"x": 1, "y": "雪"}, "z": None}, {"a": {"x": True, "y": "雪"}}):
            with pytest.raises(core.CoreError, match="^key_reused$"):
                core.create_task_once(
                    store,
                    client="agent",
                    key="synthetic-create",
                    request=changed,
                    title="Café 雪",
                    source="agent",
                )
        assert {table: rows(path, table) for table in before} == before


def test_core_and_store_route_all_json_writes_through_the_shared_module(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from docket import serialization

    fixed_times(monkeypatch, NOW, NOW, NOW, NOW)
    original = serialization.canonical_json
    calls = []

    def trace(value):
        calls.append(value)
        return original(value)

    monkeypatch.setattr(serialization, "canonical_json", trace)
    with Store(tmp_path / "docket.sqlite3") as store:
        create(store, True)
        assert len(calls) == 3  # before, after, saved request
        calls.clear()
        create(store, True)
        assert calls == [REQUEST, REQUEST]  # loaded and incoming comparison
        calls.clear()
        fields = {
            "provider": "gmail",
            "message_id": "synthetic/2",
            "link": "https://mail.example/2",
        }
        core.add_link(store, "t1", client="email", key="synthetic-link", request=fields, **fields)
        assert calls == [fields]
        calls.clear()
        core.add_link(store, "t1", client="email", key="synthetic-link", request=fields, **fields)
        assert calls == [fields, fields]


def test_creation_has_one_private_insertion_and_audit_path() -> None:
    tree = ast.parse(inspect.getsource(core))
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    inserters = [
        name
        for name, node in functions.items()
        if any(
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == "insert_task"
            for call in ast.walk(node)
        )
    ]
    assert len(inserters) == 1
    helper = inserters[0]
    assert helper.startswith("_")
    for name in ("create_task", "create_task_once"):
        assert any(
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id == helper
            for call in ast.walk(functions[name])
        )
    calls = [
        call.func.attr
        for call in ast.walk(functions[helper])
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
    ]
    assert calls.count("append_audit") == 1
    assert "transaction" not in calls
    assert "now" not in calls
    for module in (core, store_module):
        assert "json.dumps" not in inspect.getsource(module)
