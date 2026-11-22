"""Phase 5b: migrations live in their own module, and the tasks SQL takes named columns."""

import ast
import inspect
import sqlite3
from collections.abc import Iterator
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import pytest

from docket import _store_tasks
from docket.deadlines import Deadline, WorkTime
from docket.store import Store
from tests.reference_cases import snapshot

MARK = "Phase 5b given test: remove this marker when migrations and task columns are split"
CREATED = "2026-11-17T14:00:00.000000+00:00"
UPDATED = "2026-11-17T15:00:00.000000+00:00"
LATER = "2026-11-17T16:00:00.000000+00:00"
MIGRATE_SOURCE = Path(__file__).parents[2] / "src" / "docket" / "_store_migrate.py"
COLUMNS = {
    "title": "Synthetic named title",
    "state": "in_progress",
    "deadline_at": "2026-11-20T15:00:00.000000+00:00",
    "deadline_zone": "America/New_York",
    "deadline_time_given": 1,
    "work_start": "2026-11-19T14:30:00.000000+00:00",
    "work_minutes": 45,
    "work_zone": "Europe/London",
    "source": "email",
    "provider": "outlook",
    "message_id": "synthetic-message-7",
    "link": "https://mail.example.test/7",
    "created_at": CREATED,
    "updated_at": UPDATED,
}
MOVED = [
    "_migrate",
    "_apply_migration",
    "_user_version",
    "_migrate_references",
    "_refuse_invalid_references",
    "_refuse_reference",
    "_backfill_reminders",
]


