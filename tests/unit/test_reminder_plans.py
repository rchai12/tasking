import copy
import dataclasses
import sqlite3
from datetime import UTC, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from docket import clock, config, ids, store
from docket.deadlines import DeadlineError
from tests.reminder_cases import CASES, projection, task_for


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_the_complete_reminder_plan(case: dict) -> None:
    from docket import reminders

    task = task_for(case)
    before = copy.deepcopy(task)
    result = reminders.plan_reminders(task, datetime.fromisoformat(case["now"]))
    assert type(result) is tuple
    assert all(
        type(row) is reminders.PlannedReminder and row.fire_at.tzinfo is UTC for row in result
    )
    assert projection(result) == case["expected"]
    assert task == before


def test_late_offsets_are_the_seven_decided_real_minute_offsets() -> None:
    from docket import reminders

    assert reminders.LATE_MINUTES == (30, 60, 120, 180, 240, 480, 720)


def test_plan_rows_are_frozen_and_contain_only_kind_and_fire_time() -> None:
    from docket import reminders

    assert [field.name for field in dataclasses.fields(reminders.PlannedReminder)] == [
        "kind",
        "fire_at",
    ]
    row = reminders.PlannedReminder("due", datetime(2026, 11, 20, 18, tzinfo=UTC))
    with pytest.raises(dataclasses.FrozenInstanceError):
        row.kind = "late"
    with pytest.raises(dataclasses.FrozenInstanceError):
        row.fire_at = datetime(2026, 11, 20, 19, tzinfo=UTC)


@pytest.mark.parametrize(
    "moment",
    [
        datetime(2026, 11, 20, 16),
        datetime(2026, 11, 20, 16, tzinfo=timezone(timedelta(hours=1))),
        datetime(2026, 11, 20, 16, tzinfo=ZoneInfo("UTC")),
    ],
    ids=["naive", "non-utc", "zoneinfo-utc"],
)
@pytest.mark.parametrize("state", ["open", "done"])
def test_now_requires_the_existing_canonical_utc_contract(moment: datetime, state: str) -> None:
    from docket import reminders

    case = dict(CASES[0], state=state)
    with pytest.raises(DeadlineError) as raised:
        reminders.plan_reminders(task_for(case), moment)
    assert str(raised.value) == "an instant must be in UTC"
    assert raised.value.__cause__ is None


def test_planning_is_repeatable_and_reads_no_clock_ids_settings_or_database(
    monkeypatch, capsys
) -> None:
    from docket import reminders

    class UnexpectedRead(Exception):
        pass

    def fail(*args, **kwargs):
        raise UnexpectedRead

    monkeypatch.setattr(clock, "now", fail)
    monkeypatch.setattr(ids, "new_id", fail)
    monkeypatch.setattr(config, "get_settings", fail)
    monkeypatch.setattr(sqlite3, "connect", fail)
    monkeypatch.setattr(store.Store, "__init__", fail)
    task = task_for(CASES[0])
    at = datetime(2026, 11, 20, 16, tzinfo=UTC)
    first = reminders.plan_reminders(task, at)
    second = reminders.plan_reminders(task, at)
    assert first == second
    assert projection(second) == CASES[0]["expected"]
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("case_name", ["fall-back", "spring-forward"])
def test_dst_warning_is_one_elapsed_hour_before_due(case_name: str) -> None:
    from docket import reminders

    case = next(case for case in CASES if case["name"] == case_name)
    result = reminders.plan_reminders(task_for(case), datetime.fromisoformat(case["now"]))
    before = next(row.fire_at for row in result if row.kind == "before")
    due = next(row.fire_at for row in result if row.kind == "due")
    assert (due - before).total_seconds() == 3600
