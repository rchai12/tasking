import dataclasses
import multiprocessing
import sqlite3
from datetime import UTC, datetime

import pytest

from docket import core
from docket.store import Store, StoreError
from tests.reminder_storage_cases import (
    AT,
    DUE,
    LATER,
    NEXT,
    NOW,
    PLAN,
    WITH_WORK,
    WORK,
    InterruptedWrite,
    open_upgraded,
    project,
    snapshot,
    version_three,
)
from tests.support import fixed_ids, fixed_times, run


@pytest.mark.parametrize(
    "source,keyed",
    [("owner", False), ("agent", False), ("agent", True), ("email", False), ("email", True)],
)
def test_approved_creation_persists_one_complete_plan(tmp_path, monkeypatch, source, keyed) -> None:
    fixed_times(monkeypatch, NOW, LATER)
    fixed_ids(monkeypatch)
    path = tmp_path / "docket.sqlite3"
    with Store(path) as opened:
        fields = dict(title="Synthetic task", source=source, deadline=DUE)
        if source == "email":
            fields.update(provider="gmail", message_id="synthetic/1", link="https://mail.example/1")
        if keyed:
            outcome = core.create_task_once(
                opened, client=source, key="synthetic-key", request={"a": 1}, **fields
            )
            assert outcome.changed
            before = snapshot(path)
            replay = core.create_task_once(
                opened, client=source, key="synthetic-key", request={"a": 1}, **fields
            )
            assert not replay.changed and replay.task.id == "t1"
            assert snapshot(path) == before
        else:
            core.create_task(opened, **fields)
        rows = opened.reminders("t1")
        assert project(rows) == PLAN
        assert [row.id for row in rows] == ["r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8", "r9"]
        assert all(row.task_id == "t1" and row.planned_at == AT for row in rows)
        assert all(row.claimed_at is row.sent_at is row.voided_at is None for row in rows)
        with pytest.raises(dataclasses.FrozenInstanceError):
            rows[0].kind = "late"
    with Store(path) as reopened:
        assert reopened.reminders("t1") == rows
        assert reopened.reminders("bad") == []
        assert reopened.reminders("t99") == []


@pytest.mark.parametrize("action", ["done", "cancel"])
def test_end_repeat_and_reopen_preserve_history_atomically(tmp_path, monkeypatch, action) -> None:
    fixed_times(monkeypatch, NOW, LATER, LATER, LATER, LATER)
    with Store(tmp_path / "docket.sqlite3") as opened:
        core.create_task(opened, title="Synthetic task", source="owner", deadline=DUE, work=WORK)
        core.change_state(opened, "t1", action, actor="owner")
        old = opened.reminders("t1")
        assert len(old) == 10 and all(row.voided_at == NEXT for row in old)
        assert not core.change_state(opened, "t1", action, actor="owner").changed
        assert opened.reminders("t1") == old
        assert core.change_state(opened, "t1", "reopen", actor="owner").changed
        all_rows = opened.reminders("t1")
        assert all_rows[:10] == old
        assert project(all_rows[10:]) == WITH_WORK
        assert all_rows[10].id == "r11" and all_rows[-1].id == "r20"
        assert all(row.planned_at == NEXT and row.voided_at is None for row in all_rows[10:])
        assert not core.change_state(opened, "t1", "reopen", actor="owner").changed
        assert opened.reminders("t1") == all_rows


@pytest.mark.parametrize(
    "change", ["deadline", "work", "clear-deadline", "clear-work", "clear-both"]
)
def test_edits_replace_only_the_changed_pending_group(tmp_path, monkeypatch, change) -> None:
    from docket.deadlines import Deadline, WorkTime

    fixed_times(monkeypatch, NOW, LATER)
    with Store(tmp_path / "docket.sqlite3") as opened:
        core.create_task(opened, title="Synthetic task", source="owner", deadline=DUE, work=WORK)
        fields = {
            "deadline": {"deadline": Deadline(datetime(2026, 11, 21, 18, tzinfo=UTC), "UTC", True)},
            "work": {"work": WorkTime(datetime(2026, 11, 20, 17, 30, tzinfo=UTC), 5, "UTC")},
            "clear-deadline": {"deadline": None},
            "clear-work": {"work": None},
            "clear-both": {"deadline": None, "work": None},
        }[change]
        core.edit_task(opened, "t1", actor="owner", **fields)
        rows = opened.reminders("t1")
        start = rows[0]
        deadline_rows = rows[1:10]
        assert (start.voided_at == NEXT) == (change in ("work", "clear-work", "clear-both"))
        assert all(
            (row.voided_at == NEXT) == (change in ("deadline", "clear-deadline", "clear-both"))
            for row in deadline_rows
        )
        new = rows[10:]
        if change == "deadline":
            assert len(new) == 9
            assert [new[0].kind, new[0].fire_at.isoformat()] == [
                "before",
                "2026-11-21T17:00:00+00:00",
            ]
        elif change == "work":
            assert project(new) == [["start", "2026-11-20T17:30:00+00:00"]]
        else:
            assert new == []


