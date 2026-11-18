import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from docket.deadlines import INSTANT_MESSAGE
from docket.schema import MIGRATIONS
from docket.store import (
    TRANSACTION_MESSAGE,
    UNKNOWN_LINK_MESSAGE,
    UNKNOWN_TASK_MESSAGE,
    Link,
    RequestKey,
    Store,
    StoreError,
)
from tests.support import path as path
from tests.support import store as base_store

__all__ = ["base_store"]

T0 = datetime(2026, 11, 14, 9, 0, tzinfo=UTC)
T1 = datetime(2026, 11, 14, 9, 30, 0, 250000, tzinfo=UTC)
GMAIL = {"provider": "gmail", "message_id": "personal/18c2f0a2", "link": "https://mail.example/2"}


@pytest.fixture
def store(base_store: Store):
    with base_store.transaction():
        for title in ("Pay rent", "Book flights"):
            base_store.insert_task(
                title=title,
                state="open",
                deadline=None,
                work=None,
                source="owner",
                provider=None,
                message_id=None,
                link=None,
                at=T0,
            )
    yield base_store


def test_the_names() -> None:
    assert UNKNOWN_LINK_MESSAGE == "unknown link"
    assert len(MIGRATIONS) == 6


def test_links_are_numbered_and_listed_per_task(store: Store) -> None:
    with store.transaction():
        first = store.insert_link("t1", at=T0, **GMAIL)
        other = store.insert_link(
            "t2",
            at=T1,
            provider="outlook",
            message_id="home/AAMk1",
            link="https://outlook.example/1",
        )
        second = store.insert_link(
            "t1",
            at=T1,
            provider="yahoo",
            message_id="main/4f2a",
            link="https://mail.yahoo.example/",
        )
    assert first == Link(
        id="l1",
        task_id="t1",
        provider="gmail",
        message_id="personal/18c2f0a2",
        link="https://mail.example/2",
        created_at=T0,
    )
    assert (other.id, second.id) == ("l2", "l3")
    assert store.links("t1") == [first, second]
    assert store.links("t2") == [other]
    assert store.links("t1")[0].created_at.tzinfo is UTC


@pytest.mark.parametrize("task_id", ["t9", "t0", "x", "", "T1"])
def test_links_of_an_unknown_task_are_none(store: Store, task_id: str) -> None:
    with store.transaction():
        store.insert_link("t1", at=T0, **GMAIL)
    assert store.links(task_id) == []


def test_a_link_write_follows_the_store_rules(store: Store) -> None:
    with pytest.raises(StoreError) as raised:
        store.insert_link("t1", at=T0, **GMAIL)
    assert str(raised.value) == TRANSACTION_MESSAGE
    with store.transaction():
        with pytest.raises(StoreError) as raised:
            store.insert_link(
                "t1", at=datetime(2026, 11, 14, 4, 0, tzinfo=ZoneInfo("UTC")), **GMAIL
            )
        assert str(raised.value) == INSTANT_MESSAGE
        with pytest.raises(StoreError) as raised:
            store.insert_link("t9", at=T0, **GMAIL)
        assert str(raised.value) == UNKNOWN_TASK_MESSAGE
    assert store.links("t1") == []


def test_a_request_key_records_its_request_and_result(store: Store) -> None:
    request = {"title": "Pay rent", "deadline": {"date": "2026-11-20", "time": None}}
    assert store.request_key("email", "gmail:personal/1") is None
    with store.transaction():
        link = store.insert_link("t1", at=T0, **GMAIL)
        made = store.insert_request_key(
            client="email",
            key="gmail:personal/1",
            request=request,
            task_id="t1",
            link_id=None,
            at=T0,
        )
        linked = store.insert_request_key(
            client="email",
            key="gmail:personal/2",
            request=GMAIL,
            task_id="t1",
            link_id=link.id,
            at=T1,
        )
    assert made == RequestKey(
        client="email",
        key="gmail:personal/1",
        request=request,
        task_id="t1",
        link_id=None,
        created_at=T0,
    )
    assert store.request_key("email", "gmail:personal/1") == made
    assert store.request_key("email", "gmail:personal/2") == linked
    assert linked.link_id == "l1"


def test_a_key_is_scoped_to_its_client(store: Store) -> None:
    with store.transaction():
        store.insert_request_key(
            client="email", key="same", request={"a": 1}, task_id="t1", link_id=None, at=T0
        )
        store.insert_request_key(
            client="agent", key="same", request={"a": 2}, task_id="t2", link_id=None, at=T0
        )
    found = (store.request_key("email", "same"), store.request_key("agent", "same"))
    assert [(key.task_id, key.request) for key in found] == [("t1", {"a": 1}), ("t2", {"a": 2})]
    assert store.request_key("owner", "same") is None


