import os
import sqlite3
import stat
from datetime import UTC, datetime
from pathlib import Path

import pytest

from docket import core
from docket import store as store_module
from docket.store import Store, StoreError
from tests.reference_cases import NOW
from tests.support import fixed_times

MARKER = "private-marker-from-library"


def test_existing_gate_permissions_are_corrected_without_replacing_it(tmp_path: Path) -> None:
    path = tmp_path / "docket.sqlite3"
    lock = path.with_name(path.name + ".startup.lock")
    lock.write_bytes(b"")
    lock.chmod(0o644)
    inode = lock.stat().st_ino
    with Store(path):
        pass
    assert lock.stat().st_ino == inode
    assert stat.S_IMODE(lock.stat().st_mode) == 0o600
    assert lock.read_bytes() == b""


def test_gate_open_and_permission_failures_skip_sqlite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    path = tmp_path / "docket.sqlite3"
    connected: list[bool] = []
    descriptors: list[int] = []
    real_open = os.open
    real_chmod = os.chmod
    fail_open = True

    def opening(file: object, flags: int, mode: int = 0o777) -> int:
        nonlocal fail_open
        if str(file).endswith(".startup.lock") and fail_open:
            raise PermissionError(MARKER)
        descriptor = real_open(file, flags, mode)  # type: ignore[arg-type]
        if str(file).endswith(".startup.lock"):
            descriptors.append(descriptor)
        return descriptor

    def permissions(file: object, mode: int) -> None:
        if str(file).endswith(".startup.lock"):
            raise PermissionError(MARKER)
        real_chmod(file, mode)  # type: ignore[arg-type]

    monkeypatch.setattr(store_module.os, "open", opening)
    monkeypatch.setattr(
        store_module.sqlite3, "connect", lambda *args, **kwargs: connected.append(True)
    )
    with caplog.at_level(0):
        with pytest.raises(StoreError, match="^store startup unavailable$") as opened:
            Store(path)
    assert MARKER not in str(opened.value)
    assert opened.value.__cause__ is None
    assert connected == []
    assert not path.exists()
    fail_open = False
    monkeypatch.setattr(store_module.os, "chmod", permissions)
    with caplog.at_level(0):
        with pytest.raises(StoreError, match="^store startup unavailable$") as changed:
            Store(path)
    assert MARKER not in str(changed.value)
    assert changed.value.__cause__ is None
    assert len(descriptors) == 1
    with pytest.raises(OSError):
        os.fstat(descriptors[0])
    assert connected == []
    captured = capsys.readouterr()
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert MARKER not in captured.out
    assert MARKER not in captured.err
    assert MARKER not in logged


def test_initialization_failure_is_not_wrapped_or_logged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    class ConnectBroke(Exception):
        pass

    def broken(*args: object, **kwargs: object) -> None:
        raise ConnectBroke(MARKER)

    monkeypatch.setattr(store_module.sqlite3, "connect", broken)
    with caplog.at_level(0):
        with pytest.raises(ConnectBroke) as raised:
            Store(tmp_path / "docket.sqlite3")
    assert str(raised.value) == MARKER
    assert not isinstance(raised.value, StoreError)
    captured = capsys.readouterr()
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert MARKER not in captured.out
    assert MARKER not in captured.err
    assert MARKER not in logged


def test_filtered_read_leaves_a_corrupt_row_and_accepts_zulu_time(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    path = tmp_path / "docket.sqlite3"
    fixed_times(monkeypatch, NOW, NOW)
    with Store(path) as store:
        core.create_task(store, title="Synthetic open task", source="owner")
        core.create_task(store, title="Synthetic hidden task", source="owner")
    with sqlite3.connect(path) as db:
        db.execute(
            "UPDATE tasks SET created_at='2026-11-17T14:00:00Z', updated_at='2026-11-17T14:00:00Z' "
            "WHERE number=1"
        )
        db.execute(
            "UPDATE tasks SET state='cancelled', created_at=? WHERE number=2",
            (MARKER,),
        )
    with Store(path) as store:
        with caplog.at_level(0):
            found = store.tasks({"open"})
        assert [task.id for task in found] == ["t1"]
        assert found[0].created_at == datetime(2026, 11, 17, 14, tzinfo=UTC)
        assert found[0].created_at.tzinfo is UTC
        assert found[0].updated_at.tzinfo is UTC
        with pytest.raises(StoreError, match="^invalid stored task time: t2$") as raised:
            store.task("t2")
    assert MARKER not in str(raised.value)
    captured = capsys.readouterr()
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert MARKER not in captured.out
    assert MARKER not in captured.err
    assert MARKER not in logged
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT created_at FROM tasks WHERE number=2").fetchone() == (MARKER,)


@pytest.mark.parametrize("planted", [3, 99])
def test_reference_rebuild_rechecks_the_version_before_its_sql(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, planted: int
) -> None:
    path = tmp_path / "docket.sqlite3"
    connect = sqlite3.connect
    created: list[str] = []
    injected: list[bool] = []

    class Tracked(sqlite3.Connection):
        def execute(self, sql: str, *args: object, **kwargs: object) -> sqlite3.Cursor:
            if sql.strip().upper() == "BEGIN IMMEDIATE" and not injected:
                enabled = super().execute("PRAGMA foreign_keys").fetchone()[0]
                if enabled == 0:
                    with connect(path) as other:
                        other.execute(f"PRAGMA user_version = {planted}")
                    injected.append(True)
            if "tasks_bounded" in sql:
                created.append(sql)
            return super().execute(sql, *args, **kwargs)

    monkeypatch.setattr(
        store_module.sqlite3,
        "connect",
        lambda *args, **kwargs: connect(*args, **kwargs, factory=Tracked),
    )
    if planted > 3:
        with pytest.raises(StoreError, match="^unsupported schema version: 99$"):
            Store(path)
    else:
        with Store(path) as store:
            assert store._connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert injected == [True]
    assert created == []
    with connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone() == (planted,)
