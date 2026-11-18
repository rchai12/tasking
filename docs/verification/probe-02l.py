"""Synthetic persistence, rollback and SQL-owner checks for the table boundary."""

import argparse
import importlib
import sys
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from docket import clock  # noqa: E402
from docket.store import Store  # noqa: E402
from tests.store_boundary_cases import (  # noqa: E402
    TABLE_MODULES,
    InjectedSqlFailure,
    add_email,
    create_agent,
    record_connections,
    snapshot,
)

AT = datetime(2026, 11, 17, 14, tzinfo=UTC)


def oracle() -> None:
    assert TABLE_MODULES == {
        "audit_log": "docket._store_audit",
        "links": "docket._store_links",
        "request_keys": "docket._store_keys",
    }


def modules(_root: Path) -> None:
    for table, name in TABLE_MODULES.items():
        module = importlib.import_module(name)
        assert Path(module.__file__).name == name.rsplit(".", 1)[1] + ".py", table


def ownership(root: Path) -> None:
    with patch.object(clock, "now", return_value=AT):
        with patcher() as opened:
            with Store(root / "docket.sqlite3") as store:
                connection = opened[0]
                connection.recording = True
                create_agent(store)
                add_email(store)
                store.audit("t1")
                store.links("t1")
                assert len(opened) == 1, f"expected one connection; actual {len(opened)}"
                for table, caller, _ in connection.events:
                    assert caller == TABLE_MODULES[table], (
                        f"{table}: expected owner {TABLE_MODULES[table]}; actual {caller}"
                    )
                assert set(table for table, _, _ in connection.events) == set(TABLE_MODULES)


def restart(root: Path) -> None:
    with patch.object(clock, "now", return_value=AT):
        with patcher() as opened:
            path = root / "docket.sqlite3"
            with Store(path) as store:
                create_agent(store)
                add_email(store)
                before = snapshot(opened[0])
            with Store(path) as store:
                assert not create_agent(store).changed
                assert not add_email(store).changed
                assert [item.id for item in store.links("t1")] == ["l1"]
                assert len(store.audit("t1")) == 1
                assert snapshot(opened[1]) == before, "replays after reopen changed stored rows"


def rollback(root: Path) -> None:
    with patch.object(clock, "now", return_value=AT):
        for index, table in enumerate(("audit_log", "request_keys")):
            with patcher() as opened:
                path = root / f"synthetic-{index}.sqlite3"
                with Store(path) as store:
                    connection = opened[0]
                    before = snapshot(connection)
                    connection.recording = True
                    connection.interrupt_table = table
                    try:
                        create_agent(store)
                    except InjectedSqlFailure:
                        pass
                    else:
                        raise AssertionError(f"forced post-{table} failure not reached")
                    assert snapshot(connection) == before, f"post-{table} failure left partial rows"
                with Store(path) as store:
                    assert store.tasks() == []
                    assert store.audit("t1") == []
                    assert store.request_key("agent", "synthetic-create") is None


@contextmanager
def patcher():
    with pytest.MonkeyPatch.context() as changes:
        yield record_connections(changes)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--oracle-only", action="store_true")
    args = parser.parse_args()
    oracle()
    print("boundary oracle ok")
    failures = 0
    if not args.oracle_only:
        for name, check in (
            ("private modules", modules),
            ("SQL owners", ownership),
            ("restart replay", restart),
            ("cross-table rollback", rollback),
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