@pytest.fixture
def connection(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """A migrated database with one owner task, t1, opened without the store."""
    path = tmp_path / "docket.sqlite3"
    Store(path).close()
    with closing(sqlite3.connect(path)) as db:
        db.row_factory = sqlite3.Row
        with db:
            db.execute(
                "INSERT INTO tasks (title, state, source, created_at, updated_at) "
                "VALUES ('Synthetic first title', 'open', 'owner', ?, ?)",
                (CREATED, CREATED),
            )
        yield db


def row(db: sqlite3.Connection, number: int) -> tuple[object, ...]:
    (found,) = _store_tasks.select_task(db, number)
    return tuple(found)


def user_version(path: Path) -> int:
    with closing(sqlite3.connect(path)) as db:
        return int(db.execute("PRAGMA user_version").fetchone()[0])


def test_the_task_insert_takes_named_columns_only() -> None:
    parameters = inspect.signature(_store_tasks.insert_task).parameters.values()
    assert [(item.name, item.kind.name) for item in parameters] == [
        ("connection", "POSITIONAL_OR_KEYWORD"),
        *((name, "KEYWORD_ONLY") for name in COLUMNS),
    ]


def test_a_positional_tuple_is_refused_and_writes_nothing(
    connection: sqlite3.Connection,
) -> None:
    with pytest.raises(TypeError):
        _store_tasks.insert_task(connection, tuple(COLUMNS.values()))  # type: ignore[call-arg]
    assert connection.execute("SELECT count(*) FROM tasks").fetchone()[0] == 1


def test_each_named_column_lands_in_its_own_column(connection: sqlite3.Connection) -> None:
    cursor = _store_tasks.insert_task(connection, **COLUMNS)  # type: ignore[arg-type]
    assert cursor.lastrowid == 2
    assert row(connection, 2) == (
        2,
        "Synthetic named title",
        "in_progress",
        "2026-11-20T15:00:00.000000+00:00",
        "America/New_York",
        1,
        "2026-11-19T14:30:00.000000+00:00",
        45,
        "Europe/London",
        "email",
        "outlook",
        "synthetic-message-7",
        "https://mail.example.test/7",
        "2026-11-17T14:00:00.000000+00:00",
        "2026-11-17T15:00:00.000000+00:00",
    )


def test_the_store_writes_each_task_field_to_its_own_column(tmp_path: Path) -> None:
    path = tmp_path / "docket.sqlite3"
    with Store(path) as store, store.transaction():
        store.insert_task(
            title="Synthetic store title",
            state="open",
            deadline=Deadline(datetime(2026, 11, 20, 15, tzinfo=UTC), "America/New_York", True),
            work=WorkTime(datetime(2026, 11, 19, 14, 30, tzinfo=UTC), 45, "Europe/London"),
            source="email",
            provider="outlook",
            message_id="synthetic-message-8",
            link="https://mail.example.test/8",
            at=datetime(2026, 11, 17, 14, tzinfo=UTC),
        )
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("SELECT * FROM tasks").fetchall() == [
            (
                1,
                "Synthetic store title",
                "open",
                "2026-11-20T15:00:00.000000+00:00",
                "America/New_York",
                1,
                "2026-11-19T14:30:00.000000+00:00",
                45,
                "Europe/London",
                "email",
                "outlook",
                "synthetic-message-8",
                "https://mail.example.test/8",
                "2026-11-17T14:00:00.000000+00:00",
                "2026-11-17T14:00:00.000000+00:00",
            )
        ]


def test_every_allowed_update_column_is_written(connection: sqlite3.Connection) -> None:
    _store_tasks.update_task(
        connection,
        1,
        LATER,
        {
            "title": "Synthetic second title",
            "state": "done",
            "deadline_at": "2026-11-20T15:00:00.000000+00:00",
            "deadline_zone": "America/New_York",
            "deadline_time_given": 0,
            "work_start": "2026-11-19T14:30:00.000000+00:00",
            "work_minutes": 30,
            "work_zone": "Europe/London",
        },
    )
    assert row(connection, 1) == (
        1,
        "Synthetic second title",
        "done",
        "2026-11-20T15:00:00.000000+00:00",
        "America/New_York",
        0,
        "2026-11-19T14:30:00.000000+00:00",
        30,
        "Europe/London",
        "owner",
        None,
        None,
        None,
        "2026-11-17T14:00:00.000000+00:00",
        "2026-11-17T16:00:00.000000+00:00",
    )


@pytest.mark.parametrize("column", ["source", "number", "updated_at"])
def test_an_unknown_update_column_is_refused_before_any_write(
    connection: sqlite3.Connection, column: str
) -> None:
    before = row(connection, 1)
    with pytest.raises(ValueError) as raised:
        _store_tasks.update_task(
            connection, 1, LATER, {"title": "Synthetic second title", column: "owner"}
        )
    assert str(raised.value) == "unknown task column"
    assert row(connection, 1) == before


@pytest.mark.parametrize("name", MOVED)
def test_the_store_keeps_no_migration_step(name: str) -> None:
    assert not hasattr(Store, name)


def test_each_open_migrates_once_through_the_module(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from docket import _store_migrate

    path = tmp_path / "docket.sqlite3"
    seen: list[Store] = []
    migrate = _store_migrate.migrate

    def counted(store: Store) -> None:
        seen.append(store)
        migrate(store)

    monkeypatch.setattr(_store_migrate, "migrate", counted)
    with Store(path) as first:
        assert seen == [first]
    with Store(path) as second:
        assert seen == [first, second]
    assert user_version(path) == 7


def test_the_store_has_no_other_way_to_migrate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from docket import _store_migrate

    path = tmp_path / "docket.sqlite3"
    monkeypatch.setattr(_store_migrate, "migrate", lambda store: None)
    Store(path).close()
    assert user_version(path) == 0
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("SELECT name FROM sqlite_master").fetchall() == []


def test_a_current_store_migrates_to_no_change(tmp_path: Path) -> None:
    from docket import _store_migrate

    path = tmp_path / "docket.sqlite3"
    with Store(path) as store:
        before = snapshot(path)
        _store_migrate.migrate(store)
        assert snapshot(path) == before
    assert user_version(path) == 7


def test_the_migration_module_owns_no_connection_and_no_task_sql() -> None:
    tree = ast.parse(MIGRATE_SOURCE.read_text())
    forbidden = {"connect", "close", "commit", "rollback", "executescript", "now"}
    called = {
        node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom | ast.Import)
        for alias in node.names
    }
    assert called & forbidden == set()
    assert "_store_tasks" not in names | imported
    assert "migrate" in {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
