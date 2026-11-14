import sqlite3
import stat
import threading
import time as wall
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from docket import clock
from docket.config import get_settings
from docket.deadlines import INSTANT_MESSAGE, Deadline, WorkTime
from docket.schema import SCHEMA_VERSION
from docket.store import (
    DB_FILENAME,
    NESTED_MESSAGE,
    SCHEMA_MESSAGE,
    TRANSACTION_MESSAGE,
    UNCHANGED,
    UNKNOWN_TASK_MESSAGE,
    AuditEntry,
    Store,
    StoreError,
    Task,
    open_store,
)

NY = "America/New_York"
T0 = datetime(2026, 11, 14, 9, 0, tzinfo=UTC)
T1 = datetime(2026, 11, 14, 9, 30, 0, 250000, tzinfo=UTC)
FRIDAY_5PM = Deadline(datetime(2026, 11, 20, 22, 0, tzinfo=UTC), NY, False)
FRIDAY_WORK = WorkTime(datetime(2026, 11, 20, 19, 0, tzinfo=UTC), 60, NY)


def mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def add(store: Store, title: str = "Pay rent", **fields: object) -> Task:
    values: dict[str, object] = {
        "title": title,
        "state": "open",
        "deadline": None,
        "work": None,
        "source": "owner",
        "provider": None,
        "message_id": None,
        "link": None,
        "at": T0,
    }
    values.update(fields)
    with store.transaction():
        return store.insert_task(**values)  # type: ignore[arg-type]


