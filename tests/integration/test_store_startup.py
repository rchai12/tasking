import sqlite3
from pathlib import Path

import pytest

from docket import store as store_module
from docket.store import Store, StoreError


class InitializationBroke(Exception):
    pass


@pytest.mark.parametrize(
    "stage",
    [
        "row_factory",
        "chmod",
        "chmod_permission",
        "busy",
        "foreign_keys",
        "version",
        "wal",
        "migration",
    ],
)
def test_each_failed_initialization_closes_the_connection_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    path = tmp_path / "docket.sqlite3"
    failure = (
        PermissionError("private-marker-from-library")
        if stage == "chmod_permission"
        else InitializationBroke()
    )
    connections = []
    closed = []
    connect = sqlite3.connect
    chmod = Path.chmod

    class Tracked(sqlite3.Connection):
        def __setattr__(self, name, value):
            if stage == "row_factory" and name == "row_factory":
                raise failure
            super().__setattr__(name, value)

        def execute(self, sql, *args, **kwargs):
            statement = sql.strip().upper()
            broken = (
                (stage == "busy" and statement.startswith("PRAGMA BUSY_TIMEOUT"))
                or (stage == "foreign_keys" and statement == "PRAGMA FOREIGN_KEYS = ON")
                or (stage == "version" and statement == "PRAGMA USER_VERSION")
                or (stage == "wal" and statement == "PRAGMA JOURNAL_MODE = WAL")
                or (stage == "migration" and statement.startswith("CREATE TABLE"))
            )
            if broken:
                raise failure
            return super().execute(sql, *args, **kwargs)

        def close(self) -> None:
            closed.append(self)
            super().close()

    def opening(*args, **kwargs):
        connection = connect(*args, **kwargs, factory=Tracked)
        connections.append(connection)
        return connection

    def permissions(self, *args, **kwargs):
        if stage in {"chmod", "chmod_permission"} and self == path:
            raise failure
        return chmod(self, *args, **kwargs)

    monkeypatch.setattr(store_module.sqlite3, "connect", opening)
    monkeypatch.setattr(Path, "chmod", permissions)
    with pytest.raises(type(failure)) as raised:
        Store(path)
    assert raised.value is failure
    assert len(connections) == 1
    assert closed == connections
    with pytest.raises(sqlite3.ProgrammingError):
        connections[0].execute("SELECT 1")


def test_connect_failure_does_not_attempt_to_close_an_uncreated_connection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    failure = InitializationBroke()
    calls = []

    def broken(*args, **kwargs):
        calls.append(True)
        raise failure

    monkeypatch.setattr(store_module.sqlite3, "connect", broken)
    with pytest.raises(InitializationBroke) as raised:
        Store(tmp_path / "docket.sqlite3")
    assert raised.value is failure
    assert calls == [True]


def test_newer_schema_refusal_closes_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "docket.sqlite3"
    connect = sqlite3.connect
    with connect(path) as db:
        db.execute("PRAGMA user_version = 99")
    closed = []

    class Tracked(sqlite3.Connection):
        def close(self) -> None:
            closed.append(True)
            super().close()

    monkeypatch.setattr(
        store_module.sqlite3, "connect", lambda *a, **k: connect(*a, **k, factory=Tracked)
    )
    with pytest.raises(StoreError, match="^unsupported schema version: 99$"):
        Store(path)
    assert closed == [True]
