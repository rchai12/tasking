import ast
import dataclasses
import importlib
import inspect
import re
import sqlite3
import sys
from datetime import UTC, date, datetime, timedelta

import pytest

from docket.deadlines import Deadline
from docket.store import Store, StoreError
from tests.digest_cases import DAY, SLOT, TASKS, ZONE, seed
from tests.notifier_cases import rows

T1 = SLOT + timedelta(minutes=1)
T2 = SLOT + timedelta(minutes=2)
OVERDUE = SLOT - timedelta(minutes=720)
NAIVE = datetime(2026, 11, 20, 12)
NEXT = date(2026, 11, 21)
THREE = TASKS[:3]
"""t1, t2 and t3 open and past their last late reminder at SLOT."""


def queue(opened: Store, task_ids=("t1", "t2"), *, day=DAY, key="k1", at=SLOT):
    with opened.transaction():
        return opened.queue_digest(day, task_ids, key=key, at=at)


def claim(opened: Store, *, day=DAY, at=T1, stale_before=SLOT, overdue_before=OVERDUE):
    with opened.transaction():
        return opened.claim_digest(
            day, at=at, stale_before=stale_before, overdue_before=overdue_before
        )


def test_the_digest_record_and_given_tables() -> None:
    from docket import schema
    from docket.store import DailyDigest

    assert [field.name for field in dataclasses.fields(DailyDigest)] == [
        "id",
        "day",
        "key",
        "task_ids",
        "queued_at",
        "claimed_at",
        "sent_at",
    ]
    with sqlite3.connect(":memory:") as db:
        db.executescript("".join(schema.MIGRATIONS))
        assert [row[1] for row in db.execute("PRAGMA table_info(digests)")] == [
            "number",
            "day",
            "key",
            "queued_at",
            "claimed_at",
            "sent_at",
        ]
        assert [row[1] for row in db.execute("PRAGMA table_info(digest_tasks)")] == [
            "digest",
            "task",
        ]
        assert [
            db.execute(f"PRAGMA table_list('{name}')").fetchone()[-1]
            for name in ("digests", "digest_tasks")
        ] == [1, 1]


def test_queue_read_claim_release_and_mark_round_trip(tmp_path) -> None:
    from docket.store import DailyDigest

    path = tmp_path / "docket.sqlite3"
    with Store(path) as opened:
        seed(opened, THREE)
        assert opened.digest(DAY) is None
        queued = queue(opened, ("t3", "t1"), at=SLOT)
        assert queued == DailyDigest("d1", DAY, "k1", ("t1", "t3"), SLOT, None, None)
        assert opened.digest(DAY) == queued
        assert opened.digest(NEXT) is None
        assert claim(opened, at=T1) == DailyDigest("d1", DAY, "k1", ("t1", "t3"), SLOT, T1, None)
        assert claim(opened, at=T2, stale_before=T1) is None
        with opened.transaction():
            opened.release_digest("d1", claimed_at=SLOT)
        assert opened.digest(DAY).claimed_at == T1
        with opened.transaction():
            opened.release_digest("d1", claimed_at=T1)
        assert opened.digest(DAY).claimed_at is None
        assert claim(opened, at=T2).claimed_at == T2
        with opened.transaction():
            opened.mark_digest_sent("d1", at=T2)
            opened.mark_digest_sent("d1", at=T2 + timedelta(minutes=1))
            opened.release_digest("d1", claimed_at=T2)
        assert (
            claim(opened, at=T2 + timedelta(minutes=9), stale_before=T2 + timedelta(minutes=8))
            is None
        )
        done = DailyDigest("d1", DAY, "k1", ("t1", "t3"), SLOT, T2, T2)
        assert opened.digest(DAY) == done
        queue(opened, ("t2",), day=NEXT, key="k2", at=T2)
    with Store(path) as reopened:
        assert reopened.digest(DAY) == done
        assert reopened.digest(NEXT) == DailyDigest("d2", NEXT, "k2", ("t2",), T2, None, None)
        assert sorted(rows(path, "digest_tasks")) == [(1, 1), (1, 3), (2, 2)]


