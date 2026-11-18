"""Synthetic upgrade/restart and atomic lifecycle properties; no sender exists in this phase."""

import hashlib
import sqlite3
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def oracle() -> None:
    from docket import schema
    from tests.reminder_storage_cases import PLAN, WITH_WORK

    assert [hashlib.sha256(sql.encode()).hexdigest() for sql in schema.MIGRATIONS[:3]] == [
        "4602024a8abbd4da1d1a399000d712d0f57e2e7c913bf0dac7ce879612bd342d",
        "5fc2bdd95fa706cf2c15b6befb304f10ada4467025d60bb2050815422aa78235",
        "dcbd5ff2ea213ef9258a2ad5f1ecc22fa47dc05489436840ea426c05fcd354d8",
    ]
    assert schema.SCHEMA_VERSION == 6 and len(PLAN) == 9 and len(WITH_WORK) == 10
    with sqlite3.connect(":memory:") as db:
        db.executescript("".join(schema.MIGRATIONS))
        assert [row[1] for row in db.execute("PRAGMA table_info(reminders)")] == [
            "number",
            "task",
            "kind",
            "fire_at",
            "planned_at",
            "claimed_at",
            "sent_at",
            "voided_at",
        ]
        assert db.execute("PRAGMA table_list('reminders')").fetchone()[-1] == 1


def upgrade(root: Path) -> None:
    from docket import clock, ids
    from docket.store import Store
    from tests.reminder_storage_cases import AT, WITH_WORK, project, snapshot, version_three

    path = root / "legacy.sqlite3"
    version_three(path)

    class UnexpectedRead(Exception):
        pass

    with (
        patch.object(clock, "now", side_effect=UnexpectedRead),
        patch.object(ids, "new_id", side_effect=UnexpectedRead),
    ):
        with Store(path) as opened:
            assert project(opened.reminders("t1")) == WITH_WORK
            assert len(opened.reminders("t2")) == 10
            assert opened.reminders("t3") == opened.reminders("t4") == []
            assert all(row.planned_at == AT for row in opened.reminders("t1"))
        before = snapshot(path)
        with Store(path):
            pass
        assert snapshot(path) == before


def lifecycle(root: Path) -> None:
    from datetime import datetime

    from docket import clock, core, ids
    from docket.deadlines import WorkTime
    from docket.store import Store
    from tests.reminder_storage_cases import (
        DUE,
        WITH_WORK,
        WORK,
        InterruptedWrite,
        project,
        snapshot,
    )

    path = root / "lifecycle.sqlite3"
    moments = [
        datetime.fromisoformat(value)
        for value in (
            "2026-11-20T16:00:00+00:00",
            "2026-11-20T16:01:00+00:00",
            "2026-11-20T16:02:00+00:00",
            "2026-11-20T16:03:00+00:00",
            "2026-11-20T16:04:00+00:00",
            "2026-11-20T16:05:00+00:00",
        )
    ]
    with (
        patch.object(clock, "now", side_effect=moments) as now,
        patch.object(ids, "new_id", side_effect=InterruptedWrite),
    ):
        with Store(path) as opened:
            fields = dict(
                client="agent",
                key="synthetic-key",
                request={},
                title="Synthetic task",
                source="agent",
                deadline=DUE,
                work=WORK,
            )
            core.create_task_once(opened, **fields)
            original = opened.reminders("t1")
            assert project(original) == WITH_WORK
            assert not core.create_task_once(opened, **fields).changed
            core.edit_task(opened, "t1", actor="owner", title="Synthetic edited")
            assert opened.reminders("t1") == original
            core.change_state(opened, "t1", "done", actor="owner")
            assert all(row.voided_at == moments[3] for row in opened.reminders("t1"))
            core.change_state(opened, "t1", "reopen", actor="owner")
            rows = opened.reminders("t1")
            assert len(rows) == 20 and project(rows[10:]) == WITH_WORK
            assert len({row.id for row in rows}) == 20
            before = snapshot(path)
            insert = Store.insert_reminders

            def interrupted(self, *args, **kwargs):
                insert(self, *args, **kwargs)
                raise InterruptedWrite

            with patch.object(Store, "insert_reminders", interrupted):
                try:
                    core.edit_task(
                        opened,
                        "t1",
                        actor="owner",
                        deadline=None,
                        work=WorkTime(
                            datetime.fromisoformat("2026-11-20T17:30:00+00:00"), 5, "UTC"
                        ),
                    )
                except InterruptedWrite:
                    pass
                else:
                    raise AssertionError("forced reminder-write interruption not reached")
            assert snapshot(path) == before
            assert now.call_count == 6


def main() -> None:
    oracle()
    print("schema and literal oracle ok")
    if "--oracle-only" in sys.argv:
        print("FAILURES 0")
        return
    failures = 0
    for name, check in (
        ("populated upgrade and restart", upgrade),
        ("retry, lifecycle and rollback", lifecycle),
    ):
        with TemporaryDirectory() as directory:
            try:
                check(Path(directory))
            except Exception as error:
                print(
                    f"FAIL {name}: expected one durable plan and atomic history; "
                    f"{type(error).__name__}"
                )
                failures += 1
            else:
                print(name + " ok")
    print(f"FAILURES {failures}")


if __name__ == "__main__":
    main()
