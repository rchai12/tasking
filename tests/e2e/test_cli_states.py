from datetime import UTC, datetime
from pathlib import Path

import pytest

from docket import core
from docket.config import get_settings
from docket.deadlines import Deadline
from docket.store import open_store
from tests.support import fixed_times, run

NY = "America/New_York"
CREATED = "2026-11-13T13:00:00+00:00"
NOW = "2026-11-14T14:00:00+00:00"
LATER = "2026-11-14T14:30:00+00:00"


@pytest.fixture(autouse=True)
def home(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCKET_TIME_ZONE", NY)


def seed(monkeypatch: pytest.MonkeyPatch, state: str) -> None:
    """t1 'Pay rent', brought to `state` through the core, as a person would."""
    steps = {"open": [], "in_progress": ["start"], "done": ["done"], "cancelled": ["cancel"]}
    fixed_times(monkeypatch, *([CREATED] * (1 + len(steps[state]))))
    with open_store(get_settings()) as store:
        core.create_task(store, title="Pay rent", source="owner")
        for action in steps[state]:
            core.change_state(store, "t1", action, actor="owner")


def stored():
    with open_store(get_settings()) as store:
        task = store.task("t1")
        assert task is not None
        return task.state, [(entry.action, entry.actor) for entry in store.audit("t1")]


@pytest.mark.parametrize(
    ("state", "command", "printed", "after"),
    [
        ("open", "start", "Started t1: Pay rent\n", "in_progress"),
        ("open", "done", "Done t1: Pay rent\n", "done"),
        ("in_progress", "done", "Done t1: Pay rent\n", "done"),
        ("open", "cancel", "Cancelled t1: Pay rent\n", "cancelled"),
        ("in_progress", "cancel", "Cancelled t1: Pay rent\n", "cancelled"),
        ("done", "reopen", "Reopened t1: Pay rent\n", "open"),
        ("cancelled", "reopen", "Reopened t1: Pay rent\n", "open"),
    ],
    ids=[
        "start",
        "done",
        "done-from-in-progress",
        "cancel",
        "cancel-from-in-progress",
        "reopen-done",
        "reopen-cancelled",
    ],
)
def test_a_state_change_is_yours_and_recorded(
    monkeypatch: pytest.MonkeyPatch, state: str, command: str, printed: str, after: str
) -> None:
    seed(monkeypatch, state)
    before = stored()[1]
    fixed_times(monkeypatch, NOW)
    result = run("tasks", command, "t1")
    assert (result.exit_code, result.stdout, result.stderr) == (0, printed, "")
    assert stored() == (after, [*before, (command, "owner")])


@pytest.mark.parametrize(
    ("state", "command", "printed"),
    [
        ("in_progress", "start", "t1 is already in progress.\n"),
        ("done", "done", "t1 is already done.\n"),
        ("cancelled", "cancel", "t1 is already cancelled.\n"),
        ("open", "reopen", "t1 is already open.\n"),
        ("in_progress", "reopen", "t1 is already in progress.\n"),
    ],
    ids=["start", "done", "cancel", "reopen-open", "reopen-in-progress"],
)
def test_a_repeat_says_so_and_writes_nothing(
    monkeypatch: pytest.MonkeyPatch, state: str, command: str, printed: str
) -> None:
    seed(monkeypatch, state)
    before = stored()
    fixed_times(monkeypatch, NOW)
    result = run("tasks", command, "t1")
    assert (result.exit_code, result.stdout, result.stderr) == (0, printed, "")
    assert stored() == before


@pytest.mark.parametrize(
    ("state", "command"),
    [("done", "start"), ("cancelled", "start"), ("cancelled", "done"), ("done", "cancel")],
    ids=["start-done", "start-cancelled", "done-cancelled", "cancel-done"],
)
def test_a_change_to_an_ended_task_is_refused(
    monkeypatch: pytest.MonkeyPatch, state: str, command: str
) -> None:
    seed(monkeypatch, state)
    before = stored()
    fixed_times(monkeypatch, NOW)
    result = run("tasks", command, "t1")
    assert (result.exit_code, result.stdout, result.stderr) == (
        1,
        "",
        "Task t1 has ended; reopen it first.\n",
    )
    assert stored() == before


@pytest.mark.parametrize("command", ["start", "done", "cancel", "reopen"])
@pytest.mark.parametrize("task_id", ["t9", "x", "T1"], ids=["missing", "malformed", "capital"])
def test_an_unknown_task_is_refused(
    monkeypatch: pytest.MonkeyPatch, command: str, task_id: str
) -> None:
    seed(monkeypatch, "open")
    before = stored()
    fixed_times(monkeypatch, NOW)
    result = run("tasks", command, task_id)
    assert (result.exit_code, result.stdout, result.stderr) == (
        1,
        "",
        f"There is no task {task_id}.\n",
    )
    assert stored() == before


def test_pressing_done_twice(monkeypatch: pytest.MonkeyPatch) -> None:
    seed(monkeypatch, "open")
    fixed_times(monkeypatch, NOW, LATER)
    assert run("tasks", "done", "t1").stdout == "Done t1: Pay rent\n"
    assert run("tasks", "done", "t1").stdout == "t1 is already done.\n"
    assert stored() == ("done", [("create", "owner"), ("done", "owner")])


@pytest.mark.parametrize("command", ["start", "done", "cancel", "reopen"])
def test_every_state_command_needs_your_time_zone(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, command: str
) -> None:
    monkeypatch.delenv("DOCKET_TIME_ZONE")
    fixed_times(monkeypatch)
    result = run("tasks", command, "t1")
    assert (result.exit_code, result.stdout, result.stderr) == (
        1,
        "",
        "DOCKET_TIME_ZONE is not set\n",
    )
    assert not (tmp_path / "data" / "docket.sqlite3").exists()


@pytest.mark.parametrize("command", ["start", "done", "cancel", "reopen"])
def test_a_state_command_without_an_id_is_a_usage_mistake(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, command: str
) -> None:
    fixed_times(monkeypatch)
    result = run("tasks", command)
    assert (result.exit_code, result.stdout) == (2, "")
    assert "Missing argument 'task_id'." in result.stderr
    assert not (tmp_path / "data" / "docket.sqlite3").exists()


@pytest.mark.parametrize("command", ["start", "done", "cancel", "reopen"])
def test_a_state_command_reads_only_the_cores_clock(
    monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    seed(monkeypatch, "done" if command == "reopen" else "open")
    fixed_times(monkeypatch, NOW)
    assert run("tasks", command, "t1").exit_code == 0


def test_adding_with_a_deadline_reads_only_the_cores_clock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_times(monkeypatch, NOW)
    result = run("tasks", "add", "Pay rent", "--due", "2026-11-20", "--at", "17:00")
    assert (result.exit_code, result.stdout, result.stderr) == (
        0,
        "Added t1: Pay rent, due Fri Nov 20 17:00 EST\n",
        "",
    )
    with open_store(get_settings()) as store:
        task = store.task("t1")
    assert task is not None
    assert task.deadline == Deadline(datetime(2026, 11, 20, 22, 0, tzinfo=UTC), NY, True)
