from datetime import UTC, date, datetime, time
from pathlib import Path

import pytest

from docket import core
from docket.cli import AT_MESSAGE, AT_WITHOUT_DUE_MESSAGE, DUE_MESSAGE, NO_TASKS_MESSAGE
from docket.config import get_settings
from docket.deadlines import Deadline, make_deadline
from docket.store import open_store
from tests.support import fixed_times, run

NY = "America/New_York"
NOW = "2026-11-14T14:00:00+00:00"
CREATED = "2026-11-13T13:00:00+00:00"
UPDATED = "2026-11-13T14:00:00+00:00"


@pytest.fixture(autouse=True)
def home(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCKET_TIME_ZONE", NY)


def seed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Six tasks a person reaches: created, one started, one done, one cancelled."""
    fixed_times(monkeypatch, *([CREATED] * 6 + [UPDATED] * 3))
    with open_store(get_settings()) as store:
        for title, deadline in [
            ("Call the dentist", None),
            ("Book flights", make_deadline(date(2026, 11, 20), None, NY)),
            ("Pay rent", make_deadline(date(2026, 11, 12), time(17, 0), NY)),
            ("Renew passport", make_deadline(date(2026, 11, 9), time(17, 0), NY)),
            ("Water plants", make_deadline(date(2026, 11, 14), time(9, 10), NY)),
            ("Old idea", None),
        ]:
            core.create_task(store, title=title, source="owner", deadline=deadline)
        core.change_state(store, "t2", "start", actor="owner")
        core.change_state(store, "t4", "done", actor="owner")
        core.change_state(store, "t6", "cancel", actor="owner")


def stored():
    with open_store(get_settings()) as store:
        return store.tasks(), [store.audit(task.id) for task in store.tasks()]


def test_the_messages() -> None:
    assert DUE_MESSAGE == "--due must be a date like 2026-11-20."
    assert AT_MESSAGE == "--at must be a time like 17:00."
    assert AT_WITHOUT_DUE_MESSAGE == "--at needs --due."
    assert NO_TASKS_MESSAGE == "No tasks."


@pytest.mark.parametrize(
    ("args", "printed", "deadline"),
    [
        (["Pay rent"], "Added t1: Pay rent\n", None),
        (
            ["Pay rent", "--due", "2026-11-20", "--at", "17:00"],
            "Added t1: Pay rent, due Fri Nov 20 17:00 EST\n",
            Deadline(datetime(2026, 11, 20, 22, 0, tzinfo=UTC), NY, True),
        ),
        (
            ["Pay rent", "--due", "2026-11-20"],
            "Added t1: Pay rent, due Fri Nov 20 17:00 EST, no time given\n",
            Deadline(datetime(2026, 11, 20, 22, 0, tzinfo=UTC), NY, False),
        ),
        (
            ["Pay rent", "--due", "2027-03-14", "--at", "02:30"],
            "Added t1: Pay rent, due Sun Mar 14 2027 03:30 EDT\n",
            Deadline(datetime(2027, 3, 14, 7, 30, tzinfo=UTC), NY, True),
        ),
        (
            ["Pay rent", "--due", "2026-11-01", "--at", "09:00"],
            "Added t1: Pay rent, due Sun Nov 1 09:00 EST\n",
            Deadline(datetime(2026, 11, 1, 14, 0, tzinfo=UTC), NY, True),
        ),
    ],
    ids=["no-deadline", "date-and-time", "date-only", "missing-time-moves-forward", "past-date"],
)
def test_adding_a_task(
    monkeypatch: pytest.MonkeyPatch, args: list[str], printed: str, deadline: Deadline | None
) -> None:
    fixed_times(monkeypatch, NOW)
    result = run("tasks", "add", *args)
    assert (result.exit_code, result.stdout, result.stderr) == (0, printed, "")
    tasks, audits = stored()
    assert [(task.id, task.title, task.state, task.deadline, task.source) for task in tasks] == [
        ("t1", "Pay rent", "open", deadline, "owner")
    ]
    assert [[(entry.action, entry.actor) for entry in audit] for audit in audits] == [
        [("create", "owner")]
    ]


def test_a_title_may_start_with_a_dash(monkeypatch: pytest.MonkeyPatch) -> None:
    fixed_times(monkeypatch, NOW)
    result = run("tasks", "add", "--", "-call back")
    assert (result.exit_code, result.stdout) == (0, "Added t1: -call back\n")


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["Pay rent", "--at", "17:00"], AT_WITHOUT_DUE_MESSAGE),
        (["Pay rent", "--due", "20261120"], DUE_MESSAGE),
        (["Pay rent", "--due", "2026-W47-1"], DUE_MESSAGE),
        (["Pay rent", "--due", "2026-11-31"], DUE_MESSAGE),
        (["Pay rent", "--due", "2026-1-5"], DUE_MESSAGE),
        (["Pay rent", "--due", "２０２６-11-20"], DUE_MESSAGE),
        (["Pay rent", "--due", ""], DUE_MESSAGE),
        (["Pay rent", "--due", "2026-11-20", "--at", "1700"], AT_MESSAGE),
        (["Pay rent", "--due", "2026-11-20", "--at", "17"], AT_MESSAGE),
        (["Pay rent", "--due", "2026-11-20", "--at", "T17:00"], AT_MESSAGE),
        (["Pay rent", "--due", "2026-11-20", "--at", "17:00Z"], AT_MESSAGE),
        (["Pay rent", "--due", "2026-11-20", "--at", "17:00:30"], AT_MESSAGE),
        (["Pay rent", "--due", "2026-11-20", "--at", "24:00"], AT_MESSAGE),
        (["Pay rent", "--due", "2026-11-20", "--at", "7:00"], AT_MESSAGE),
        (["Pay rent", "--due", "20261120", "--at", "1700"], DUE_MESSAGE),
        ([" Pay rent"], "A title is 1 to 100 characters on one line, with no space at either end."),
        (
            ["Pay\trent", "--due", "2026-11-20"],
            "A title is 1 to 100 characters on one line, with no space at either end.",
        ),
    ],
    ids=[
        "at-without-due",
        "compact-date",
        "week-date",
        "no-such-day",
        "unpadded-date",
        "fullwidth-digits",
        "empty-date",
        "compact-time",
        "hour-only",
        "t-prefix",
        "with-zone",
        "with-seconds",
        "hour-24",
        "unpadded-time",
        "date-checked-before-time",
        "title",
        "title-with-a-tab",
    ],
)
def test_a_refused_add_writes_nothing(
    monkeypatch: pytest.MonkeyPatch, args: list[str], message: str
) -> None:
    fixed_times(monkeypatch, NOW)
    result = run("tasks", "add", *args)
    assert (result.exit_code, result.stdout, result.stderr) == (1, "", message + "\n")
    assert stored() == ([], [])


def test_the_list_shows_open_work_soonest_first(monkeypatch: pytest.MonkeyPatch) -> None:
    seed(monkeypatch)
    fixed_times(monkeypatch, NOW)
    result = run("tasks", "list")
    assert (result.exit_code, result.stderr) == (0, "")
    assert result.stdout.splitlines() == [
        "t3    open, overdue         Pay rent  due Thu Nov 12 17:00 EST",
        "t5    open                  Water plants  due Sat Nov 14 09:10 EST",
        "t2    in progress           Book flights  due Fri Nov 20 17:00 EST, no time given",
        "t1    open                  Call the dentist",
    ]


def test_the_full_list_adds_ended_tasks_in_the_same_order(monkeypatch: pytest.MonkeyPatch) -> None:
    seed(monkeypatch)
    fixed_times(monkeypatch, NOW)
    result = run("tasks", "list", "--all")
    assert result.stdout.splitlines() == [
        "t4    done                  Renew passport  due Mon Nov 9 17:00 EST",
        "t3    open, overdue         Pay rent  due Thu Nov 12 17:00 EST",
        "t5    open                  Water plants  due Sat Nov 14 09:10 EST",
        "t2    in progress           Book flights  due Fri Nov 20 17:00 EST, no time given",
        "t1    open                  Call the dentist",
        "t6    cancelled             Old idea",
    ]


def test_tasks_with_one_deadline_keep_their_id_order(monkeypatch: pytest.MonkeyPatch) -> None:
    fixed_times(monkeypatch, CREATED, CREATED, CREATED, NOW)
    friday = make_deadline(date(2026, 11, 20), None, NY)
    with open_store(get_settings()) as store:
        for title in ("Third", "First", "Second"):
            core.create_task(store, title=title, source="owner", deadline=friday)
    result = run("tasks", "list")
    assert [line.split()[0] for line in result.stdout.splitlines()] == ["t1", "t2", "t3"]


def test_an_empty_list_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    fixed_times(monkeypatch, NOW)
    result = run("tasks", "list")
    assert (result.exit_code, result.stdout, result.stderr) == (0, "No tasks.\n", "")
    fixed_times(monkeypatch, NOW)
    assert run("tasks", "list", "--all").stdout == "No tasks.\n"


def test_showing_a_task(monkeypatch: pytest.MonkeyPatch) -> None:
    seed(monkeypatch)
    fixed_times(monkeypatch, NOW)
    result = run("tasks", "show", "t2")
    assert (result.exit_code, result.stderr) == (0, "")
    assert result.stdout.splitlines() == [
        "t2  Book flights",
        "State: in progress",
        "Due: Fri Nov 20 17:00 EST, no time given",
        "Work: none",
        "Source: owner",
        "Created: Fri Nov 13 08:00 EST",
        "Updated: Fri Nov 13 09:00 EST",
    ]


@pytest.mark.parametrize("task_id", ["t9", "x", "T1"], ids=["missing", "malformed", "capital"])
def test_showing_an_unknown_task_is_refused(monkeypatch: pytest.MonkeyPatch, task_id: str) -> None:
    seed(monkeypatch)
    fixed_times(monkeypatch, NOW)
    result = run("tasks", "show", task_id)
    assert (result.exit_code, result.stdout, result.stderr) == (
        1,
        "",
        f"There is no task {task_id}.\n",
    )


@pytest.mark.parametrize(
    "args",
    [["add", "Pay rent"], ["list"], ["show", "t1"]],
    ids=["add", "list", "show"],
)
@pytest.mark.parametrize(
    ("zone", "message"),
    [
        (None, "DOCKET_TIME_ZONE is not set"),
        ("", "DOCKET_TIME_ZONE is not set"),
        ("america/new_york", "DOCKET_TIME_ZONE must be a time zone name"),
    ],
    ids=["unset", "empty", "wrong-case"],
)
def test_every_task_command_needs_your_time_zone(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    args: list[str],
    zone: str | None,
    message: str,
) -> None:
    if zone is None:
        monkeypatch.delenv("DOCKET_TIME_ZONE")
    else:
        monkeypatch.setenv("DOCKET_TIME_ZONE", zone)
    fixed_times(monkeypatch)
    result = run("tasks", *args)
    assert (result.exit_code, result.stdout, result.stderr) == (1, "", message + "\n")
    assert not (tmp_path / "data" / "docket.sqlite3").exists()


@pytest.mark.parametrize(
    ("args", "complaint"),
    [
        (["tasks", "add"], "Missing argument 'title'."),
        (["tasks", "show"], "Missing argument 'task_id'."),
        (["tasks", "list", "extra"], "Got unexpected extra argument(s) (extra)"),
        (["tasks", "nope"], "No such command 'nope'."),
    ],
    ids=["add-without-title", "show-without-id", "list-with-an-argument", "unknown-command"],
)
def test_a_usage_mistake_exits_2_and_writes_nothing(
    monkeypatch: pytest.MonkeyPatch, args: list[str], complaint: str
) -> None:
    fixed_times(monkeypatch)
    result = run(*args)
    assert (result.exit_code, result.stdout) == (2, "")
    assert complaint in result.stderr
    assert not (get_settings().data_dir / "docket.sqlite3").exists()


def test_listing_and_showing_read_the_clock_once(monkeypatch: pytest.MonkeyPatch) -> None:
    seed(monkeypatch)
    fixed_times(monkeypatch, NOW)
    assert run("tasks", "list").exit_code == 0
    fixed_times(monkeypatch, NOW)
    assert run("tasks", "show", "t3").exit_code == 0
    fixed_times(monkeypatch, NOW)
    assert run("tasks", "add", "One more").stdout == "Added t7: One more\n"