CASES = {
    "queue-outside": "a write needs a transaction",
    "claim-outside": "a write needs a transaction",
    "mark-outside": "a write needs a transaction",
    "release-outside": "a write needs a transaction",
    "queue-naive": "an instant must be in UTC",
    "claim-naive": "an instant must be in UTC",
    "stale-naive": "an instant must be in UTC",
    "overdue-naive": "an instant must be in UTC",
    "mark-naive": "an instant must be in UTC",
    "release-naive": "an instant must be in UTC",
    "day-text": "invalid digest day",
    "day-datetime": "invalid digest day",
    "claim-day": "invalid digest day",
    "read-day": "invalid digest day",
    "empty-key": "invalid digest key",
    "long-key": "invalid digest key",
    "key-type": "invalid digest key",
    "no-tasks": "a digest needs a task",
    "malformed-id": "invalid task id",
    "unknown-task": "task not open: t99",
    "ended-task": "task not open: t4",
    "duplicate": "task not open: t1",
    "same-day": "digest already queued: 2026-11-20",
    "unknown-mark": "unknown digest",
    "unknown-release": "unknown digest",
}


@pytest.mark.parametrize("case", list(CASES))
def test_digest_writes_refuse_before_any_sql_change(tmp_path, case) -> None:
    path = tmp_path / "docket.sqlite3"
    with Store(path) as opened:
        seed(opened, (*THREE, TASKS[4]))
        if case == "same-day":
            queue(opened)
        before = {name: rows(path, name) for name in ("digests", "digest_tasks", "tasks")}
        calls = {
            "queue-outside": lambda: opened.queue_digest(DAY, ("t1",), key="k2", at=SLOT),
            "claim-outside": lambda: opened.claim_digest(
                DAY, at=SLOT, stale_before=SLOT, overdue_before=OVERDUE
            ),
            "mark-outside": lambda: opened.mark_digest_sent("d1", at=SLOT),
            "release-outside": lambda: opened.release_digest("d1", claimed_at=SLOT),
            "read-day": lambda: opened.digest("2026-11-20"),
        }
        inside = {
            "queue-naive": lambda: opened.queue_digest(DAY, ("t1",), key="k2", at=NAIVE),
            "claim-naive": lambda: opened.claim_digest(
                DAY, at=NAIVE, stale_before=SLOT, overdue_before=OVERDUE
            ),
            "stale-naive": lambda: opened.claim_digest(
                DAY, at=SLOT, stale_before=NAIVE, overdue_before=OVERDUE
            ),
            "overdue-naive": lambda: opened.claim_digest(
                DAY, at=SLOT, stale_before=SLOT, overdue_before=NAIVE
            ),
            "mark-naive": lambda: opened.mark_digest_sent("d1", at=NAIVE),
            "release-naive": lambda: opened.release_digest("d1", claimed_at=NAIVE),
            "day-text": lambda: opened.queue_digest("2026-11-20", ("t1",), key="k2", at=SLOT),
            "day-datetime": lambda: opened.queue_digest(SLOT, ("t1",), key="k2", at=SLOT),
            "claim-day": lambda: opened.claim_digest(
                SLOT, at=SLOT, stale_before=SLOT, overdue_before=OVERDUE
            ),
            "empty-key": lambda: opened.queue_digest(DAY, ("t1",), key="", at=SLOT),
            "long-key": lambda: opened.queue_digest(DAY, ("t1",), key="k" * 201, at=SLOT),
            "key-type": lambda: opened.queue_digest(DAY, ("t1",), key=5, at=SLOT),
            "no-tasks": lambda: opened.queue_digest(DAY, (), key="k2", at=SLOT),
            "malformed-id": lambda: opened.queue_digest(DAY, ("t1", "x1"), key="k2", at=SLOT),
            "unknown-task": lambda: opened.queue_digest(DAY, ("t1", "t99"), key="k2", at=SLOT),
            "ended-task": lambda: opened.queue_digest(DAY, ("t1", "t4"), key="k2", at=SLOT),
            "duplicate": lambda: opened.queue_digest(DAY, ("t1", "t1"), key="k2", at=SLOT),
            "same-day": lambda: opened.queue_digest(DAY, ("t3",), key="k2", at=SLOT),
            "unknown-mark": lambda: opened.mark_digest_sent("d9", at=SLOT),
            "unknown-release": lambda: opened.release_digest("x1", claimed_at=SLOT),
        }
        with pytest.raises(StoreError) as raised:
            if case in calls:
                calls[case]()
            else:
                with opened.transaction():
                    inside[case]()
        assert str(raised.value) == CASES[case]
        assert raised.value.__cause__ is None
    assert {name: rows(path, name) for name in before} == before


