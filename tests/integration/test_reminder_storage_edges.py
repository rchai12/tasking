import sqlite3
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from docket import _store_reminders, core
from docket.deadlines import Deadline, WorkTime
from docket.reminders import PlannedReminder
from docket.store import Store, StoreError
from tests.reminder_storage_cases import (
    AT,
    DUE,
    LATER,
    NEXT,
    NOW,
    WORK,
    project,
    snapshot,
    version_three,
)
from tests.support import fixed_ids, fixed_times

FRESH = [
    ["start", "2026-11-20T17:30:00+00:00"],
    ["before", "2026-11-21T17:00:00+00:00"],
    ["due", "2026-11-21T18:00:00+00:00"],
    ["late", "2026-11-21T18:30:00+00:00"],
    ["late", "2026-11-21T19:00:00+00:00"],
    ["late", "2026-11-21T20:00:00+00:00"],
    ["late", "2026-11-21T21:00:00+00:00"],
    ["late", "2026-11-21T22:00:00+00:00"],
    ["late", "2026-11-22T02:00:00+00:00"],
    ["late", "2026-11-22T06:00:00+00:00"],
]


def test_a_combined_replacement_voids_both_groups_and_writes_ten_rows(
    tmp_path, monkeypatch
) -> None:
    fixed_times(monkeypatch, NOW, LATER)
    with Store(tmp_path / "docket.sqlite3") as opened:
        core.create_task(opened, title="Synthetic task", source="owner", deadline=DUE, work=WORK)
        core.edit_task(
            opened,
            "t1",
            actor="owner",
            deadline=Deadline(datetime(2026, 11, 21, 18, tzinfo=UTC), "UTC", True),
            work=WorkTime(datetime(2026, 11, 20, 17, 30, tzinfo=UTC), 5, "UTC"),
        )
        rows = opened.reminders("t1")
        assert project(rows[:10]) == [
            ["start", "2026-11-20T16:30:00+00:00"],
            ["before", "2026-11-20T17:00:00+00:00"],
            ["due", "2026-11-20T18:00:00+00:00"],
            ["late", "2026-11-20T18:30:00+00:00"],
            ["late", "2026-11-20T19:00:00+00:00"],
            ["late", "2026-11-20T20:00:00+00:00"],
            ["late", "2026-11-20T21:00:00+00:00"],
            ["late", "2026-11-20T22:00:00+00:00"],
            ["late", "2026-11-21T02:00:00+00:00"],
            ["late", "2026-11-21T06:00:00+00:00"],
        ]
        assert all(row.voided_at == NEXT for row in rows[:10])
        assert project(rows[10:19]) == FRESH[1:]
        assert project(rows[19:]) == FRESH[:1]
        assert all(row.voided_at is None and row.planned_at == NEXT for row in rows[10:])
        assert [row.action for row in opened.audit("t1")] == ["create", "deadline", "work_time"]
        assert opened.task("t1").state == "open"


def test_a_work_only_task_keeps_one_start_row_through_end_and_reopen(tmp_path, monkeypatch) -> None:
    fixed_times(monkeypatch, NOW, LATER, LATER)
    with Store(tmp_path / "docket.sqlite3") as opened:
        core.create_task(opened, title="Synthetic task", source="owner", work=WORK)
        assert project(opened.reminders("t1")) == [["start", "2026-11-20T16:30:00+00:00"]]
        core.change_state(opened, "t1", "done", actor="owner")
        ended = opened.reminders("t1")
        assert ended[0].id == "r1" and ended[0].voided_at == NEXT
        core.change_state(opened, "t1", "reopen", actor="owner")
        rows = opened.reminders("t1")
        assert rows[0] == ended[0]
        assert project(rows[1:]) == [["start", "2026-11-20T16:30:00+00:00"]]
        assert rows[1].id == "r2" and rows[1].planned_at == NEXT and rows[1].voided_at is None
        assert opened.task("t1").state == "open"


def test_reopening_an_ended_overflowing_legacy_task_stays_ended(tmp_path, monkeypatch) -> None:
    path = tmp_path / "docket.sqlite3"
    version_three(path)
    with sqlite3.connect(path) as db:
        db.execute(
            "UPDATE tasks SET state = 'done', deadline_at = '9999-12-31T23:59:00+00:00' "
            "WHERE number = 1"
        )
    fixed_times(monkeypatch)
    with Store(path) as opened:
        assert opened.reminders("t1") == []
        assert len(opened.reminders("t2")) == 10
        fixed_times(monkeypatch, NOW)
        with pytest.raises(core.CoreError) as raised:
            core.change_state(opened, "t1", "reopen", actor="owner")
        assert (raised.value.code, str(raised.value), raised.value.__cause__) == (
            "invalid_reminder_plan",
            "invalid_reminder_plan",
            None,
        )
        task = opened.task("t1")
        assert task is not None and task.state == "done"
        assert opened.reminders("t1") == []