@pytest.mark.parametrize("operation", ["title", "noop", "same-values", "start", "link"])
def test_unrelated_changes_and_retries_keep_reminder_ids_and_instants(
    tmp_path, monkeypatch, operation
) -> None:
    fixed_times(monkeypatch, NOW, LATER)
    with Store(tmp_path / "docket.sqlite3") as opened:
        core.create_task(opened, title="Synthetic task", source="owner", deadline=DUE, work=WORK)
        before = opened.reminders("t1")
        if operation == "title":
            core.edit_task(opened, "t1", actor="owner", title="Synthetic changed")
        elif operation == "noop":
            core.edit_task(opened, "t1", actor="owner")
        elif operation == "same-values":
            core.edit_task(opened, "t1", actor="owner", deadline=DUE, work=WORK)
        elif operation == "start":
            core.change_state(opened, "t1", "start", actor="owner")
        else:
            core.add_link(
                opened,
                "t1",
                client="email",
                key="synthetic-link",
                request={},
                provider="gmail",
                message_id="synthetic/2",
                link="https://mail.example/2",
            )
        assert opened.reminders("t1") == before


@pytest.mark.parametrize("operation", ["create", "keyed", "edit", "end", "reopen"])
def test_a_failure_after_reminder_sql_rolls_back_every_table(
    tmp_path, monkeypatch, operation
) -> None:
    fixed_times(monkeypatch, NOW, LATER, LATER)
    path = tmp_path / "docket.sqlite3"
    with Store(path) as opened:
        if operation not in ("create", "keyed"):
            core.create_task(opened, title="Synthetic task", source="owner", deadline=DUE)
            if operation == "reopen":
                core.change_state(opened, "t1", "done", actor="owner")
        method = "void_reminders" if operation == "end" else "insert_reminders"
        original = getattr(Store, method)

        def broken(self, *args, **kwargs):
            original(self, *args, **kwargs)
            raise InterruptedWrite

        monkeypatch.setattr(Store, method, broken)
        before = snapshot(path)
        with pytest.raises(InterruptedWrite):
            if operation == "create":
                core.create_task(opened, title="Synthetic new", source="owner", deadline=DUE)
            elif operation == "keyed":
                core.create_task_once(
                    opened,
                    client="agent",
                    key="synthetic-new",
                    request={},
                    title="Synthetic new",
                    source="agent",
                    deadline=DUE,
                )
            elif operation == "edit":
                core.edit_task(opened, "t1", actor="owner", deadline=None, work=WORK)
            else:
                core.change_state(
                    opened, "t1", "done" if operation == "end" else "reopen", actor="owner"
                )
        assert snapshot(path) == before


def test_upgrade_backfills_active_tasks_once_using_stored_updated_at(tmp_path, monkeypatch) -> None:
    path = tmp_path / "docket.sqlite3"
    version_three(path)
    before = snapshot(path)
    fixed_times(monkeypatch)
    fixed_ids(monkeypatch)
    with Store(path) as opened:
        rows = opened.reminders("t1")
        assert project(rows) == WITH_WORK
        assert len(opened.reminders("t2")) == 10
        assert opened.reminders("t3") == opened.reminders("t4") == []
        assert all(row.planned_at == AT for row in rows)
        assert len(opened.audit("t1")) == 0
    after = snapshot(path)
    for table in ("tasks", "audit_log", "links", "request_keys"):
        assert after[table] == before[table]
    with Store(path) as reopened:
        assert reopened.reminders("t1") == rows
    assert snapshot(path) == after


def test_independent_upgraders_do_not_duplicate_backfilled_plans(tmp_path) -> None:
    path = tmp_path / "docket.sqlite3"
    version_three(path)
    ctx = multiprocessing.get_context("spawn")
    start = ctx.Event()
    messages = ctx.Queue()
    workers = [
        ctx.Process(target=open_upgraded, args=(str(path), start, messages)) for _ in range(2)
    ]
    try:
        for worker in workers:
            worker.start()
        start.set()
        assert [messages.get(timeout=15), messages.get(timeout=15)] == [
            ("ok", 10, 10),
            ("ok", 10, 10),
        ]
        for worker in workers:
            worker.join(timeout=10)
            assert worker.exitcode == 0
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
            worker.join(timeout=10)
        messages.close()
        messages.join_thread()


