import fcntl
import multiprocessing
import os
import sqlite3
import stat
from pathlib import Path

import pytest

from docket import store as store_module
from docket.store import Store, StoreError
from tests.reference_cases import snapshot
from tests.startup_cases import held_gate, open_child, prepare


@pytest.mark.parametrize("version", [0, 1, 2, 5], ids=["empty", "v1", "v2", "current"])
def test_two_processes_initialize_the_same_database_once(tmp_path: Path, version: int) -> None:
    path = tmp_path / "docket.sqlite3"
    prepare(path, version)
    before = snapshot(path) if version == 2 else None
    ctx = multiprocessing.get_context("spawn")
    start = ctx.Event()
    messages = ctx.Queue()
    workers = [ctx.Process(target=open_child, args=(str(path), start, messages)) for _ in range(2)]
    try:
        for worker in workers:
            worker.start()
        assert messages.get(timeout=10) == ("ready",)
        assert messages.get(timeout=10) == ("ready",)
        start.set()
        results = [messages.get(timeout=10), messages.get(timeout=10)]
        if version == 2:
            assert results == [("ok", ["t1"], ["l1"], 5, []), ("ok", ["t1"], ["l1"], 5, [])]
            assert snapshot(path) == before
        elif version == 1:
            assert results == [("ok", ["t1"], [], 5, []), ("ok", ["t1"], [], 5, [])]
        else:
            assert results == [("ok", [], [], 5, []), ("ok", [], [], 5, [])]
        for worker in workers:
            worker.join(timeout=10)
            assert worker.exitcode == 0
    finally:
        start.set()
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
            worker.join(timeout=10)
        messages.close()
        messages.join_thread()


def test_startup_gate_is_private_held_before_connect_and_persistent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "docket.sqlite3"
    lock = tmp_path / "docket.sqlite3.startup.lock"
    connect = sqlite3.connect
    entered = []

    def opening(*args, **kwargs):
        assert lock.exists(), "startup gate file is missing"
        assert stat.S_IMODE(lock.stat().st_mode) == 0o600
        with lock.open("a+b") as second:
            with pytest.raises(BlockingIOError):
                fcntl.flock(second, fcntl.LOCK_EX | fcntl.LOCK_NB)
        entered.append(True)
        return connect(*args, **kwargs)

    monkeypatch.setattr(store_module.sqlite3, "connect", opening)
    with Store(path):
        pass
    inode = lock.stat().st_ino
    with lock.open("a+b") as free:
        fcntl.flock(free, fcntl.LOCK_EX | fcntl.LOCK_NB)
    with Store(path):
        pass
    assert lock.stat().st_ino == inode
    assert entered == [True, True]
    assert lock.read_bytes() == b""


def test_gate_acquisition_error_is_constant_and_closes_the_descriptor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "docket.sqlite3"
    descriptors = []
    connected = []

    def blocked(handle, operation):
        descriptors.append(handle if isinstance(handle, int) else handle.fileno())
        raise PermissionError("private-marker-from-library")

    def forbidden(*args, **kwargs):
        connected.append(True)
        raise AssertionError("SQLite opened before startup gate")

    monkeypatch.setattr(fcntl, "flock", blocked)
    monkeypatch.setattr(store_module.sqlite3, "connect", forbidden)
    with pytest.raises(StoreError) as raised:
        Store(path)
    assert str(raised.value) == "store startup unavailable"
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None or raised.value.__suppress_context__
    assert len(descriptors) == 1
    with pytest.raises(OSError):
        os.fstat(descriptors[0])
    assert connected == []
    assert not path.exists()


def test_failed_constructor_releases_the_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class ConnectBroke(Exception):
        pass

    path = tmp_path / "docket.sqlite3"
    lock = tmp_path / "docket.sqlite3.startup.lock"

    def broken(*args, **kwargs):
        raise ConnectBroke

    monkeypatch.setattr(store_module.sqlite3, "connect", broken)
    with pytest.raises(ConnectBroke):
        Store(path)
    assert lock.exists()
    with lock.open("a+b") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)


def test_schema_version_decisions_are_under_an_immediate_transaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    connect = sqlite3.connect
    reads = []

    class Tracked(sqlite3.Connection):
        last_begin = None

        def execute(self, sql, *args, **kwargs):
            statement = sql.strip().upper()
            if statement.startswith("BEGIN"):
                self.last_begin = statement
            if statement == "PRAGMA USER_VERSION":
                reads.append(self.in_transaction)
                assert self.in_transaction and self.last_begin == "BEGIN IMMEDIATE"
            return super().execute(sql, *args, **kwargs)

    monkeypatch.setattr(
        store_module.sqlite3, "connect", lambda *a, **k: connect(*a, **k, factory=Tracked)
    )
    with Store(tmp_path / "docket.sqlite3"):
        pass
    assert reads
    assert all(reads)


def test_migration_foreign_keys_remain_scoped_to_the_reference_rebuild(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    connect = sqlite3.connect
    observed = []

    class Tracked(sqlite3.Connection):
        def execute(self, sql, *args, **kwargs):
            if sql.lstrip().startswith("CREATE TABLE"):
                version = super().execute("PRAGMA user_version").fetchone()[0]
                enabled = super().execute("PRAGMA foreign_keys").fetchone()[0]
                observed.append((version, enabled))
            return super().execute(sql, *args, **kwargs)

    monkeypatch.setattr(
        store_module.sqlite3, "connect", lambda *a, **k: connect(*a, **k, factory=Tracked)
    )
    with Store(tmp_path / "docket.sqlite3") as store:
        assert store._connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert observed == [(0, 1), (0, 1), (1, 1), (1, 1), (2, 0), (2, 0), (3, 1), (4, 1), (4, 1)]


def test_process_exit_releases_a_gate_without_deleting_it(tmp_path: Path) -> None:
    path = tmp_path / "docket.sqlite3"
    ctx = multiprocessing.get_context("spawn")
    parent, child = ctx.Pipe()
    worker = ctx.Process(target=held_gate, args=(str(path), child))
    try:
        worker.start()
        assert parent.poll(10)
        assert parent.recv() is True
        worker.terminate()
        worker.join(timeout=10)
        assert not worker.is_alive()
        with Store(path):
            pass
        assert (tmp_path / "docket.sqlite3.startup.lock").exists()
    finally:
        if worker.is_alive():
            worker.terminate()
        worker.join(timeout=10)
        parent.close()
        child.close()


def test_a_later_transaction_rechecks_the_version_before_applying_sql(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "docket.sqlite3"
    connect = sqlite3.connect
    begins = []
    injected = []

    class Tracked(sqlite3.Connection):
        def execute(self, sql, *args, **kwargs):
            if sql.strip().upper() == "BEGIN IMMEDIATE":
                begins.append(True)
                if len(begins) == 2:
                    assert not self.in_transaction
                    with connect(path) as other:
                        other.execute("PRAGMA user_version = 99")
                    injected.append(True)
            return super().execute(sql, *args, **kwargs)

    monkeypatch.setattr(
        store_module.sqlite3, "connect", lambda *a, **k: connect(*a, **k, factory=Tracked)
    )
    with pytest.raises(StoreError, match="^unsupported schema version: 99$"):
        Store(path)
    assert injected == [True]
    with connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone() == (99,)