def raw(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(path, isolation_level=None)


@pytest.fixture
def path(tmp_path: Path) -> Path:
    return tmp_path / "docket.sqlite3"


@pytest.fixture
def store(path: Path):
    with Store(path) as opened:
        yield opened


def test_the_names() -> None:
    assert DB_FILENAME == "docket.sqlite3"
    assert SCHEMA_MESSAGE == "unsupported schema version"
    assert TRANSACTION_MESSAGE == "a write needs a transaction"
    assert NESTED_MESSAGE == "a transaction is already open"
    assert UNKNOWN_TASK_MESSAGE == "unknown task"
    assert SCHEMA_VERSION == 1


def test_opening_makes_a_private_file_in_wal_mode(store: Store, path: Path) -> None:
    add(store)
    assert mode(path) == 0o600
    assert mode(path.with_name("docket.sqlite3-wal")) == 0o600
    assert mode(path.with_name("docket.sqlite3-shm")) == 0o600
    connection = raw(path)
    assert connection.execute("PRAGMA user_version").fetchone() == (1,)
    assert connection.execute("PRAGMA journal_mode").fetchone() == ("wal",)


def test_an_existing_file_is_made_private(path: Path) -> None:
    path.touch()
    path.chmod(0o644)
    Store(path).close()
    assert mode(path) == 0o600


def test_opening_again_keeps_the_data(path: Path) -> None:
    with Store(path) as first:
        made = add(first)
    with Store(path) as second:
        assert second.task("t1") == made
        assert second.tasks() == [made]


def test_a_newer_schema_is_refused(path: Path) -> None:
    connection = raw(path)
    connection.execute("PRAGMA user_version = 99")
    connection.close()
    with pytest.raises(StoreError) as raised:
        Store(path)
    assert str(raised.value) == "unsupported schema version: 99"


def test_open_store_uses_the_private_data_folder(tmp_path: Path) -> None:
    with open_store(get_settings()) as opened:
        add(opened)
    assert mode(tmp_path / "data") == 0o700
    assert mode(tmp_path / "data" / "docket.sqlite3") == 0o600


def test_a_new_task_gets_the_next_short_id(store: Store) -> None:
    first = add(store)
    second = add(store, "Book flights", at=T1)
    assert first == Task(
        id="t1",
        title="Pay rent",
        state="open",
        deadline=None,
        work=None,
        source="owner",
        provider=None,
        message_id=None,
        link=None,
        created_at=T0,
        updated_at=T0,
    )
    assert (second.id, second.title, second.created_at) == ("t2", "Book flights", T1)
    assert store.task("t1") == first
    assert store.task("t2") == second


def test_deadlines_and_work_times_come_back_as_stored(store: Store) -> None:
    made = add(store, deadline=FRIDAY_5PM, work=FRIDAY_WORK)
    found = store.task(made.id)
    assert found is not None
    assert (found.deadline, found.work) == (FRIDAY_5PM, FRIDAY_WORK)
    assert found.deadline.at.tzinfo is UTC
    assert found.work.start.tzinfo is UTC
    assert found.created_at.tzinfo is UTC


def test_an_email_task_keeps_its_reference(store: Store) -> None:
    made = add(
        store,
        source="email",
        provider="gmail",
        message_id="personal/18c2f0a1",
        link="https://mail.example/18c2f0a1",
    )
    assert store.task(made.id) == made
    assert (made.source, made.provider, made.message_id, made.link) == (
        "email",
        "gmail",
        "personal/18c2f0a1",
        "https://mail.example/18c2f0a1",
    )


def test_the_stored_text_is_fixed(store: Store, path: Path) -> None:
    made = add(store, deadline=FRIDAY_5PM, work=FRIDAY_WORK, at=T1)
    with store.transaction():
        store.append_audit(
            made.id, at=T1, action="create", actor="owner", before={}, after={"state": "open"}
        )
    connection = raw(path)
    row = connection.execute(
        "SELECT number, title, state, deadline_at, deadline_zone, deadline_time_given,"
        " work_start, work_minutes, work_zone, source, created_at, updated_at FROM tasks"
    ).fetchone()
    assert row == (
        1,
        "Pay rent",
        "open",
        "2026-11-20T22:00:00.000000+00:00",
        "America/New_York",
        0,
        "2026-11-20T19:00:00.000000+00:00",
        60,
        "America/New_York",
        "owner",
        "2026-11-14T09:30:00.250000+00:00",
        "2026-11-14T09:30:00.250000+00:00",
    )
    audit = connection.execute("SELECT task, at, action, actor, before, after FROM audit_log")
    assert audit.fetchone() == (
        1,
        "2026-11-14T09:30:00.250000+00:00",
        "create",
        "owner",
        "{}",
        '{"state":"open"}',
    )


@pytest.mark.parametrize(
    "write",
    [
        lambda store: store.insert_task(
            title="Pay rent",
            state="open",
            deadline=None,
            work=None,
            source="owner",
            provider=None,
            message_id=None,
            link=None,
            at=T0,
        ),
        lambda store: store.update_task("t1", at=T1, state="done"),
        lambda store: store.append_audit(
            "t1", at=T1, action="done", actor="owner", before={}, after={}
        ),
    ],
    ids=["insert", "update", "audit"],
)
def test_a_write_needs_a_transaction(store: Store, write) -> None:
    made = add(store)
    with pytest.raises(StoreError) as raised:
        write(store)
    assert str(raised.value) == TRANSACTION_MESSAGE
    assert store.tasks() == [made]
    assert store.audit("t1") == []


def test_a_transaction_cannot_be_nested(store: Store) -> None:
    with store.transaction():
        with pytest.raises(StoreError) as raised:
            with store.transaction():
                pass
    assert str(raised.value) == NESTED_MESSAGE


def test_a_failed_transaction_leaves_nothing_and_no_lock(store: Store, path: Path) -> None:
    with pytest.raises(RuntimeError):
        with store.transaction():
            made = store.insert_task(
                title="Pay rent",
                state="open",
                deadline=None,
                work=None,
                source="owner",
                provider=None,
                message_id=None,
                link=None,
                at=T0,
            )
            store.append_audit(made.id, at=T0, action="create", actor="owner", before={}, after={})
            raise RuntimeError("stop")
    assert store.tasks() == []
    other = sqlite3.connect(path, timeout=0, isolation_level=None)
    other.execute("BEGIN IMMEDIATE")
    other.execute("ROLLBACK")
    assert add(store).id == "t1"


def test_a_transaction_holds_the_write_lock_until_it_ends(store: Store, path: Path) -> None:
    other = sqlite3.connect(path, timeout=0, isolation_level=None)
    with store.transaction():
        with pytest.raises(sqlite3.OperationalError) as raised:
            other.execute("BEGIN IMMEDIATE")
        assert str(raised.value) == "database is locked"
    other.execute("BEGIN IMMEDIATE")
    other.execute("ROLLBACK")


def test_another_store_sees_only_committed_tasks(store: Store, path: Path) -> None:
    with Store(path) as other:
        with store.transaction():
            store.insert_task(
                title="Pay rent",
                state="open",
                deadline=None,
                work=None,
                source="owner",
                provider=None,
                message_id=None,
                link=None,
                at=T0,
            )
            assert other.task("t1") is None
            assert other.tasks() == []
        assert [task.id for task in other.tasks()] == ["t1"]


def test_a_second_writer_waits_for_the_first(store: Store, path: Path) -> None:
    found: list[str] = []

    def second() -> None:
        with Store(path) as other:
            found.append(add(other, "Book flights").id)

    with store.transaction():
        store.insert_task(
            title="Pay rent",
            state="open",
            deadline=None,
            work=None,
            source="owner",
            provider=None,
            message_id=None,
            link=None,
            at=T0,
        )
        thread = threading.Thread(target=second)
        thread.start()
        wall.sleep(0.5)
        assert found == []
    thread.join(timeout=10)
    assert found == ["t2"]
    assert [task.id for task in store.tasks()] == ["t1", "t2"]


def test_an_update_changes_only_what_it_names(store: Store) -> None:
    made = add(store, deadline=FRIDAY_5PM, work=FRIDAY_WORK)
    with store.transaction():
        changed = store.update_task(made.id, at=T1, state="in_progress")
    assert changed == Task(
        id="t1",
        title="Pay rent",
        state="in_progress",
        deadline=FRIDAY_5PM,
        work=FRIDAY_WORK,
        source="owner",
        provider=None,
        message_id=None,
        link=None,
        created_at=T0,
        updated_at=T1,
    )
    assert store.task("t1") == changed


def test_an_update_can_set_and_clear_every_field(store: Store) -> None:
    made = add(store)
    with store.transaction():
        store.update_task(made.id, at=T1, title="Pay rent today", deadline=FRIDAY_5PM)
        store.update_task(made.id, at=T1, work=FRIDAY_WORK)
    found = store.task(made.id)
    assert found is not None
    assert (found.title, found.deadline, found.work) == ("Pay rent today", FRIDAY_5PM, FRIDAY_WORK)
    with store.transaction():
        cleared = store.update_task(made.id, at=T1, deadline=None, work=None)
    assert (cleared.deadline, cleared.work) == (None, None)
    assert UNCHANGED is not None


@pytest.mark.parametrize(
    "task_id", ["t9", "t0", "1", "x1"], ids=["missing", "zero", "bare", "other"]
)
def test_an_unknown_task_cannot_be_written(store: Store, task_id: str) -> None:
    add(store)
    with store.transaction():
        with pytest.raises(StoreError) as raised:
            store.update_task(task_id, at=T1, state="done")
        assert str(raised.value) == UNKNOWN_TASK_MESSAGE
        with pytest.raises(StoreError) as raised:
            store.append_audit(task_id, at=T1, action="done", actor="owner", before={}, after={})
        assert str(raised.value) == UNKNOWN_TASK_MESSAGE


@pytest.mark.parametrize(
    "task_id",
    ["t2", "t0", "t01", "T1", "1", "t1 ", " t1", "t-1", "t", "", "t1\n", "t١"],
    ids=[
        "missing",
        "zero",
        "leading-zero",
        "capital",
        "bare-number",
        "trailing-space",
        "leading-space",
        "negative",
        "letter-only",
        "empty",
        "newline",
        "arabic-indic-digit",
    ],
)
def test_a_lookup_by_an_unknown_or_malformed_id_finds_nothing(store: Store, task_id: str) -> None:
    add(store)
    assert store.task(task_id) is None
    assert store.audit(task_id) == []


def test_tasks_are_listed_in_order_and_filtered_by_state(store: Store) -> None:
    add(store, "One")
    add(store, "Two", state="done")
    add(store, "Three", state="in_progress")
    add(store, "Four")
    assert [task.title for task in store.tasks()] == ["One", "Two", "Three", "Four"]
    assert [task.title for task in store.tasks({"open"})] == ["One", "Four"]
    assert [task.title for task in store.tasks({"open", "in_progress"})] == ["One", "Three", "Four"]
    assert store.tasks({"cancelled"}) == []
    assert store.tasks(set()) == []


def test_audit_entries_come_back_in_order(store: Store) -> None:
    made = add(store)
    add(store, "Other")
    with store.transaction():
        first = store.append_audit(
            made.id, at=T0, action="create", actor="email", before={}, after={"title": "Pay rent"}
        )
        store.append_audit("t2", at=T0, action="create", actor="owner", before={}, after={})
        second = store.append_audit(
            made.id,
            at=T1,
            action="deadline",
            actor="agent",
            before={"deadline": None},
            after={"deadline": {"at": "2026-11-20T22:00:00+00:00", "zone": NY}},
        )
    assert first == AuditEntry(
        task_id="t1",
        at=T0,
        action="create",
        actor="email",
        before={},
        after={"title": "Pay rent"},
    )
    assert store.audit("t1") == [first, second]
    assert second.after == {"deadline": {"at": "2026-11-20T22:00:00+00:00", "zone": NY}}
    assert store.audit("t1")[1].at.tzinfo is UTC


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE audit_log SET actor = 'agent'",
        "DELETE FROM audit_log",
        "DELETE FROM tasks",
    ],
    ids=["change-audit", "remove-audit", "remove-task"],
)
def test_the_record_cannot_be_rewritten(store: Store, path: Path, sql: str) -> None:
    made = add(store)
    with store.transaction():
        store.append_audit(made.id, at=T0, action="create", actor="owner", before={}, after={})
    with pytest.raises(sqlite3.IntegrityError):
        raw(path).execute(sql)
    assert len(store.audit(made.id)) == 1
    assert store.task(made.id) == made


