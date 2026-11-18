import ast
import dataclasses
import importlib
import inspect
import re
import sqlite3
import sys
from datetime import datetime

import pytest

from docket import reminders
from docket.store import Store, StoreError
from tests.reminder_storage_cases import AT, NEXT


def test_reminder_kinds_have_one_domain_policy_and_the_same_typed_plan_contract() -> None:
    from typing import get_args

    from docket import domain

    assert domain.REMINDER_KINDS == ("start", "before", "due_soon", "due", "late")
    assert set(get_args(reminders.PlannedReminder.__annotations__["kind"])) == set(
        domain.REMINDER_KINDS
    )


def seed(opened: Store) -> None:
    with opened.transaction():
        opened.insert_task(
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


def test_low_level_records_pending_voids_and_restart(tmp_path) -> None:
    from docket.store import Reminder

    assert [f.name for f in dataclasses.fields(Reminder)] == [
        "id",
        "task_id",
        "kind",
        "fire_at",
        "planned_at",
        "claimed_at",
        "sent_at",
        "voided_at",
    ]
    path = tmp_path / "docket.sqlite3"
    with Store(path) as opened:
        seed(opened)
        with opened.transaction():
            rows = opened.insert_reminders(
                "t1",
                (reminders.PlannedReminder("due", AT), reminders.PlannedReminder("start", NEXT)),
                at=AT,
            )
        assert [row.id for row in rows] == ["r1", "r2"]
        assert rows[0] == Reminder("r1", "t1", "due", AT, AT, None, None, None)
        with opened.transaction():
            opened.void_reminders("t1", at=NEXT, kinds=())
        assert opened.reminders("t1") == rows
        # A future sender's already-sent row is not pending. Synthetic SQL only.
        opened._connection.execute(
            "UPDATE reminders SET claimed_at=?,sent_at=? WHERE number=1",
            (AT.isoformat(), AT.isoformat()),
        )
        with opened.transaction():
            opened.void_reminders("t1", at=NEXT)
        after = opened.reminders("t1")
        assert after[0].sent_at == AT and after[0].voided_at is None
        assert after[1].voided_at == NEXT
        with opened.transaction():
            opened.void_reminders("t1", at=AT)
        assert opened.reminders("t1") == after
        with opened.transaction():
            added = opened.insert_reminders(
                "t1", (reminders.PlannedReminder("late", NEXT),), at=NEXT
            )
        assert [row.id for row in added] == ["r3"]
        after = [*after, *added]
    with Store(path) as reopened:
        assert reopened.reminders("t1") == after


@pytest.mark.parametrize(
    "case",
    [
        "insert-outside",
        "void-outside",
        "insert-now",
        "void-now",
        "fire-time",
        "kind",
        "void-kind",
        "unknown-insert",
        "unknown-void",
        "bad-second",
    ],
)
def test_write_guards_refuse_before_partial_sql(tmp_path, case) -> None:
    with Store(tmp_path / "docket.sqlite3") as opened:
        seed(opened)
        good = reminders.PlannedReminder("due", AT)
        if case in ("insert-outside", "void-outside"):
            with pytest.raises(StoreError, match="^a write needs a transaction$"):
                if case == "insert-outside":
                    opened.insert_reminders("t1", (good,), at=AT)
                else:
                    opened.void_reminders("t1", at=AT)
        else:
            expected = {
                "insert-now": "an instant must be in UTC",
                "void-now": "an instant must be in UTC",
                "fire-time": "an instant must be in UTC",
                "kind": "invalid reminder kind",
                "void-kind": "invalid reminder kind",
                "unknown-insert": "unknown task",
                "unknown-void": "unknown task",
                "bad-second": "invalid reminder kind",
            }[case]
            with opened.transaction():
                with pytest.raises(StoreError) as raised:
                    if case == "insert-now":
                        opened.insert_reminders("t1", (good,), at=datetime(2026, 11, 20, 16))
                    elif case == "void-now":
                        opened.void_reminders("t1", at=datetime(2026, 11, 20, 16))
                    elif case == "fire-time":
                        opened.insert_reminders(
                            "t1",
                            (reminders.PlannedReminder("due", datetime(2026, 11, 20, 16)),),
                            at=AT,
                        )
                    elif case in ("kind", "bad-second"):
                        bad = reminders.PlannedReminder("synthetic-invalid", AT)
                        opened.insert_reminders(
                            "t1", (good, bad) if case == "bad-second" else (bad,), at=AT
                        )
                    elif case == "void-kind":
                        opened.void_reminders("t1", at=AT, kinds=("synthetic-invalid",))
                    elif case == "unknown-insert":
                        opened.insert_reminders("t99", (good,), at=AT)
                    else:
                        opened.void_reminders("t99", at=AT)
                assert str(raised.value) == expected
                assert raised.value.__cause__ is None
        assert opened.reminders("t1") == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("number", 0),
        ("number", -1),
        ("task", 99),
        ("kind", "synthetic-invalid"),
        ("kind", None),
        ("fire_at", None),
        ("planned_at", None),
    ],
)
def test_given_schema_checks_foreign_keys_and_nullability(tmp_path, field, value) -> None:
    with Store(tmp_path / "docket.sqlite3") as opened:
        seed(opened)
        fields = {
            "number": 1,
            "task": 1,
            "kind": "due",
            "fire_at": AT.isoformat(),
            "planned_at": AT.isoformat(),
        }
        fields[field] = value
        with pytest.raises(sqlite3.IntegrityError):
            opened._connection.execute(
                "INSERT INTO reminders(number,task,kind,fire_at,planned_at) "
                "VALUES (:number,:task,:kind,:fire_at,:planned_at)",
                fields,
            )


