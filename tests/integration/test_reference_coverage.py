import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from docket.schema import MIGRATION_1
from docket.store import Store, StoreError
from tests.reference_cases import STAMP, snapshot, version_two
from tests.support import fixed_times

AT = datetime(2026, 11, 17, 14, tzinfo=UTC)
EXACT_ID = "é" * 512
EXACT_LINK = "x" * 2048


def test_upgraded_connection_rejects_a_link_with_no_task(tmp_path: Path) -> None:
    path = tmp_path / "docket.sqlite3"
    version_two(path)
    with Store(path) as opened:
        before = opened.links("t1")
        with pytest.raises(sqlite3.IntegrityError):
            opened._connection.execute(
                "INSERT INTO links (task, provider, message_id, link, created_at) "
                "VALUES (999, 'gmail', 'synthetic/missing', 'https://mail.example/missing', ?)",
                (STAMP,),
            )
        assert opened.links("t1") == before


def test_preflight_refusal_closes_once_and_reads_no_clock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "docket.sqlite3"
    version_two(path)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE tasks SET link=? WHERE number=1", ("bad\nline",))
    before = snapshot(path)
    closed: list[bool] = []
    restored: list[int] = []
    connect = sqlite3.connect

    class Tracked(sqlite3.Connection):
        def close(self) -> None:
            restored.append(self.execute("PRAGMA foreign_keys").fetchone()[0])
            closed.append(True)
            super().close()

    monkeypatch.setattr(
        "docket.store.sqlite3.connect",
        lambda *args, **kwargs: connect(*args, **kwargs, factory=Tracked),
    )
    fixed_times(monkeypatch)
    with pytest.raises(StoreError, match="^invalid stored reference: t1 link$"):
        Store(path)
    assert closed == [True]
    assert restored == [1]
    assert snapshot(path) == before
    with connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone() == (2,)


def test_exact_cap_and_non_email_rows_upgrade_unchanged(tmp_path: Path) -> None:
    path = tmp_path / "docket.sqlite3"
    version_two(path)
    with sqlite3.connect(path) as db:
        db.execute(
            "UPDATE tasks SET message_id=?, link=? WHERE number=1",
            (EXACT_ID, EXACT_LINK),
        )
        db.execute("UPDATE links SET message_id=?, link=? WHERE number=1", (EXACT_ID, EXACT_LINK))
        db.execute(
            "INSERT INTO tasks(title,state,source,created_at,updated_at) "
            "VALUES ('Synthetic owner task','open','owner',?,?)",
            (STAMP, STAMP),
        )
    before = snapshot(path)
    with Store(path) as opened:
        task = opened.task("t1")
        owner = opened.task("t2")
        assert task is not None and owner is not None
        assert (task.message_id, task.link) == (EXACT_ID, EXACT_LINK)
        assert (owner.message_id, owner.link) == (None, None)
        assert opened.links("t1")[0].message_id == EXACT_ID
        assert opened.links("t1")[0].link == EXACT_LINK
    assert snapshot(path) == before


def test_version_one_keeps_its_rows_through_every_migration(tmp_path: Path) -> None:
    path = tmp_path / "docket.sqlite3"
    db = sqlite3.connect(path, isolation_level=None)
    db.executescript(MIGRATION_1)
    db.execute(
        "INSERT INTO tasks(title,state,source,provider,message_id,link,created_at,updated_at) "
        "VALUES ('Synthetic reference task','done','email','outlook',?,? ,?,?)",
        (EXACT_ID, EXACT_LINK, STAMP, STAMP),
    )
    db.execute(
        "INSERT INTO audit_log(task,at,action,actor,before,after) "
        "VALUES (1,?,'create','email','{}','{\"title\":\"Synthetic reference task\"}')",
        (STAMP,),
    )
    db.execute("PRAGMA user_version = 1")
    tasks_before = db.execute("SELECT * FROM tasks ORDER BY 1").fetchall()
    audit_before = db.execute("SELECT * FROM audit_log ORDER BY 1").fetchall()
    db.close()
    with Store(path) as opened:
        task = opened.task("t1")
        assert task is not None
        assert (task.state, task.message_id, task.link) == ("done", EXACT_ID, EXACT_LINK)
        assert len(opened.audit("t1")) == 1
        assert opened.links("t1") == []
    after = snapshot(path)
    assert after["tasks"] == tasks_before
    assert after["audit_log"] == audit_before
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone() == (4,)


def test_direct_store_writes_keep_valid_references_and_roll_back_overlong_ones(
    tmp_path: Path,
) -> None:
    path = tmp_path / "docket.sqlite3"
    with Store(path) as opened:
        with opened.transaction():
            opened.insert_task(
                title="Synthetic reference task",
                state="open",
                deadline=None,
                work=None,
                source="email",
                provider="gmail",
                message_id=EXACT_ID,
                link=EXACT_LINK,
                at=AT,
            )
            opened.append_audit(
                "t1",
                at=AT,
                action="create",
                actor="email",
                before={},
                after={"title": "Synthetic reference task"},
            )
        task = opened.task("t1")
        assert task is not None
        assert (task.message_id, task.link) == (EXACT_ID, EXACT_LINK)
        assert len(opened.audit("t1")) == 1
        with pytest.raises(sqlite3.IntegrityError):
            with opened.transaction():
                opened.append_audit(
                    "t1",
                    at=AT,
                    action="start",
                    actor="email",
                    before={"state": "open"},
                    after={"state": "in_progress"},
                )
                opened.insert_task(
                    title="Synthetic overlong task",
                    state="open",
                    deadline=None,
                    work=None,
                    source="email",
                    provider="gmail",
                    message_id="x" * 513,
                    link=EXACT_LINK,
                    at=AT,
                )
        assert [item.id for item in opened.tasks()] == ["t1"]
        assert [item.action for item in opened.audit("t1")] == ["create"]
        with pytest.raises(sqlite3.IntegrityError):
            with opened.transaction():
                opened.insert_request_key(
                    client="email",
                    key="overlong",
                    request={"source": "email"},
                    task_id="t1",
                    link_id=None,
                    at=AT,
                )
                opened.insert_link(
                    "t1",
                    provider="gmail",
                    message_id=EXACT_ID,
                    link="y" * 2049,
                    at=AT,
                )
        assert opened.links("t1") == []
        assert opened.request_key("email", "overlong") is None


def test_preflight_names_the_earliest_task_field(tmp_path: Path) -> None:
    path = tmp_path / "docket.sqlite3"
    version_two(path)
    with sqlite3.connect(path) as db:
        db.execute(
            "INSERT INTO tasks(title,state,source,provider,message_id,link,created_at,updated_at) "
            "VALUES ('Synthetic second task','cancelled','email','yahoo','bad\nline',"
            "'bad\u2028line',?,?)",
            (STAMP, STAMP),
        )
        db.execute("UPDATE links SET message_id=? WHERE number=1", ("bad\x00tail",))
    before = snapshot(path)
    with pytest.raises(StoreError, match="^invalid stored reference: t2 message_id$"):
        Store(path)
    assert snapshot(path) == before