@pytest.mark.parametrize(
    "fields",
    [
        {"state": "late"},
        {"title": ""},
        {"title": "x" * 101},
        {"source": "camera"},
        {"source": "email"},
        {"provider": "gmail", "message_id": "personal/1", "link": "https://mail.example/1"},
    ],
    ids=[
        "state",
        "empty-title",
        "long-title",
        "source",
        "email-without-reference",
        "reference-on-owner",
    ],
)
def test_the_schema_refuses_a_bad_task(store: Store, fields: dict[str, object]) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        add(store, **fields)
    assert store.tasks() == []


@pytest.mark.parametrize(
    "at",
    [
        datetime(2026, 11, 14, 9, 0),
        datetime(2026, 11, 14, 4, 0, tzinfo=ZoneInfo(NY)),
    ],
    ids=["naive", "new-york"],
)
def test_a_written_instant_must_be_utc(store: Store, at: datetime) -> None:
    add(store)
    with pytest.raises(StoreError) as raised:
        add(store, at=at)
    assert str(raised.value) == INSTANT_MESSAGE
    with store.transaction():
        with pytest.raises(StoreError) as raised:
            store.update_task("t1", at=at, state="done")
        assert str(raised.value) == INSTANT_MESSAGE
        with pytest.raises(StoreError) as raised:
            store.append_audit("t1", at=at, action="done", actor="owner", before={}, after={})
        assert str(raised.value) == INSTANT_MESSAGE
    assert [task.state for task in store.tasks()] == ["open"]


def test_the_store_never_reads_the_clock(store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse() -> datetime:
        raise AssertionError("the store read the clock")

    monkeypatch.setattr(clock, "now", refuse)
    made = add(store)
    with store.transaction():
        store.update_task(made.id, at=T1, state="done")
        store.append_audit(made.id, at=T1, action="done", actor="owner", before={}, after={})
    assert store.task(made.id) is not None
