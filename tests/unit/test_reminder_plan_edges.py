from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from docket.deadlines import Deadline, WorkTime
from docket.reminders import plan_reminders
from docket.store import Task


def _task(**changes: object) -> Task:
    values: dict[str, object] = {
        "id": "t1",
        "title": "Synthetic task",
        "state": "open",
        "deadline": None,
        "work": None,
        "source": "owner",
        "provider": None,
        "message_id": None,
        "link": None,
        "created_at": datetime(2026, 10, 1, tzinfo=UTC),
        "updated_at": datetime(2026, 10, 1, tzinfo=UTC),
    }
    values.update(changes)
    return Task(**values)


def test_terminal_and_undated_tasks_skip_arithmetic_at_the_limit() -> None:
    moment = datetime.max.replace(tzinfo=UTC)
    deadline = Deadline(moment, "America/New_York", True)
    done = _task(state="done", deadline=deadline)
    undated = _task()
    assert plan_reminders(done, moment) == ()
    assert plan_reminders(undated, moment) == ()
    assert done.deadline == deadline


def test_a_late_slot_past_the_representable_range_raises() -> None:
    due = datetime.max.replace(tzinfo=UTC)
    task = _task(deadline=Deadline(due, "America/New_York", True))
    with pytest.raises(OverflowError):
        plan_reminders(task, due - timedelta(days=1))
    assert task.deadline is not None
    assert task.deadline.at == due


def test_a_changed_snapshot_is_planned_again() -> None:
    now = datetime(2026, 11, 20, 16, tzinfo=UTC)
    task = _task(
        deadline=Deadline(datetime(2026, 11, 20, 18, tzinfo=UTC), "America/New_York", True)
    )
    first = plan_reminders(task, now)
    changed = replace(
        task,
        deadline=Deadline(datetime(2026, 11, 20, 20, tzinfo=UTC), "America/New_York", True),
        work=WorkTime(datetime(2026, 11, 20, 16, 30, tzinfo=UTC), 5, "America/New_York"),
    )
    second = plan_reminders(changed, now)
    assert task.id == changed.id
    assert [row.fire_at for row in second if row.kind == "before"] == [
        datetime(2026, 11, 20, 19, tzinfo=UTC)
    ]
    assert [row.fire_at for row in second if row.kind == "start"] == [
        datetime(2026, 11, 20, 16, 30, tzinfo=UTC)
    ]
    assert first != second