MOVED = Deadline(datetime(2026, 11, 30, 22, tzinfo=UTC), ZONE, True)


@pytest.mark.parametrize(
    "state,found,stored",
    [
        ("unclaimed", "d1", T1),
        ("fresh-claim", None, SLOT),
        ("stale-claim", "d1", T1),
        ("sent", None, SLOT),
        ("other-day", None, None),
        ("all-ended", None, None),
        ("all-moved", None, None),
        ("one-left", "d1", T1),
    ],
    ids=[
        "unclaimed",
        "fresh-claim",
        "stale-claim",
        "sent",
        "other-day",
        "all-ended",
        "all-moved",
        "one-left",
    ],
)
def test_a_claim_takes_only_that_days_unsent_digest_with_a_task_still_overdue(
    tmp_path, state, found, stored
) -> None:
    with Store(tmp_path / "docket.sqlite3") as opened:
        seed(opened, THREE)
        queue(opened)
        with opened.transaction():
            if state in {"fresh-claim", "stale-claim", "sent"}:
                opened.claim_digest(DAY, at=SLOT, stale_before=SLOT, overdue_before=OVERDUE)
            if state == "sent":
                opened.mark_digest_sent("d1", at=SLOT)
            if state in {"all-ended", "one-left"}:
                opened.update_task("t1", at=SLOT, state="done")
            if state == "all-ended":
                opened.update_task("t2", at=SLOT, state="cancelled")
            if state == "all-moved":
                opened.update_task("t1", at=SLOT, deadline=MOVED)
                opened.update_task("t2", at=SLOT, deadline=None)
        stale = SLOT + timedelta(microseconds=1) if state != "fresh-claim" else SLOT
        result = claim(opened, day=NEXT if state == "other-day" else DAY, stale_before=stale)
        assert (result and result.id) == found
        assert opened.digest(DAY).claimed_at == stored
        if found:
            assert result == opened.digest(DAY)


Q = SLOT.isoformat()
SCHEMA_CASES = {
    "number": ("INSERT INTO digests VALUES (0, '2026-11-22', 'k9', ?, NULL, NULL)", (Q,), "CHECK"),
    "day": ("INSERT INTO digests VALUES (NULL, '2026-02-30', 'k9', ?, NULL, NULL)", (Q,), "CHECK"),
    "day-format": (
        "INSERT INTO digests VALUES (NULL, '2026-11-22T00:00', 'k9', ?, NULL, NULL)",
        (Q,),
        "CHECK",
    ),
    "same-day": (
        "INSERT INTO digests VALUES (NULL, '2026-11-20', 'k9', ?, NULL, NULL)",
        (Q,),
        "UNIQUE",
    ),
    "empty-key": (
        "INSERT INTO digests VALUES (NULL, '2026-11-22', '', ?, NULL, NULL)",
        (Q,),
        "CHECK",
    ),
    "same-key": (
        "INSERT INTO digests VALUES (NULL, '2026-11-22', 'k1', ?, NULL, NULL)",
        (Q,),
        "UNIQUE",
    ),
    "queued": (
        "INSERT INTO digests VALUES (NULL, '2026-11-22', 'k9', NULL, NULL, NULL)",
        (),
        "NOT NULL",
    ),
    "same-task": ("INSERT INTO digest_tasks VALUES (1, 1)", (), "UNIQUE"),
    "unknown-task": ("INSERT INTO digest_tasks VALUES (2, 99)", (), "FOREIGN"),
    "unknown-digest": ("INSERT INTO digest_tasks VALUES (9, 1)", (), "FOREIGN"),
    "change-day": ("UPDATE digests SET day = '2026-11-22'", (), "digest contents are immutable"),
    "change-key": ("UPDATE digests SET key = 'k9'", (), "digest contents are immutable"),
    "change-queued": ("UPDATE digests SET queued_at = ?", (Q,), "digest contents are immutable"),
    "delete-digest": ("DELETE FROM digests", (), "digests are never removed"),
    "change-member": ("UPDATE digest_tasks SET task = 2", (), "digest tasks are immutable"),
    "delete-member": ("DELETE FROM digest_tasks", (), "digest tasks are never removed"),
}


