"""Phase 5a: every stored row decodes through one check, and the store's files are private."""

import os
import sqlite3
import stat
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

import pytest

from docket import core
from docket.store import Store, StoreError
from tests.reference_cases import snapshot
from tests.support import fixed_times

NOW = "2026-11-17T14:00:00+00:00"
STAMP = "2026-11-17T14:00:00.000000+00:00"
MARK = "Phase 5a given test: remove this marker when store decoding is shared"
BAD_TIMES = [
    "synthetic-invalid-instant",
    "2026-11-17T14:00:00",
    "2026-11-17T09:00:00-05:00",
]
BAD_TIME_IDS = ["unparseable", "naive", "non-utc"]
REQUEST = '{"tool": "create_task", "title": "Synthetic keyed task", "deadline": null}'


@pytest.fixture
def opened(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[Store, Path]]:
    """t1 exists with its create audit row; the clock allows no further reads."""
    path = tmp_path / "docket.sqlite3"
    fixed_times(monkeypatch, NOW)
    with Store(path) as store:
        core.create_task(store, title="Synthetic stored task", source="owner")
        fixed_times(monkeypatch)
        yield store, path


def plant(path: Path, sql: str, values: tuple[object, ...]) -> dict[str, list[tuple]]:
    with closing(sqlite3.connect(path)) as db, db:
        db.execute(sql, values)
    return snapshot(path)


def refused_quietly(message: str, call) -> None:
    with pytest.raises(StoreError) as raised:
        call()
    assert str(raised.value) == message
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None or raised.value.__suppress_context__


def mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


@pytest.mark.parametrize(
    ("at", "before", "after"),
    [
        *((bad, "{}", "{}") for bad in BAD_TIMES),
        (STAMP, "{not json", "{}"),
        (STAMP, "{}", "{not json"),
        (STAMP, "[]", "{}"),
        (STAMP, "{}", "null"),
        (STAMP, '"synthetic text"', "{}"),
    ],
    ids=[*BAD_TIME_IDS, "before-not-json", "after-not-json", "list", "null", "string"],
)
def test_a_bad_audit_row_is_refused_without_library_text(
    opened: tuple[Store, Path], at: str, before: str, after: str
) -> None:
    store, path = opened
    planted = plant(
        path,
        "INSERT INTO audit_log (task, at, action, actor, before, after) "
        "VALUES (1, ?, 'retitle', 'owner', ?, ?)",
        (at, before, after),
    )
    refused_quietly("invalid stored audit entry: t1", lambda: store.audit("t1"))
    assert snapshot(path) == planted


@pytest.mark.parametrize("created_at", BAD_TIMES, ids=BAD_TIME_IDS)
def test_a_bad_link_row_is_refused_without_library_text(
    opened: tuple[Store, Path], created_at: str
) -> None:
    store, path = opened
    plant(
        path,
        "INSERT INTO links (task, provider, message_id, link, created_at) "
        "VALUES (1, 'gmail', 'synthetic-message-1', 'https://mail.example.test/1', ?)",
        (STAMP,),
    )
    planted = plant(
        path,
        "INSERT INTO links (task, provider, message_id, link, created_at) "
        "VALUES (1, 'gmail', 'synthetic-message-2', 'https://mail.example.test/2', ?)",
        (created_at,),
    )
    refused_quietly("invalid stored link: l2", lambda: store.links("t1"))
    assert snapshot(path) == planted


@pytest.mark.parametrize(
    ("request_text", "created_at"),
    [
        *((REQUEST, bad) for bad in BAD_TIMES),
        ("{not json", STAMP),
        ("[]", STAMP),
        ("null", STAMP),
        ("7", STAMP),
    ],
    ids=[*BAD_TIME_IDS, "not-json", "list", "null", "number"],
)
def test_a_bad_request_key_row_is_refused_without_library_text(
    opened: tuple[Store, Path], request_text: str, created_at: str
) -> None:
    store, path = opened
    planted = plant(
        path,
        "INSERT INTO request_keys (client, key, request, task, link, created_at) "
        "VALUES ('agent', 'run-1:step-1', ?, 1, NULL, ?)",
        (request_text, created_at),
    )
    refused_quietly(
        "invalid stored request key: t1", lambda: store.request_key("agent", "run-1:step-1")
    )
    assert snapshot(path) == planted