@pytest.mark.parametrize("column", ["number", "task", "kind", "fire_at", "planned_at", "delete"])
def test_given_schema_keeps_plan_history_immutable(tmp_path, column) -> None:
    with Store(tmp_path / "docket.sqlite3") as opened:
        seed(opened)
        opened._connection.execute(
            "INSERT INTO reminders(task,kind,fire_at,planned_at) VALUES (1,'due',?,?)",
            (AT.isoformat(), AT.isoformat()),
        )
        with pytest.raises(sqlite3.IntegrityError) as raised:
            if column == "delete":
                opened._connection.execute("DELETE FROM reminders WHERE number=1")
            else:
                opened._connection.execute(f"UPDATE reminders SET {column}={column} WHERE number=1")
        assert str(raised.value) == (
            "reminders are never removed" if column == "delete" else "reminder plan is immutable"
        )


@pytest.mark.parametrize("column", ["fire_at", "planned_at", "claimed_at", "sent_at", "voided_at"])
@pytest.mark.parametrize(
    "bad",
    ["synthetic-invalid", "2026-11-20T16:00:00", "2026-11-20T16:00:00+01:00"],
    ids=["unparseable", "naive", "non-utc"],
)
def test_bad_stored_times_are_refused_without_library_text(tmp_path, column, bad) -> None:
    with Store(tmp_path / "docket.sqlite3") as opened:
        seed(opened)
        fields = {
            "task": 1,
            "kind": "due",
            "fire_at": AT.isoformat(),
            "planned_at": AT.isoformat(),
            "claimed_at": None,
            "sent_at": None,
            "voided_at": None,
        }
        fields[column] = bad
        opened._connection.execute(
            "INSERT INTO reminders(task,kind,fire_at,planned_at,claimed_at,sent_at,voided_at) "
            "VALUES (:task,:kind,:fire_at,:planned_at,:claimed_at,:sent_at,:voided_at)",
            fields,
        )
        with pytest.raises(StoreError) as raised:
            opened.reminders("t1")
        assert str(raised.value) == "invalid stored reminder time: r1"
        assert raised.value.__cause__ is None


def test_normal_reminder_sql_uses_only_the_supplied_connection_module(
    tmp_path, monkeypatch
) -> None:
    from docket import store as store_module

    module = importlib.import_module("docket._store_reminders")
    for name in ("insert_reminder", "select_reminders", "void_reminders"):
        assert list(inspect.signature(getattr(module, name)).parameters)[0] == "connection"
    tree = ast.parse(inspect.getsource(module))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith("docket")
        if isinstance(node, ast.Import):
            assert all(not alias.name.startswith("docket") for alias in node.names)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in {
                "connect",
                "close",
                "commit",
                "rollback",
                "now",
                "executescript",
                "fromisoformat",
                "cursor",
            }
            if node.func.attr == "execute" and node.args and isinstance(node.args[0], ast.Constant):
                assert (
                    re.match(r"\s*(BEGIN|COMMIT|ROLLBACK|PRAGMA)\b", str(node.args[0].value), re.I)
                    is None
                )
    connect = sqlite3.connect
    owners = []
    connections = []

    class Tracked(sqlite3.Connection):
        def execute(self, sql, *args, **kwargs):
            if re.search(
                r"^\s*(INSERT INTO|UPDATE)\s+reminders\b|^\s*SELECT\b.*\bFROM\s+reminders\b",
                sql,
                re.I | re.S,
            ):
                owners.append(sys._getframe(1).f_globals["__name__"])
                if not sql.lstrip().upper().startswith("SELECT"):
                    assert self.in_transaction
            return super().execute(sql, *args, **kwargs)

    def tracked_connect(*args, **kwargs):
        connection = connect(*args, **kwargs, factory=Tracked)
        connections.append(connection)
        return connection

    monkeypatch.setattr(store_module.sqlite3, "connect", tracked_connect)
    with Store(tmp_path / "docket.sqlite3") as opened:
        seed(opened)
        with opened.transaction():
            opened.insert_reminders("t1", (reminders.PlannedReminder("due", AT),), at=AT)
            opened.void_reminders("t1", at=NEXT)
        assert len(opened.reminders("t1")) == 1
    assert len(owners) >= 3 and set(owners) == {"docket._store_reminders"}
    assert len(connections) == 1
