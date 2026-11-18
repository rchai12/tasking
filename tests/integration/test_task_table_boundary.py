import ast
import importlib
import inspect
import re
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from docket import core
from docket.deadlines import Deadline, WorkTime
from docket.store import Store, StoreError
from tests.store_boundary_cases import InjectedSqlFailure, add_email, create_agent, snapshot
from tests.support import fixed_times
from tests.task_boundary_cases import ALL_TABLE_MODULES, record_task_connections

NOW = "2026-11-17T14:00:00+00:00"
AT = datetime(2026, 11, 17, 14, tzinfo=UTC)
LATER = datetime(2026, 11, 17, 15, tzinfo=UTC)
DUE = Deadline(datetime(2026, 11, 1, 22, tzinfo=UTC), "America/New_York", False)
WORK = WorkTime(datetime(2026, 11, 1, 21, tzinfo=UTC), 30, "America/New_York")


def test_task_module_is_sql_only_on_the_supplied_connection() -> None:
    module = importlib.import_module("docket._store_tasks")
    tree = ast.parse(inspect.getsource(module))
    assert any(
        isinstance(node, ast.FunctionDef)
        and node.args.args
        and node.args.args[0].arg == "connection"
        for node in tree.body
    )
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.module != "docket" and not (node.module or "").startswith("docket.")
        if isinstance(node, ast.Import):
            assert all(not name.name.startswith("docket") for name in node.names)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in {
                "connect",
                "close",
                "commit",
                "rollback",
                "cursor",
                "executescript",
                "now",
                "fromisoformat",
                "dumps",
                "loads",
            }
            if (
                node.func.attr == "execute"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                assert (
                    re.match(r"\s*(BEGIN|COMMIT|ROLLBACK|PRAGMA)\b", node.args[0].value, re.I)
                    is None
                )


@pytest.mark.parametrize("operation", ["insert", "update", "task", "tasks", "filtered", "exists"])
def test_ordinary_sql_for_all_tables_has_one_owner_and_connection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    opened = record_task_connections(monkeypatch)
    fixed_times(monkeypatch, NOW, NOW, NOW)
    with Store(tmp_path / "docket.sqlite3") as store:
        create_agent(store)
        add_email(store)
        connection = opened[0]
        connection.recording = True
        if operation == "insert":
            core.create_task(store, title="Synthetic two", source="owner")
        elif operation == "update":
            core.edit_task(store, "t1", actor="owner", title="Synthetic edit")
        elif operation == "task":
            assert store.task("t1") is not None
        elif operation == "tasks":
            assert len(store.tasks()) == 1
        elif operation == "filtered":
            assert len(store.tasks(("open",))) == 1
        else:
            with store.transaction():
                store.append_audit(
                    "t1", at=AT, action="retitle", actor="owner", before={}, after={}
                )
        assert len(opened) == 1
        assert any(table == "tasks" for table, _, _ in connection.events)
        for table, caller, _in_transaction in connection.events:
            assert caller == ALL_TABLE_MODULES[table], (
                f"{operation}: {table} SQL expected {ALL_TABLE_MODULES[table]}; actual {caller}"
            )


@pytest.mark.parametrize(
    ("case", "title", "state", "deadline", "work"),
    [
        (
            "unchanged",
            "Synthetic task",
            "open",
            ("2026-11-01T22:00:00.000000+00:00", "America/New_York", 0),
            ("2026-11-01T21:00:00.000000+00:00", 30, "America/New_York"),
        ),
        (
            "title",
            "Synthetic ' edit",
            "open",
            ("2026-11-01T22:00:00.000000+00:00", "America/New_York", 0),
            ("2026-11-01T21:00:00.000000+00:00", 30, "America/New_York"),
        ),
        (
            "state",
            "Synthetic task",
            "in_progress",
            ("2026-11-01T22:00:00.000000+00:00", "America/New_York", 0),
            ("2026-11-01T21:00:00.000000+00:00", 30, "America/New_York"),
        ),
        (
            "clear-deadline",
            "Synthetic task",
            "open",
            (None, None, None),
            ("2026-11-01T21:00:00.000000+00:00", 30, "America/New_York"),
        ),
        (
            "clear-work",
            "Synthetic task",
            "open",
            ("2026-11-01T22:00:00.000000+00:00", "America/New_York", 0),
            (None, None, None),
        ),
        ("clear-both", "Synthetic task", "open", (None, None, None), (None, None, None)),
        (
            "replace",
            "Synthetic task",
            "open",
            ("2027-03-14T21:00:00.000000+00:00", "America/New_York", 1),
            ("2027-03-14T20:00:00.000000+00:00", 45, "America/New_York"),
        ),
    ],
    ids=["unchanged", "title", "state", "clear-deadline", "clear-work", "clear-both", "replace"],
)
def test_update_keeps_unchanged_clear_and_replacement_values_literal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    title: str,
    state: str,
    deadline,
    work,
) -> None:
    opened = record_task_connections(monkeypatch)
    with Store(tmp_path / "docket.sqlite3") as store:
        with store.transaction():
            store.insert_task(
                title="Synthetic task",
                state="open",
                deadline=DUE,
                work=WORK,
                source="owner",
                provider=None,
                message_id=None,
                link=None,
                at=AT,
            )
            fields = {}
            if case == "title":
                fields["title"] = "Synthetic ' edit"
            elif case == "state":
                fields["state"] = "in_progress"
            elif case == "replace":
                fields["deadline"] = Deadline(
                    datetime(2027, 3, 14, 21, tzinfo=UTC), "America/New_York", True
                )
                fields["work"] = WorkTime(
                    datetime(2027, 3, 14, 20, tzinfo=UTC), 45, "America/New_York"
                )
            else:
                if case in {"clear-deadline", "clear-both"}:
                    fields["deadline"] = None
                if case in {"clear-work", "clear-both"}:
                    fields["work"] = None
            made = store.update_task("t1", at=LATER, **fields)
        assert (made.id, made.title, made.state, made.created_at, made.updated_at) == (
            "t1",
            title,
            state,
            AT,
            LATER,
        )
        assert snapshot(opened[0])["tasks"] == [
            (
                1,
                title,
                state,
                *deadline,
                *work,
                "owner",
                None,
                None,
                None,
                "2026-11-17T14:00:00.000000+00:00",
                "2026-11-17T15:00:00.000000+00:00",
            )
        ]


