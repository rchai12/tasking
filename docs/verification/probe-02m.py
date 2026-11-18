"""Offline task-table ownership, restart and interrupted-write properties."""

import argparse
import importlib
import sys
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from docket import clock, core  # noqa: E402
from docket.store import Store  # noqa: E402
from tests.store_boundary_cases import (  # noqa: E402
    InjectedSqlFailure,
    add_email,
    create_agent,
    snapshot,
)
from tests.task_boundary_cases import ALL_TABLE_MODULES, record_task_connections  # noqa: E402

AT = datetime(2026, 11, 17, 14, tzinfo=UTC)


def oracle() -> None:
    assert ALL_TABLE_MODULES == {
        "tasks": "docket._store_tasks",
        "audit_log": "docket._store_audit",
        "links": "docket._store_links",
        "request_keys": "docket._store_keys",
    }
    for value, expected in (
        ("2026-11-01T17:00", "2026-11-01T22:00:00+00:00"),
        ("2027-03-14T17:00", "2027-03-14T21:00:00+00:00"),
    ):
        wall = datetime.fromisoformat(value).replace(tzinfo=ZoneInfo("America/New_York"), fold=0)
        assert wall.astimezone(UTC).isoformat() == expected


@contextmanager
def recorder():
    with pytest.MonkeyPatch.context() as changes:
        yield record_task_connections(changes)


def module(_root: Path) -> None:
    assert importlib.import_module("docket._store_tasks").__name__ == "docket._store_tasks"


def ownership(root: Path) -> None:
    with recorder() as opened, patch.object(clock, "now", return_value=AT):
        with Store(root / "docket.sqlite3") as store:
            connection = opened[0]
            connection.recording = True
            create_agent(store)
            add_email(store)
            core.edit_task(store, "t1", actor="owner", title="Synthetic edit")
            assert store.task("t1") is not None
            assert len(store.tasks(("open",))) == 1
            store.audit("t1")
            store.links("t1")
            assert len(opened) == 1, f"expected one connection; actual {len(opened)}"
            assert {table for table, _, _ in connection.events} == set(ALL_TABLE_MODULES)
            for table, caller, _transaction in connection.events:
                assert caller == ALL_TABLE_MODULES[table], (
                    f"{table}: expected {ALL_TABLE_MODULES[table]}; actual {caller}"
                )


def restart(root: Path) -> None:
    with recorder() as opened, patch.object(clock, "now", return_value=AT):
        path = root / "docket.sqlite3"
        with Store(path) as store:
            create_agent(store)
            add_email(store)
            core.change_state(store, "t1", "done", actor="owner")
            before = snapshot(opened[0])
        with Store(path) as store:
            for _ in range(5):
                outcome = create_agent(store)
                assert (outcome.task.id, outcome.task.state, outcome.changed) == (
                    "t1",
                    "done",
                    False,
                )
                assert not add_email(store).changed
            assert len(store.audit("t1")) == 2
            assert [item.id for item in store.links("t1")] == ["l1"]
            assert snapshot(opened[1]) == before, "reopen/replays changed rows or sequences"


def rollback(root: Path) -> None:
    with patch.object(clock, "now", return_value=AT):
        for operation in ("insert", "update"):
            with recorder() as opened:
                path = root / f"synthetic-{operation}.sqlite3"
                with Store(path) as store:
                    if operation == "update":
                        create_agent(store)
                    connection = opened[0]
                    before = snapshot(connection)
                    connection.recording = True
                    connection.interrupt_task = operation
                    try:
                        if operation == "insert":
                            create_agent(store)
                        else:
                            core.edit_task(store, "t1", actor="owner", title="Synthetic edit")
                    except InjectedSqlFailure:
                        pass
                    else:
                        raise AssertionError(f"post-task-{operation} interruption not reached")
                    assert snapshot(connection) == before, f"{operation} left partial rows"
                with Store(path):
                    assert snapshot(opened[1]) == before, f"{operation} changed persisted state"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--oracle-only", action="store_true")
    args = parser.parse_args()
    oracle()
    print("task-boundary oracle ok")
    failures = 0
    if not args.oracle_only:
        for name, check in (
            ("private task module", module),
            ("four SQL owners", ownership),
            ("ended-task replay", restart),
            ("interrupted task writes", rollback),
        ):
            with TemporaryDirectory() as folder:
                try:
                    check(Path(folder))
                    print(f"{name} ok")
                except Exception as error:
                    print(f"{name} FAIL: {type(error).__name__}: {error}")
                    failures += 1
    print(f"FAILURES {failures}")
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