@pytest.mark.parametrize(
    "updated",
    ["2026-11-20T17:30:00+00:00", "2026-11-22T16:00:00+00:00"],
    ids=["due-soon", "all-past"],
)
def test_backfill_uses_the_last_approved_instant_and_preserves_past_slots(
    tmp_path, monkeypatch, updated
) -> None:
    path = tmp_path / "docket.sqlite3"
    version_three(path)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE tasks SET updated_at=? WHERE number=1", (updated,))
    fixed_times(monkeypatch)
    fixed_ids(monkeypatch)
    with Store(path) as opened:
        rows = opened.reminders("t1")
        assert all(row.planned_at.isoformat() == updated for row in rows)
        assert [rows[0].kind, rows[0].fire_at.isoformat()] == ["start", "2026-11-20T16:30:00+00:00"]
        if updated == "2026-11-20T17:30:00+00:00":
            assert [rows[1].kind, rows[1].fire_at.isoformat()] == [
                "due_soon",
                "2026-11-20T17:30:00+00:00",
            ]
            assert project(rows[2:]) == PLAN[1:]
        else:
            assert project(rows[1:]) == PLAN[1:]


def test_unschedulable_legacy_task_refuses_upgrade_without_changing_data(
    tmp_path, monkeypatch
) -> None:
    path = tmp_path / "docket.sqlite3"
    version_three(path)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE tasks SET deadline_at='9999-12-31T23:59:00+00:00' WHERE number=2")
    before = snapshot(path)
    fixed_times(monkeypatch)
    with pytest.raises(StoreError) as raised:
        Store(path)
    assert str(raised.value) == "invalid reminder plan: t2"
    assert raised.value.__cause__ is None
    assert snapshot(path) == before
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone() == (3,)


@pytest.mark.parametrize("operation", ["create", "keyed", "edit"])
def test_overflow_is_a_safe_core_refusal_and_rolls_back(tmp_path, monkeypatch, operation) -> None:
    from docket.deadlines import Deadline

    fixed_times(monkeypatch, NOW, LATER)
    bad = Deadline(datetime(9999, 12, 31, 23, 59, tzinfo=UTC), "UTC", True)
    path = tmp_path / "docket.sqlite3"
    with Store(path) as opened:
        if operation == "edit":
            core.create_task(opened, title="Synthetic task", source="owner", deadline=DUE)
        before = snapshot(path)
        with pytest.raises(core.CoreError) as raised:
            if operation == "create":
                core.create_task(opened, title="Synthetic task", source="owner", deadline=bad)
            elif operation == "keyed":
                core.create_task_once(
                    opened,
                    client="agent",
                    key="synthetic-key",
                    request={},
                    title="Synthetic task",
                    source="agent",
                    deadline=bad,
                )
            else:
                core.edit_task(opened, "t1", actor="owner", deadline=bad)
        assert (raised.value.code, str(raised.value)) == (
            "invalid_reminder_plan",
            "invalid_reminder_plan",
        )
        assert raised.value.__cause__ is None
        assert snapshot(path) == before


def test_overflow_reaches_http_and_cli_as_safe_refusals(tmp_path, monkeypatch) -> None:
    from docket.intake import accept_task

    fixed_times(monkeypatch, NOW, NOW)
    with Store(tmp_path / "api.sqlite3") as opened:
        answer = accept_task(
            opened,
            client="email",
            key="synthetic-key",
            body={
                "source": "email",
                "title": "Synthetic task",
                "deadline": {"date": "9999-12-31", "time": "23:59", "time_zone": "UTC"},
                "provider": "gmail",
                "message_id": "synthetic/1",
                "link": "https://mail.example/1",
            },
        )
        assert (answer.status, answer.body) == (422, {"error": "invalid_reminder_plan"})
        assert opened.tasks() == []
    monkeypatch.setenv("DOCKET_TIME_ZONE", "UTC")
    result = run("tasks", "add", "Synthetic task", "--due", "9999-12-31", "--at", "23:59")
    assert (result.exit_code, result.stdout, result.stderr) == (
        1,
        "",
        "That time cannot be scheduled for reminders.\n",
    )


@pytest.mark.parametrize("name", ["fall-back", "spring-forward"])
def test_dst_plans_survive_the_store_round_trip(tmp_path, monkeypatch, name) -> None:
    from tests.reminder_cases import CASES, task_for

    case = next(case for case in CASES if case["name"] == name)
    task = task_for(case)
    fixed_times(monkeypatch, case["now"])
    path = tmp_path / "docket.sqlite3"
    with Store(path) as opened:
        core.create_task(
            opened, title="Synthetic task", source="owner", deadline=task.deadline, work=task.work
        )
        assert project(opened.reminders("t1")) == case["expected"]
    with Store(path) as reopened:
        assert project(reopened.reminders("t1")) == case["expected"]