def test_a_malformed_legacy_time_keeps_version_three(tmp_path) -> None:
    path = tmp_path / "docket.sqlite3"
    version_three(path)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE tasks SET deadline_at = 'synthetic-invalid' WHERE number = 1")
    before = snapshot(path)
    with pytest.raises(StoreError) as raised:
        Store(path)
    assert str(raised.value) == "invalid stored task time: t1"
    assert raised.value.__cause__ is None
    assert snapshot(path) == before
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone() == (3,)


def test_inactive_and_empty_legacy_plans_upgrade_without_clock_or_ids(
    tmp_path, monkeypatch
) -> None:
    path = tmp_path / "docket.sqlite3"
    version_three(path)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE tasks SET state = 'done'")
        db.execute(
            "UPDATE tasks SET state = 'open', deadline_at = NULL, deadline_zone = NULL, "
            "deadline_time_given = NULL, work_start = NULL, work_minutes = NULL, "
            "work_zone = NULL WHERE number = 1"
        )
    fixed_times(monkeypatch)
    fixed_ids(monkeypatch)
    with Store(path) as opened:
        assert opened.reminders("t1") == opened.reminders("t2") == []
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone() == (4,)


def test_a_backfill_sql_failure_rolls_back_and_releases_the_startup_lock(
    tmp_path, monkeypatch
) -> None:
    path = tmp_path / "docket.sqlite3"
    version_three(path)
    before = snapshot(path)
    original = _store_reminders.insert_reminder
    seen: set[int] = set()

    def fail(connection, task, kind, fire_at, planned_at):
        seen.add(task)
        if len(seen) > 1:
            raise sqlite3.OperationalError("synthetic")
        return original(connection, task, kind, fire_at, planned_at)

    monkeypatch.setattr(_store_reminders, "insert_reminder", fail)
    closes: list[object] = []
    close = Store.close

    def record(self):
        closes.append(self)
        return close(self)

    monkeypatch.setattr(Store, "close", record)
    with pytest.raises(sqlite3.OperationalError):
        Store(path)
    assert len(closes) == 1
    assert snapshot(path) == before
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone() == (3,)
    monkeypatch.setattr(_store_reminders, "insert_reminder", original)
    with Store(path) as opened:
        assert len(opened.reminders("t1")) == 10
        assert len(opened.reminders("t2")) == 10


def test_public_writes_require_canonical_utc_and_string_kinds(tmp_path) -> None:
    moment = datetime(2026, 11, 20, 16, 0, 0, 1, tzinfo=UTC)
    zone = datetime(2026, 11, 20, 16, tzinfo=ZoneInfo("UTC"))
    with Store(tmp_path / "docket.sqlite3") as opened:
        with opened.transaction():
            opened.insert_task(
                title="Synthetic task",
                state="open",
                deadline=None,
                work=None,
                source="owner",
                provider=None,
                message_id=None,
                link=None,
                at=AT,
            )
        with opened.transaction():
            with pytest.raises(StoreError) as zone_time:
                opened.insert_reminders("t1", (PlannedReminder("due", zone),), at=AT)
            with pytest.raises(StoreError) as zone_at:
                opened.insert_reminders("t1", (PlannedReminder("due", AT),), at=zone)
            with pytest.raises(StoreError) as kind:
                opened.insert_reminders("t1", (PlannedReminder(None, AT),), at=AT)  # type: ignore[arg-type]
            with pytest.raises(StoreError) as void_kind:
                opened.void_reminders("t1", at=AT, kinds=(None,))  # type: ignore[arg-type]
            assert str(zone_time.value) == str(zone_at.value) == "an instant must be in UTC"
            assert str(kind.value) == str(void_kind.value) == "invalid reminder kind"
            assert (
                zone_time.value.__cause__
                is zone_at.value.__cause__
                is kind.value.__cause__
                is void_kind.value.__cause__
                is None
            )
            written = opened.insert_reminders("t1", (PlannedReminder("due", moment),), at=moment)
        assert written[0].fire_at == written[0].planned_at == moment
        assert opened.reminders("t1") == written