def test_a_keyed_retry_over_a_bad_key_row_writes_nothing(
    opened: tuple[Store, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    store, path = opened
    planted = plant(
        path,
        "INSERT INTO request_keys (client, key, request, task, link, created_at) "
        "VALUES ('agent', 'run-1:step-1', '{not json', 1, NULL, ?)",
        (STAMP,),
    )
    fixed_times(monkeypatch, NOW)
    refused_quietly(
        "invalid stored request key: t1",
        lambda: core.create_task_once(
            store,
            client="agent",
            key="run-1:step-1",
            request={"tool": "create_task", "title": "Synthetic keyed task", "deadline": None},
            title="Synthetic keyed task",
            source="agent",
        ),
    )
    assert snapshot(path) == planted


def test_good_audit_link_and_key_rows_still_decode(opened: tuple[Store, Path]) -> None:
    store, path = opened
    plant(
        path,
        "INSERT INTO links (task, provider, message_id, link, created_at) "
        "VALUES (1, 'gmail', 'synthetic-message-1', 'https://mail.example.test/1', ?)",
        ("2026-11-17T14:00:00Z",),
    )
    plant(
        path,
        "INSERT INTO request_keys (client, key, request, task, link, created_at) "
        "VALUES ('email', 'synthetic-key', ?, 1, 1, ?)",
        (REQUEST, STAMP),
    )
    (entry,) = store.audit("t1")
    assert (entry.task_id, entry.at.isoformat(), entry.action, entry.before) == (
        "t1",
        "2026-11-17T14:00:00+00:00",
        "create",
        {},
    )
    (link,) = store.links("t1")
    assert (link.id, link.created_at.isoformat()) == ("l1", "2026-11-17T14:00:00+00:00")
    found = store.request_key("email", "synthetic-key")
    assert found is not None
    assert (found.request, found.task_id, found.link_id, found.created_at.isoformat()) == (
        {"tool": "create_task", "title": "Synthetic keyed task", "deadline": None},
        "t1",
        "l1",
        "2026-11-17T14:00:00+00:00",
    )


def test_a_new_database_is_private_before_sqlite_opens_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from docket import store as store_module

    path = tmp_path / "docket.sqlite3"
    seen: list[int | None] = []
    connect = sqlite3.connect

    def watched(*args: object, **kwargs: object) -> sqlite3.Connection:
        seen.append(mode(path) if path.exists() else None)
        return connect(*args, **kwargs)

    monkeypatch.setattr(store_module.sqlite3, "connect", watched)
    previous = os.umask(0o022)
    try:
        Store(path).close()
    finally:
        os.umask(previous)
    assert (seen, mode(path)) == ([0o600], 0o600)


def test_leftover_wal_and_shm_files_are_made_private(tmp_path: Path) -> None:
    path = tmp_path / "docket.sqlite3"
    Store(path).close()
    with closing(sqlite3.connect(path)) as writer:
        writer.execute("PRAGMA journal_mode = WAL")
        writer.execute("PRAGMA wal_autocheckpoint = 0")
        with writer:
            writer.execute(
                "INSERT INTO tasks (title, state, source, created_at, updated_at) "
                "VALUES ('Synthetic WAL task', 'open', 'owner', ?, ?)",
                (STAMP, STAMP),
            )
        wal = tmp_path / "docket.sqlite3-wal"
        shm = tmp_path / "docket.sqlite3-shm"
        wal.chmod(0o644)
        shm.chmod(0o644)
        with Store(path) as store:
            assert [task.title for task in store.tasks()] == ["Synthetic WAL task"]
            assert (mode(path), mode(wal), mode(shm)) == (0o600, 0o600, 0o600)


def test_a_side_file_that_vanishes_before_its_chmod_is_not_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "docket.sqlite3"
    Store(path).close()
    for side in ("-wal", "-shm"):
        (tmp_path / f"docket.sqlite3{side}").write_bytes(b"")
    chmod = os.chmod

    def vanishing(file: object, *args: object, **kwargs: object) -> None:
        if str(file).endswith(("-wal", "-shm")):
            raise FileNotFoundError(2, "synthetic vanished side file")
        chmod(file, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "chmod", vanishing)
    with Store(path) as store:
        assert store.tasks() == []


def test_a_database_that_cannot_be_created_gives_the_constant_startup_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from docket import store as store_module

    path = tmp_path / "docket.sqlite3"
    real_open = os.open

    def opening(file: object, flags: int, mode: int = 0o777) -> int:
        if str(file) == str(path):
            raise PermissionError(13, "synthetic-private-library-text")
        return real_open(file, flags, mode)  # type: ignore[arg-type]

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("SQLite opened a database the store could not create")

    monkeypatch.setattr(store_module.os, "open", opening)
    monkeypatch.setattr(store_module.sqlite3, "connect", forbidden)
    refused_quietly("store startup unavailable", lambda: Store(path))
    assert not path.exists()
    monkeypatch.undo()
    Store(path).close()
    assert mode(path) == 0o600


def test_the_store_side_files_are_ignored_by_git() -> None:
    lines = (Path(__file__).parents[2] / ".gitignore").read_text().splitlines()
    for pattern in ("*.sqlite3-wal", "*.sqlite3-shm", "*.startup.lock"):
        assert pattern in lines, pattern
