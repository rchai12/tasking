import ast
import dataclasses
import importlib
import inspect
import re
import sqlite3
import sys
from datetime import datetime, timedelta

import pytest

from docket import reminders
from docket.store import Store, StoreError
from tests.notifier_cases import NOW, rows

T1 = NOW + timedelta(minutes=15)
T2 = NOW + timedelta(minutes=30)
NAIVE = datetime(2026, 11, 20, 16)


def seed(opened: Store) -> None:
    """t1 with r1 (due at NOW) and r2 (start at NOW); t2 with r3 (due at NOW)."""
    with opened.transaction():
        for _ in range(2):
            opened.insert_task(
                title="Synthetic task",
                state="open",
                deadline=None,
                work=None,
                source="owner",
                provider=None,
                message_id=None,
                link=None,
                at=NOW,
            )
        plans = (reminders.PlannedReminder("due", NOW), reminders.PlannedReminder("start", NOW))
        opened.insert_reminders("t1", plans, at=NOW)
        opened.insert_reminders("t2", plans[:1], at=NOW)


def queue(opened: Store, ids=("r1",), *, key="k1", task="t1", missed=0, at=NOW):
    with opened.transaction():
        return opened.queue_post(task, ids, key=key, kind="due", missed=missed, at=at)


def test_the_post_record_and_given_tables() -> None:
    from docket.store import Post

    assert [field.name for field in dataclasses.fields(Post)] == [
        "id",
        "task_id",
        "key",
        "kind",
        "missed",
        "reminder_ids",
        "queued_at",
        "claimed_at",
        "sent_at",
    ]
    from docket import schema

    with sqlite3.connect(":memory:") as db:
        db.executescript("".join(schema.MIGRATIONS))
        assert [row[1] for row in db.execute("PRAGMA table_info(posts)")] == [
            "number",
            "task",
            "key",
            "kind",
            "missed",
            "queued_at",
            "claimed_at",
            "sent_at",
        ]
        assert [row[1] for row in db.execute("PRAGMA table_info(post_reminders)")] == [
            "post",
            "reminder",
        ]
        assert [
            db.execute(f"PRAGMA table_list('{name}')").fetchone()[-1]
            for name in (
                "posts",
                "post_reminders",
            )
        ] == [1, 1]


def test_due_queue_claim_release_and_mark_round_trip(tmp_path) -> None:
    from docket.store import Post

    path = tmp_path / "docket.sqlite3"
    with Store(path) as opened:
        seed(opened)
        assert [row.id for row in opened.due_reminders(NOW)] == ["r1", "r2", "r3"]
        assert opened.due_reminders(NOW - timedelta(microseconds=1)) == []
        with opened.transaction():
            post = opened.queue_post("t1", ("r1", "r2"), key="k1", kind="start", missed=2, at=T1)
        assert post == Post("p1", "t1", "k1", "start", 2, ("r1", "r2"), T1, None, None)
        assert [row.id for row in opened.due_reminders(T2)] == ["r3"]
        assert [row.claimed_at for row in opened.reminders("t1")] == [T1, T1]
        with opened.transaction():
            claimed = opened.claim_posts(at=T1, stale_before=NOW)
        assert claimed == [Post("p1", "t1", "k1", "start", 2, ("r1", "r2"), T1, T1, None)]
        with opened.transaction():
            assert opened.claim_posts(at=T2, stale_before=T1) == []
            opened.release_post("p1", claimed_at=NOW)
        assert opened.posts("t1")[0].claimed_at == T1
        with opened.transaction():
            opened.release_post("p1", claimed_at=T1)
        assert opened.posts("t1")[0].claimed_at is None
        with opened.transaction():
            assert [post.id for post in opened.claim_posts(at=T2, stale_before=NOW)] == ["p1"]
            opened.mark_post_sent("p1", at=T2)
            opened.mark_post_sent("p1", at=T2 + timedelta(minutes=1))
            opened.release_post("p1", claimed_at=T2)
            assert (
                opened.claim_posts(
                    at=T2 + timedelta(minutes=9), stale_before=T2 + timedelta(minutes=8)
                )
                == []
            )
        done = Post("p1", "t1", "k1", "start", 2, ("r1", "r2"), T1, T2, T2)
        assert opened.posts("t1") == [done]
        assert [row.sent_at for row in opened.reminders("t1")] == [T2, T2]
    with Store(path) as reopened:
        assert reopened.posts("t1") == [done]
        assert reopened.posts("t2") == reopened.posts("bad") == reopened.posts("t99") == []


