import sqlite3
from pathlib import Path

import pytest

from docket import schema
from docket import store as store_module
from docket.intake import Answer, accept_link, accept_task
from docket.store import Store, StoreError
from tests.reference_cases import BODY, LINK, NOW, snapshot, version_two
from tests.support import fixed_times


@pytest.mark.parametrize("start", [0, 2], ids=["new", "populated-v2"])
def test_migration_preserves_rows_ids_sequences_and_invariants(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, start: int
) -> None:
    path = tmp_path / "docket.sqlite3"
    if start == 2:
        version_two(path)
        before = snapshot(path)
    with Store(path) as opened:
        if start == 2:
            assert snapshot(path) == before
            fixed_times(monkeypatch, NOW, NOW)
            assert accept_task(opened, client="email", key="task-key", body=BODY) == Answer(
                200, {"id": "t1"}
            )
            assert accept_link(opened, "t1", client="email", key="link-key", body=LINK) == Answer(
                200, {"id": "l1"}
            )
            assert snapshot(path) == before
            with opened.transaction():
                made = opened.insert_link(
                    "t1",
                    provider="gmail",
                    message_id="next",
                    link="next",
                    at=opened.task("t1").created_at,
                )
            assert made.id == "l3"
    db = sqlite3.connect(path, isolation_level=None)
    try:
        assert db.execute("PRAGMA user_version").fetchone() == (4,)
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        if start == 2:
            with pytest.raises(sqlite3.IntegrityError, match="tasks are never removed"):
                db.execute("DELETE FROM tasks WHERE number=1")
            with pytest.raises(sqlite3.IntegrityError, match="audit rows are never changed"):
                db.execute("UPDATE audit_log SET action='done'")
            with pytest.raises(sqlite3.IntegrityError, match="audit rows are never removed"):
                db.execute("DELETE FROM audit_log")
    finally:
        db.close()


@pytest.mark.parametrize(("table", "identifier"), [("tasks", "t1"), ("links", "l1")])
@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("message_id", "x" * 513),
        ("link", "x" * 2049),
        ("message_id", "bad\x1b[2J"),
        ("link", "bad\u200dformat"),
        ("message_id", "bad\u2028line"),
        ("link", "bad\u2029paragraph"),
        ("link", "bad\nline"),
        ("message_id", "bad\x00tail"),
    ],
    ids=["id-long", "link-long", "escape", "format", "line", "paragraph", "newline", "nul"],
)
def test_invalid_legacy_reference_refuses_without_data_changes(
    tmp_path: Path, table: str, identifier: str, field: str, bad: str
) -> None:
    path = tmp_path / "docket.sqlite3"
    version_two(path)
    with sqlite3.connect(path) as db:
        db.execute(f"UPDATE {table} SET {field}=? WHERE number=1", (bad,))
    before = snapshot(path)
    with pytest.raises(StoreError) as raised:
        Store(path)
    assert str(raised.value) == f"invalid stored reference: {identifier} {field}"
    assert snapshot(path) == before
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone() == (2,)
        assert (
            db.execute("SELECT name FROM sqlite_master WHERE name LIKE '%bounded%'").fetchall()
            == []
        )


@pytest.mark.parametrize("table", ["tasks", "links"])
@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("message_id", "x" * 513),
        ("link", "x" * 2049),
        ("message_id", "x\x00" + "x" * 513),
        ("link", "x\x00" + "x" * 2049),
    ],
    ids=["id-long", "link-long", "nul-id-bypass", "nul-link-bypass"],
)
def test_sql_update_cannot_bypass_reference_length_checks(
    tmp_path: Path, table: str, field: str, bad: str
) -> None:
    path = tmp_path / "docket.sqlite3"
    with Store(path) as opened:
        from datetime import UTC, datetime
        from unittest.mock import patch

        from docket import core

        with patch("docket.clock.now", return_value=datetime(2026, 11, 17, 14, tzinfo=UTC)):
            core.create_task(
                opened,
                title="Synthetic reference task",
                source="email",
                provider="gmail",
                message_id="synthetic/1",
                link="https://mail.example/1",
            )
            core.add_link(
                opened,
                "t1",
                client="email",
                key="l",
                request=LINK,
                provider="gmail",
                message_id="synthetic/2",
                link="https://mail.example/2",
            )
    with sqlite3.connect(path) as db:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(f"UPDATE {table} SET {field}=? WHERE number=1", (bad,))


def test_failed_migration_rolls_back_closes_and_restores_foreign_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "docket.sqlite3"
    version_two(path)
    before = snapshot(path)
    closed = []
    restored = []
    connect = sqlite3.connect

    class Tracked(sqlite3.Connection):
        def close(self) -> None:
            restored.append(self.execute("PRAGMA foreign_keys").fetchone()[0])
            closed.append(True)
            super().close()

    monkeypatch.setattr(
        store_module.sqlite3, "connect", lambda *a, **k: connect(*a, **k, factory=Tracked)
    )
    monkeypatch.setattr(
        store_module,
        "MIGRATIONS",
        (
            schema.MIGRATION_1,
            schema.MIGRATION_2,
            schema.MIGRATION_3 + "\nSELECT missing_function();",
        ),
    )
    with pytest.raises(sqlite3.OperationalError):
        Store(path)
    assert closed == [True]
    assert restored == [1]
    monkeypatch.setattr(store_module.sqlite3, "connect", connect)
    assert snapshot(path) == before
    with connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone() == (2,)


def test_foreign_key_check_failure_refuses_the_upgrade(tmp_path: Path) -> None:
    path = tmp_path / "docket.sqlite3"
    version_two(path)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE request_keys SET task=999 WHERE key='task-key'")
    before = snapshot(path)
    with pytest.raises(StoreError, match="^invalid reference migration$"):
        Store(path)
    assert snapshot(path) == before