@pytest.mark.parametrize("case", list(SCHEMA_CASES))
def test_given_digest_schema_refuses_bad_rows_and_history_changes(tmp_path, case) -> None:
    sql, values, expected = SCHEMA_CASES[case]
    with Store(tmp_path / "docket.sqlite3") as opened:
        seed(opened, THREE)
        for number, day in ((1, "2026-11-20"), (2, "2026-11-21")):
            opened._connection.execute(
                "INSERT INTO digests VALUES (?, ?, ?, ?, NULL, NULL)",
                (number, day, f"k{number}", Q),
            )
        opened._connection.execute("INSERT INTO digest_tasks VALUES (1, 1)")
        with pytest.raises(sqlite3.IntegrityError) as raised:
            opened._connection.execute(sql, values)
        assert expected in str(raised.value)


@pytest.mark.parametrize("column", ["queued_at", "claimed_at", "sent_at"])
@pytest.mark.parametrize(
    "bad",
    ["synthetic-invalid", "2026-11-20T12:00:00", "2026-11-20T12:00:00+01:00"],
    ids=["unparseable", "naive", "non-utc"],
)
def test_bad_stored_digest_times_are_refused_without_library_text(tmp_path, column, bad) -> None:
    with Store(tmp_path / "docket.sqlite3") as opened:
        seed(opened, THREE)
        fields = {"queued_at": Q, "claimed_at": None, "sent_at": None}
        fields[column] = bad
        opened._connection.execute(
            "INSERT INTO digests VALUES (1, '2026-11-20', 'k1', :queued_at, :claimed_at, :sent_at)",
            fields,
        )
        opened._connection.execute("INSERT INTO digest_tasks VALUES (1, 1)")
        with pytest.raises(StoreError) as raised:
            opened.digest(DAY)
        assert str(raised.value) == "invalid stored digest time: d1"
        assert raised.value.__cause__ is None


def test_digest_sql_stays_in_its_table_module_on_one_connection(tmp_path, monkeypatch) -> None:
    from docket import store as store_module

    module = importlib.import_module("docket._store_digests")
    tree = ast.parse(inspect.getsource(module))
    assert any(isinstance(node, ast.FunctionDef) for node in tree.body)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            assert node.args.args[0].arg == "connection"
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
                "new_id",
                "executescript",
                "fromisoformat",
                "isoformat",
                "cursor",
            }
            if node.func.attr == "execute" and node.args and isinstance(node.args[0], ast.Constant):
                assert (
                    re.match(r"\s*(BEGIN|COMMIT|ROLLBACK|PRAGMA)\b", str(node.args[0].value), re.I)
                    is None
                )
    connect = sqlite3.connect
    owners: dict[str, set[str]] = {"digests": set(), "digest_tasks": set()}
    connections = []
    pattern = re.compile(
        r"^\s*(?:INSERT INTO|UPDATE)\s+(\w+)|^\s*SELECT\b.*?\bFROM\s+(\w+)", re.I | re.S
    )

    class Tracked(sqlite3.Connection):
        def execute(self, sql, *args, **kwargs):
            found = pattern.search(sql)
            table = found and (found.group(1) or found.group(2))
            if table in owners:
                owners[table].add(sys._getframe(1).f_globals["__name__"])
                if not sql.lstrip().upper().startswith("SELECT"):
                    assert self.in_transaction
            return super().execute(sql, *args, **kwargs)

    def tracked_connect(*args, **kwargs):
        connection = connect(*args, **kwargs, factory=Tracked)
        connections.append(connection)
        return connection

    monkeypatch.setattr(store_module.sqlite3, "connect", tracked_connect)
    with Store(tmp_path / "docket.sqlite3") as opened:
        seed(opened, THREE)
        queue(opened)
        claim(opened)
        with opened.transaction():
            opened.release_digest("d1", claimed_at=T1)
        claim(opened)
        with opened.transaction():
            opened.mark_digest_sent("d1", at=T2)
        assert opened.digest(DAY).sent_at == T2
    assert owners == {
        "digests": {"docket._store_digests"},
        "digest_tasks": {"docket._store_digests"},
    }
    assert len(connections) == 1