CASES = {
    "queue-outside": "a write needs a transaction",
    "claim-outside": "a write needs a transaction",
    "mark-outside": "a write needs a transaction",
    "release-outside": "a write needs a transaction",
    "queue-naive": "an instant must be in UTC",
    "claim-naive": "an instant must be in UTC",
    "stale-naive": "an instant must be in UTC",
    "mark-naive": "an instant must be in UTC",
    "release-naive": "an instant must be in UTC",
    "due-naive": "an instant must be in UTC",
    "unknown-task": "unknown task",
    "empty-key": "invalid post key",
    "long-key": "invalid post key",
    "key-type": "invalid post key",
    "kind": "invalid reminder kind",
    "missed-negative": "invalid missed count",
    "missed-over": "invalid missed count",
    "missed-bool": "invalid missed count",
    "no-reminders": "a post needs a reminder",
    "malformed-id": "invalid reminder id",
    "other-task": "reminder not pending: r3",
    "claimed": "reminder not pending: r1",
    "duplicate": "reminder not pending: r1",
    "unknown-mark": "unknown post",
    "unknown-release": "unknown post",
}


@pytest.mark.parametrize("case", list(CASES))
def test_post_writes_refuse_before_any_sql_change(tmp_path, case) -> None:
    path = tmp_path / "docket.sqlite3"
    with Store(path) as opened:
        seed(opened)
        if case == "claimed":
            queue(opened)
        before = {name: rows(path, name) for name in ("posts", "post_reminders", "reminders")}
        calls = {
            "queue-outside": lambda: opened.queue_post(
                "t1", ("r1",), key="k2", kind="due", missed=0, at=NOW
            ),
            "claim-outside": lambda: opened.claim_posts(at=NOW, stale_before=NOW),
            "mark-outside": lambda: opened.mark_post_sent("p1", at=NOW),
            "release-outside": lambda: opened.release_post("p1", claimed_at=NOW),
        }
        inside = {
            "queue-naive": lambda: opened.queue_post(
                "t1", ("r1",), key="k2", kind="due", missed=0, at=NAIVE
            ),
            "claim-naive": lambda: opened.claim_posts(at=NAIVE, stale_before=NOW),
            "stale-naive": lambda: opened.claim_posts(at=NOW, stale_before=NAIVE),
            "mark-naive": lambda: opened.mark_post_sent("p1", at=NAIVE),
            "release-naive": lambda: opened.release_post("p1", claimed_at=NAIVE),
            "due-naive": lambda: opened.due_reminders(NAIVE),
            "unknown-task": lambda: opened.queue_post(
                "t99", ("r1",), key="k2", kind="due", missed=0, at=NOW
            ),
            "empty-key": lambda: opened.queue_post(
                "t1", ("r1",), key="", kind="due", missed=0, at=NOW
            ),
            "long-key": lambda: opened.queue_post(
                "t1", ("r1",), key="k" * 201, kind="due", missed=0, at=NOW
            ),
            "key-type": lambda: opened.queue_post(
                "t1", ("r1",), key=5, kind="due", missed=0, at=NOW
            ),
            "kind": lambda: opened.queue_post(
                "t1", ("r1",), key="k2", kind="synthetic-invalid", missed=0, at=NOW
            ),
            "missed-negative": lambda: opened.queue_post(
                "t1", ("r1",), key="k2", kind="due", missed=-1, at=NOW
            ),
            "missed-over": lambda: opened.queue_post(
                "t1", ("r1", "r2"), key="k2", kind="due", missed=3, at=NOW
            ),
            "missed-bool": lambda: opened.queue_post(
                "t1", ("r1",), key="k2", kind="due", missed=True, at=NOW
            ),
            "no-reminders": lambda: opened.queue_post(
                "t1", (), key="k2", kind="due", missed=0, at=NOW
            ),
            "malformed-id": lambda: opened.queue_post(
                "t1", ("r2", "x1"), key="k2", kind="due", missed=0, at=NOW
            ),
            "other-task": lambda: opened.queue_post(
                "t1", ("r2", "r3"), key="k2", kind="due", missed=0, at=NOW
            ),
            "claimed": lambda: opened.queue_post(
                "t1", ("r2", "r1"), key="k2", kind="due", missed=0, at=NOW
            ),
            "duplicate": lambda: opened.queue_post(
                "t1", ("r1", "r1"), key="k2", kind="due", missed=0, at=NOW
            ),
            "unknown-mark": lambda: opened.mark_post_sent("p9", at=NOW),
            "unknown-release": lambda: opened.release_post("x1", claimed_at=NOW),
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


@pytest.mark.parametrize(
    "state,claimed",
    [
        ("unclaimed", ["p1"]),
        ("fresh-claim", []),
        ("stale-claim", ["p1"]),
        ("sent", []),
        ("all-voided", []),
        ("partly-voided", ["p1"]),
    ],
    ids=["unclaimed", "fresh-claim", "stale-claim", "sent", "all-voided", "partly-voided"],
)
def test_a_claim_takes_only_unsent_unclaimed_or_stale_posts_with_a_live_reminder(
    tmp_path, state, claimed
) -> None:
    with Store(tmp_path / "docket.sqlite3") as opened:
        seed(opened)
        queue(opened, ("r1", "r2"))
        with opened.transaction():
            if state != "unclaimed":
                opened.claim_posts(at=NOW, stale_before=NOW)
            if state == "sent":
                opened.mark_post_sent("p1", at=NOW)
            if state == "all-voided":
                opened.void_reminders("t1", at=NOW)
            if state == "partly-voided":
                opened.void_reminders("t1", at=NOW, kinds=("start",))
            stale = NOW + timedelta(microseconds=1) if state != "fresh-claim" else NOW
            found = opened.claim_posts(at=T1, stale_before=stale)
        assert [post.id for post in found] == claimed
        assert [post.claimed_at for post in found] == [T1] * len(claimed)
        if state == "partly-voided":
            with opened.transaction():
                opened.mark_post_sent("p1", at=T2)
            assert [(row.sent_at, row.voided_at) for row in opened.reminders("t1")] == [
                (T2, None),
                (None, NOW),
            ]


Q = NOW.isoformat()
SCHEMA_CASES = {
    "number": ("INSERT INTO posts VALUES (0, 1, 'k9', 'due', 0, ?, NULL, NULL)", (Q,), "CHECK"),
    "task": ("INSERT INTO posts VALUES (NULL, 99, 'k9', 'due', 0, ?, NULL, NULL)", (Q,), "FOREIGN"),
    "empty-key": ("INSERT INTO posts VALUES (NULL, 1, '', 'due', 0, ?, NULL, NULL)", (Q,), "CHECK"),
    "same-key": (
        "INSERT INTO posts VALUES (NULL, 1, 'k1', 'due', 0, ?, NULL, NULL)",
        (Q,),
        "UNIQUE",
    ),
    "kind": ("INSERT INTO posts VALUES (NULL, 1, 'k9', 'other', 0, ?, NULL, NULL)", (Q,), "CHECK"),
    "missed": ("INSERT INTO posts VALUES (NULL, 1, 'k9', 'due', -1, ?, NULL, NULL)", (Q,), "CHECK"),
    "queued": (
        "INSERT INTO posts VALUES (NULL, 1, 'k9', 'due', 0, NULL, NULL, NULL)",
        (),
        "NOT NULL",
    ),
    "second-post": ("INSERT INTO post_reminders VALUES (2, 1)", (), "UNIQUE"),
    "unknown-reminder": ("INSERT INTO post_reminders VALUES (2, 99)", (), "FOREIGN"),
    "change-key": ("UPDATE posts SET key = 'k9'", (), "post contents are immutable"),
    "change-missed": ("UPDATE posts SET missed = 1", (), "post contents are immutable"),
    "change-queued": ("UPDATE posts SET queued_at = ?", (Q,), "post contents are immutable"),
    "delete-post": ("DELETE FROM posts", (), "posts are never removed"),
    "change-link": ("UPDATE post_reminders SET reminder = 2", (), "post reminders are immutable"),
    "delete-link": ("DELETE FROM post_reminders", (), "post reminders are never removed"),
}


@pytest.mark.parametrize("case", list(SCHEMA_CASES))
def test_given_post_schema_refuses_bad_rows_and_history_changes(tmp_path, case) -> None:
    sql, values, expected = SCHEMA_CASES[case]
    with Store(tmp_path / "docket.sqlite3") as opened:
        seed(opened)
        for number in (1, 2):
            opened._connection.execute(
                "INSERT INTO posts VALUES (?, 1, ?, 'due', 0, ?, NULL, NULL)",
                (number, f"k{number}", Q),
            )
        opened._connection.execute("INSERT INTO post_reminders VALUES (1, 1)")
        with pytest.raises(sqlite3.IntegrityError) as raised:
            opened._connection.execute(sql, values)
        assert expected in str(raised.value)


@pytest.mark.parametrize("column", ["queued_at", "claimed_at", "sent_at"])
@pytest.mark.parametrize(
    "bad",
    ["synthetic-invalid", "2026-11-20T16:00:00", "2026-11-20T16:00:00+01:00"],
    ids=["unparseable", "naive", "non-utc"],
)
def test_bad_stored_post_times_are_refused_without_library_text(tmp_path, column, bad) -> None:
    with Store(tmp_path / "docket.sqlite3") as opened:
        seed(opened)
        fields = {"queued_at": NOW.isoformat(), "claimed_at": None, "sent_at": None}
        fields[column] = bad
        opened._connection.execute(
            "INSERT INTO posts VALUES (1, 1, 'k1', 'due', 0, :queued_at, :claimed_at, :sent_at)",
            fields,
        )
        opened._connection.execute("INSERT INTO post_reminders VALUES (1, 1)")
        with pytest.raises(StoreError) as raised:
            opened.posts("t1")
        assert str(raised.value) == "invalid stored post time: p1"
        assert raised.value.__cause__ is None


def test_post_and_reminder_sql_stay_in_their_table_modules_on_one_connection(
    tmp_path, monkeypatch
) -> None:
    from docket import store as store_module

    module = importlib.import_module("docket._store_posts")
    functions = [node for node in ast.parse(inspect.getsource(module)).body]
    assert any(isinstance(node, ast.FunctionDef) for node in functions)
    for node in functions:
        if isinstance(node, ast.FunctionDef):
            assert node.args.args[0].arg == "connection"
    for node in ast.walk(ast.parse(inspect.getsource(module))):
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
    owners: dict[str, set[str]] = {"posts": set(), "post_reminders": set(), "reminders": set()}
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
        seed(opened)
        for owner in owners.values():
            owner.clear()
        assert len(opened.due_reminders(NOW)) == 3
        queue(opened, ("r1", "r2"))
        with opened.transaction():
            opened.claim_posts(at=T1, stale_before=NOW)
            opened.release_post("p1", claimed_at=T1)
            opened.claim_posts(at=T1, stale_before=NOW)
            opened.mark_post_sent("p1", at=T2)
        assert len(opened.posts("t1")) == 1
    assert owners == {
        "posts": {"docket._store_posts"},
        "post_reminders": {"docket._store_posts"},
        "reminders": {"docket._store_reminders"},
    }
    assert len(connections) == 1