def test_filters_empty_and_missing_keep_their_exact_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened = record_task_connections(monkeypatch)
    with Store(tmp_path / "docket.sqlite3") as store:
        with store.transaction():
            for state in ("open", "done", "in_progress"):
                store.insert_task(
                    title="Synthetic task",
                    state=state,
                    deadline=None,
                    work=None,
                    source="owner",
                    provider=None,
                    message_id=None,
                    link=None,
                    at=AT,
                )
        assert [task.id for task in store.tasks()] == ["t1", "t2", "t3"]
        assert [task.id for task in store.tasks(("in_progress", "open"))] == ["t1", "t3"]
        assert store.tasks(()) == []
        assert store.tasks(("missing",)) == []
        assert store.tasks(("open' OR 1=1 --",)) == []
        for task_id in ("t99", "t0", "T1", "t1' OR 1=1 --"):
            assert store.task(task_id) is None
        assert len(opened) == 1


@pytest.mark.parametrize("operation", ["insert", "update"])
def test_failure_after_task_sql_rolls_back_rows_audit_keys_and_sequences(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    opened = record_task_connections(monkeypatch)
    fixed_times(monkeypatch, NOW, NOW, NOW)
    with Store(tmp_path / "docket.sqlite3") as store:
        if operation == "update":
            create_agent(store)
        connection = opened[0]
        before = snapshot(connection)
        connection.recording = True
        connection.interrupt_task = operation

        def call():
            if operation == "insert":
                return create_agent(store)
            return core.edit_task(store, "t1", actor="owner", title="Synthetic edit")

        with pytest.raises(InjectedSqlFailure):
            call()
        connection.interrupt_task = None
        assert snapshot(connection) == before
        result = call()
        assert (result.task.id, result.changed) == ("t1", True)


@pytest.mark.parametrize("operation", ["insert", "update"])
@pytest.mark.parametrize("guard", ["outside", "naive", "equivalent-zone"])
def test_task_write_guards_run_before_any_sql_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str, guard: str
) -> None:
    module = importlib.import_module("docket._store_tasks")

    def forbidden(*_args, **_kwargs):
        raise AssertionError("unguarded task helper call")

    for name, function in inspect.getmembers(module, inspect.isfunction):
        if list(inspect.signature(function).parameters)[:1] == ["connection"]:
            monkeypatch.setattr(module, name, forbidden)
    at = AT
    if guard == "naive":
        at = datetime(2026, 11, 17, 14)
    elif guard == "equivalent-zone":
        at = datetime(2026, 11, 17, 14, tzinfo=ZoneInfo("UTC"))

    def call(store):
        if operation == "update":
            return store.update_task("t99", at=at, title="Synthetic edit")
        return store.insert_task(
            title="Synthetic task",
            state="open",
            deadline=None,
            work=None,
            source="owner",
            provider=None,
            message_id=None,
            link=None,
            at=at,
        )

    with Store(tmp_path / "docket.sqlite3") as store:
        if guard == "outside":
            with pytest.raises(StoreError, match="^a write needs a transaction$"):
                call(store)
        else:
            with store.transaction():
                with pytest.raises(StoreError, match="^an instant must be in UTC$"):
                    call(store)


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("deadline_zone", "PRIVATE_SYNTHETIC"),
        ("created_at", "2026-11-17T14:00:00"),
        ("work_start", "invalid"),
    ],
    ids=["deadline-zone", "created-naive", "work-text"],
)
def test_corrupt_task_refusals_stay_at_the_facade_without_repair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, column: str, value: str
) -> None:
    opened = record_task_connections(monkeypatch)
    with Store(tmp_path / "docket.sqlite3") as store:
        with store.transaction():
            store.insert_task(
                title="Synthetic task",
                state="open",
                deadline=DUE,
                work=WORK,
                source="owner",
                provider=None,
                message_id=None,
                link=None,
                at=AT,
            )
        connection = opened[0]
        connection.execute(f"UPDATE tasks SET {column} = ? WHERE number = 1", (value,))
        before = snapshot(connection)
        for read in (lambda: store.task("t1"), store.tasks):
            with pytest.raises(StoreError) as raised:
                read()
            assert str(raised.value) == "invalid stored task time: t1"
            assert raised.value.__cause__ is None and raised.value.__suppress_context__
        assert snapshot(connection) == before
