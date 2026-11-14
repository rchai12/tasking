from datetime import UTC, datetime
from pathlib import Path

import pytest

from docket import core
from docket.cli import (
    BOTH_DUES_MESSAGE,
    CLEAR_ALONE_MESSAGE,
    MIDNIGHT_MESSAGE,
    MINUTES_MESSAGE,
    NOTHING_TO_EDIT_MESSAGE,
    PLAN_DATE_MESSAGE,
    PLAN_NEEDS_MESSAGE,
    PLAN_TIME_MESSAGE,
)
from docket.config import get_settings
from docket.deadlines import Deadline, WorkTime
from docket.store import open_store
from tests.support import fixed_times, run

NY = "America/New_York"
CREATED = "2026-11-13T13:00:00+00:00"
NOW = "2026-11-14T14:00:00+00:00"
FRIDAY_5PM = Deadline(datetime(2026, 11, 20, 22, 0, tzinfo=UTC), NY, True)
FRIDAY_WORK = WorkTime(datetime(2026, 11, 20, 19, 0, tzinfo=UTC), 60, NY)
TITLE_SENTENCE = "A title is 1 to 100 characters on one line, with no space at either end."


@pytest.fixture(autouse=True)
def home(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCKET_TIME_ZONE", NY)


def seed(monkeypatch: pytest.MonkeyPatch, *, deadline=None, work=None, state="open") -> None:
    """t1 'Pay rent', reached through the core as a person would."""
    steps = [] if state == "open" else [{"done": "done", "cancelled": "cancel"}[state]]
    fixed_times(monkeypatch, *([CREATED] * (1 + len(steps))))
    with open_store(get_settings()) as store:
        core.create_task(store, title="Pay rent", source="owner", deadline=deadline, work=work)
        for action in steps:
            core.change_state(store, "t1", action, actor="owner")


def stored():
    with open_store(get_settings()) as store:
        task = store.task("t1")
        assert task is not None
        rows = [(entry.action, entry.actor) for entry in store.audit("t1")]
        return (task.title, task.deadline, task.work), rows


def test_the_messages() -> None:
    assert NOTHING_TO_EDIT_MESSAGE == "Give --title, --due or --no-due."
    assert BOTH_DUES_MESSAGE == "--due and --no-due can't be used together."
    assert PLAN_NEEDS_MESSAGE == "Give a date and a start time, or --clear."
    assert CLEAR_ALONE_MESSAGE == "--clear takes no date, start time or --minutes."
    assert PLAN_DATE_MESSAGE == "The date must look like 2026-11-20."
    assert PLAN_TIME_MESSAGE == "The start time must look like 14:00."
    assert MINUTES_MESSAGE == "--minutes must be 5 to 720."
    assert MIDNIGHT_MESSAGE == "A work time must end by midnight."


@pytest.mark.parametrize(
    ("args", "printed", "after", "actions"),
    [
        (
            ["--title", "Pay rent today"],
            "Updated t1: Pay rent today, due Fri Nov 20 17:00 EST\n",
            ("Pay rent today", FRIDAY_5PM, None),
            ["retitle"],
        ),
        (
            ["--due", "2026-11-21", "--at", "09:00"],
            "Updated t1: Pay rent, due Sat Nov 21 09:00 EST\n",
            ("Pay rent", Deadline(datetime(2026, 11, 21, 14, 0, tzinfo=UTC), NY, True), None),
            ["deadline"],
        ),
        (
            ["--due", "2026-11-21"],
            "Updated t1: Pay rent, due Sat Nov 21 17:00 EST, no time given\n",
            ("Pay rent", Deadline(datetime(2026, 11, 21, 22, 0, tzinfo=UTC), NY, False), None),
            ["deadline"],
        ),
        (
            ["--no-due"],
            "Updated t1: Pay rent, no deadline\n",
            ("Pay rent", None, None),
            ["deadline"],
        ),
        (
            ["--title", "Pay rent today", "--no-due"],
            "Updated t1: Pay rent today, no deadline\n",
            ("Pay rent today", None, None),
            ["retitle", "deadline"],
        ),
    ],
    ids=["title", "date-and-time", "date-only", "clear-deadline", "title-and-clear"],
)
def test_editing_a_task(
    monkeypatch: pytest.MonkeyPatch,
    args: list[str],
    printed: str,
    after: tuple[object, ...],
    actions: list[str],
) -> None:
    seed(monkeypatch, deadline=FRIDAY_5PM)
    fixed_times(monkeypatch, NOW)
    result = run("tasks", "edit", "t1", *args)
    assert (result.exit_code, result.stdout, result.stderr) == (0, printed, "")
    found, rows = stored()
    assert found == after
    assert rows == [("create", "owner"), *[(action, "owner") for action in actions]]


@pytest.mark.parametrize(
    "args",
    [["--title", "Pay rent"], ["--due", "2026-11-20", "--at", "17:00"]],
    ids=["same-title", "same-deadline"],
)
def test_an_edit_that_changes_nothing_says_so(
    monkeypatch: pytest.MonkeyPatch, args: list[str]
) -> None:
    seed(monkeypatch, deadline=FRIDAY_5PM)
    before = stored()
    fixed_times(monkeypatch, NOW)
    result = run("tasks", "edit", "t1", *args)
    assert (result.exit_code, result.stdout, result.stderr) == (0, "Nothing changed for t1.\n", "")
    assert stored() == before


@pytest.mark.parametrize(
    ("args", "message"),
    [
        ([], NOTHING_TO_EDIT_MESSAGE),
        (["--due", "2026-11-21", "--no-due"], BOTH_DUES_MESSAGE),
        (["--at", "09:00"], "--at needs --due."),
        (["--no-due", "--at", "09:00"], "--at needs --due."),
        (["--due", "20261121"], "--due must be a date like 2026-11-20."),
        (["--due", "2026-11-21", "--at", "9:00"], "--at must be a time like 17:00."),
        (["--title", " Pay rent"], TITLE_SENTENCE),
        (["--title", ""], TITLE_SENTENCE),
    ],
    ids=[
        "nothing",
        "due-and-no-due",
        "at-alone",
        "at-with-no-due",
        "bad-date",
        "bad-time",
        "bad-title",
        "empty-title",
    ],
)
def test_a_refused_edit_changes_nothing(
    monkeypatch: pytest.MonkeyPatch, args: list[str], message: str
) -> None:
    seed(monkeypatch, deadline=FRIDAY_5PM)
    before = stored()
    fixed_times(monkeypatch, NOW)
    result = run("tasks", "edit", "t1", *args)
    assert (result.exit_code, result.stdout, result.stderr) == (1, "", message + "\n")
    assert stored() == before


@pytest.mark.parametrize(
    ("seeded", "command", "message"),
    [
        (
            {"deadline": FRIDAY_5PM, "work": FRIDAY_WORK},
            ["edit", "t1", "--due", "2026-11-20", "--at", "14:30"],
            "The work time must end by the deadline.",
        ),
        (
            {"deadline": FRIDAY_5PM},
            ["plan", "t1", "2026-11-20", "16:30"],
            "The work time must end by the deadline.",
        ),
        (
            {"state": "done"},
            ["edit", "t1", "--title", "New"],
            "Task t1 has ended; reopen it first.",
        ),
        ({"state": "cancelled"}, ["plan", "t1", "--clear"], "Task t1 has ended; reopen it first."),
        ({}, ["edit", "t9", "--title", "New"], "There is no task t9."),
        ({}, ["plan", "x", "2026-11-20", "14:00"], "There is no task x."),
    ],
    ids=[
        "deadline-before-work-ends",
        "work-past-the-deadline",
        "edit-ended",
        "plan-ended",
        "edit-unknown",
        "plan-unknown",
    ],
)
def test_the_core_refuses_and_nothing_changes(
    monkeypatch: pytest.MonkeyPatch, seeded: dict[str, object], command: list[str], message: str
) -> None:
    seed(monkeypatch, **seeded)
    before = stored()
    fixed_times(monkeypatch, NOW)
    result = run("tasks", *command)
    assert (result.exit_code, result.stdout, result.stderr) == (1, "", message + "\n")
    assert stored() == before


@pytest.mark.parametrize(
    ("args", "minutes_setting", "printed", "work"),
    [
        (
            ["2026-11-20", "14:00"],
            None,
            "Planned t1: Fri Nov 20 14:00 to 15:00 EST\n",
            FRIDAY_WORK,
        ),
        (
            ["2026-11-20", "14:00", "--minutes", "90"],
            None,
            "Planned t1: Fri Nov 20 14:00 to 15:30 EST\n",
            WorkTime(datetime(2026, 11, 20, 19, 0, tzinfo=UTC), 90, NY),
        ),
        (
            ["2026-11-20", "14:00"],
            "45",
            "Planned t1: Fri Nov 20 14:00 to 14:45 EST\n",
            WorkTime(datetime(2026, 11, 20, 19, 0, tzinfo=UTC), 45, NY),
        ),
        (
            ["2027-03-14", "02:30"],
            None,
            "Planned t1: Sun Mar 14 2027 03:30 to 04:30 EDT\n",
            WorkTime(datetime(2027, 3, 14, 7, 30, tzinfo=UTC), 60, NY),
        ),
        (
            ["2026-11-20", "23:00"],
            None,
            "Planned t1: Fri Nov 20 23:00 EST to Sat Nov 21 00:00 EST\n",
            WorkTime(datetime(2026, 11, 21, 4, 0, tzinfo=UTC), 60, NY),
        ),
    ],
    ids=[
        "default-length",
        "minutes",
        "length-setting",
        "missing-time-moves-forward",
        "to-midnight",
    ],
)
def test_planning_a_work_time(
    monkeypatch: pytest.MonkeyPatch,
    args: list[str],
    minutes_setting: str | None,
    printed: str,
    work: WorkTime,
) -> None:
    if minutes_setting is not None:
        monkeypatch.setenv("DOCKET_WORK_MINUTES", minutes_setting)
    seed(monkeypatch)
    fixed_times(monkeypatch, NOW)
    result = run("tasks", "plan", "t1", *args)
    assert (result.exit_code, result.stdout, result.stderr) == (0, printed, "")
    found, rows = stored()
    assert found == ("Pay rent", None, work)
    assert rows == [("create", "owner"), ("work_time", "owner")]


def test_clearing_and_repeating_a_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    seed(monkeypatch, deadline=FRIDAY_5PM, work=FRIDAY_WORK)
    fixed_times(monkeypatch, NOW, NOW, NOW)
    assert run("tasks", "plan", "t1", "2026-11-20", "14:00").stdout == "Nothing changed for t1.\n"
    assert run("tasks", "plan", "t1", "--clear").stdout == "Cleared the work time of t1.\n"
    assert run("tasks", "plan", "t1", "--clear").stdout == "Nothing changed for t1.\n"
    found, rows = stored()
    assert found == ("Pay rent", FRIDAY_5PM, None)
    assert rows == [("create", "owner"), ("work_time", "owner")]


@pytest.mark.parametrize(
    ("args", "message"),
    [
        ([], PLAN_NEEDS_MESSAGE),
        (["2026-11-20"], PLAN_NEEDS_MESSAGE),
        (["--clear", "2026-11-20"], CLEAR_ALONE_MESSAGE),
        (["--clear", "--minutes", "30"], CLEAR_ALONE_MESSAGE),
        (["20261120", "14:00"], PLAN_DATE_MESSAGE),
        (["2026-11-31", "14:00"], PLAN_DATE_MESSAGE),
        (["2026-11-20", "1400"], PLAN_TIME_MESSAGE),
        (["2026-11-20", "24:00"], PLAN_TIME_MESSAGE),
        (["20261120", "1400"], PLAN_DATE_MESSAGE),
        (["2026-11-20", "14:00", "--minutes", "4"], MINUTES_MESSAGE),
        (["2026-11-20", "14:00", "--minutes", "721"], MINUTES_MESSAGE),
        (["2026-11-20", "23:30"], MIDNIGHT_MESSAGE),
        (["2026-11-20", "08:00", "--minutes", "720", "--clear"], CLEAR_ALONE_MESSAGE),
    ],
    ids=[
        "nothing",
        "no-start",
        "clear-with-date",
        "clear-with-minutes",
        "compact-date",
        "no-such-day",
        "compact-time",
        "hour-24",
        "date-checked-before-time",
        "too-short",
        "too-long",
        "past-midnight",
        "clear-with-everything",
    ],
)
def test_a_refused_plan_changes_nothing(
    monkeypatch: pytest.MonkeyPatch, args: list[str], message: str
) -> None:
    seed(monkeypatch)
    before = stored()
    fixed_times(monkeypatch, NOW)
    result = run("tasks", "plan", "t1", *args)
    assert (result.exit_code, result.stdout, result.stderr) == (1, "", message + "\n")
    assert stored() == before


def test_a_length_that_is_not_a_number_is_a_usage_mistake(monkeypatch: pytest.MonkeyPatch) -> None:
    seed(monkeypatch)
    fixed_times(monkeypatch)
    result = run("tasks", "plan", "t1", "2026-11-20", "14:00", "--minutes", "ninety")
    assert (result.exit_code, result.stdout) == (2, "")
    assert "Invalid value for '--minutes'" in result.stderr


@pytest.mark.parametrize(
    "args",
    [["edit", "t1", "--title", "New"], ["plan", "t1", "2026-11-20", "14:00"]],
    ids=["edit", "plan"],
)
def test_edit_and_plan_need_your_time_zone(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, args: list[str]
) -> None:
    monkeypatch.delenv("DOCKET_TIME_ZONE")
    fixed_times(monkeypatch)
    result = run("tasks", *args)
    assert (result.exit_code, result.stdout, result.stderr) == (
        1,
        "",
        "DOCKET_TIME_ZONE is not set\n",
    )
    assert not (tmp_path / "data" / "docket.sqlite3").exists()


@pytest.mark.parametrize(
    "args",
    [["edit", "t1", "--due", "2026-11-21"], ["plan", "t1", "2026-11-20", "14:00"]],
    ids=["edit", "plan"],
)
def test_edit_and_plan_read_only_the_cores_clock(
    monkeypatch: pytest.MonkeyPatch, args: list[str]
) -> None:
    seed(monkeypatch)
    fixed_times(monkeypatch, NOW)
    assert run("tasks", *args).exit_code == 0