def test_the_stored_request_text_is_canonical(store: Store, path: Path) -> None:
    with store.transaction():
        store.insert_request_key(
            client="email",
            key="gmail:personal/1",
            request={"title": "Café", "deadline": None, "a": [1, 2]},
            task_id="t1",
            link_id=None,
            at=T1,
        )
    row = sqlite3.connect(path).execute("SELECT * FROM request_keys").fetchone()
    assert row == (
        "email",
        "gmail:personal/1",
        '{"a":[1,2],"deadline":null,"title":"Café"}',
        1,
        None,
        "2026-11-14T09:30:00.250000+00:00",
    )


def test_a_request_key_write_follows_the_store_rules(store: Store) -> None:
    def write(**fields: object) -> None:
        values: dict[str, object] = {
            "client": "email",
            "key": "k",
            "request": {},
            "task_id": "t1",
            "link_id": None,
            "at": T0,
        }
        values.update(fields)
        store.insert_request_key(**values)  # type: ignore[arg-type]

    with pytest.raises(StoreError) as raised:
        write()
    assert str(raised.value) == TRANSACTION_MESSAGE
    with store.transaction():
        for fields, message in [
            ({"at": datetime(2026, 11, 14, 9, 0)}, INSTANT_MESSAGE),
            ({"task_id": "t9"}, UNKNOWN_TASK_MESSAGE),
            ({"link_id": "l9"}, UNKNOWN_LINK_MESSAGE),
            ({"link_id": "x"}, UNKNOWN_LINK_MESSAGE),
        ]:
            with pytest.raises(StoreError) as raised:
                write(**fields)
            assert str(raised.value) == message
    assert store.request_key("email", "k") is None


@pytest.mark.parametrize(
    "fields",
    [{"client": "camera"}, {"key": ""}, {"key": "k" * 201}, {"client": "agent", "link_id": "l1"}],
    ids=["client", "empty-key", "long-key", "agent-with-a-link"],
)
def test_the_schema_refuses_a_bad_key(store: Store, fields: dict[str, object]) -> None:
    values: dict[str, object] = {
        "client": "email",
        "key": "k",
        "request": {},
        "task_id": "t1",
        "link_id": None,
        "at": T0,
    }
    values.update(fields)
    with pytest.raises(sqlite3.IntegrityError):
        with store.transaction():
            store.insert_link("t1", at=T0, **GMAIL)
            store.insert_request_key(**values)  # type: ignore[arg-type]
    assert store.links("t1") == []


def test_a_key_is_used_once_per_client(store: Store) -> None:
    with store.transaction():
        store.insert_request_key(
            client="email", key="k", request={}, task_id="t1", link_id=None, at=T0
        )
    with pytest.raises(sqlite3.IntegrityError):
        with store.transaction():
            store.insert_request_key(
                client="email", key="k", request={}, task_id="t2", link_id=None, at=T1
            )
    found = store.request_key("email", "k")
    assert found is not None and found.task_id == "t1"


def test_a_version_1_database_moves_to_version_2_keeping_its_tasks(path: Path) -> None:
    connection = sqlite3.connect(path, isolation_level=None)
    connection.executescript(MIGRATIONS[0])
    stamp = "2026-11-13T13:00:00.000000+00:00"
    connection.execute(
        "INSERT INTO tasks (title, state, source, created_at, updated_at)"
        " VALUES ('Pay rent', 'open', 'owner', ?, ?)",
        (stamp, stamp),
    )
    connection.execute("PRAGMA user_version = 1")
    connection.close()
    with Store(path) as opened:
        assert [task.title for task in opened.tasks()] == ["Pay rent"]
        with opened.transaction():
            opened.insert_link("t1", at=T0, **GMAIL)
        assert [link.id for link in opened.links("t1")] == ["l1"]
    assert sqlite3.connect(path).execute("PRAGMA user_version").fetchone() == (6,)


def test_links_and_keys_can_be_pruned_but_tasks_cannot(store: Store, path: Path) -> None:
    with store.transaction():
        link = store.insert_link("t1", at=T0, **GMAIL)
        store.insert_request_key(
            client="email", key="k", request={}, task_id="t1", link_id=link.id, at=T0
        )
    raw = sqlite3.connect(path, isolation_level=None)
    raw.execute("DELETE FROM request_keys")
    raw.execute("DELETE FROM links")
    assert (store.links("t1"), store.request_key("email", "k")) == ([], None)
    with pytest.raises(sqlite3.IntegrityError):
        raw.execute("DELETE FROM tasks")
