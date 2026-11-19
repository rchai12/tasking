"""Phase 6a: what list_tasks and get_task answer, through an in-memory MCP client."""

import sqlite3
from datetime import time
from pathlib import Path

import pytest

from docket import clock, config, core, ids, reminders
from docket.deadlines import Deadline, WorkTime
from docket.store import Store, open_store
from tests.mcp_cases import HOME, Clock, add, at, call, refusal, seed, server
from tests.notifier_cases import FakeNotifier, SyntheticBug


@pytest.fixture
def ticker(monkeypatch: pytest.MonkeyPatch) -> Clock:
    """DOCKET_TIME_ZONE is New York and the clock stands at NOW."""
    found = Clock()
    keys = iter(f"k{n}" for n in range(1, 100))
    monkeypatch.setenv("DOCKET_TIME_ZONE", HOME)
    monkeypatch.setattr(clock, "now", found.now)
    monkeypatch.setattr(ids, "new_id", lambda: next(keys))
    return found


def listing(built, status: str, after: str | None = None) -> dict:
    arguments = {"status": status} if after is None else {"status": status, "after": after}
    result = call(built, "list_tasks", arguments)
    assert result.is_error is False
    return result.structured_content


def page(built, status: str, after: str | None = None) -> tuple[list[str], str | None]:
    found = listing(built, status, after)
    return [task["id"] for task in found["tasks"]], found["next_after"]


@pytest.mark.parametrize(
    ("status", "after", "expected", "reads"),
    [
        ("open", None, ["t1", "t2", "t4", "t5", "t8", "t9"], 0),
        ("in_progress", None, ["t3"], 0),
        ("due", None, ["t2", "t4"], 1),
        ("overdue", None, ["t3", "t8", "t9"], 1),
        ("done", None, ["t6"], 0),
        ("cancelled", None, ["t7"], 0),
        ("open", "t5", ["t8", "t9"], 0),
        ("due", "t2", ["t4"], 1),
        ("overdue", "t999", [], 1),
    ],
    ids=[
        "open",
        "in-progress",
        "due-later-today",
        "overdue-includes-exactly-now",
        "done",
        "cancelled",
        "open-after-t5",
        "due-after-t2",
        "after-every-id",
    ],
)
def test_list_tasks_filters_by_status(
    ticker: Clock, status: str, after: str | None, expected: list[str], reads: int
) -> None:
    seed()
    built = server()
    ticker.reads = 0
    assert page(built, status, after) == (expected, None)
    assert ticker.reads == reads


def test_a_listed_task_carries_its_deadline_and_work_time(ticker: Clock) -> None:
    seed()
    built = server()
    assert listing(built, "due") == {
        "tasks": [
            {
                "id": "t2",
                "title": "Synthetic due at five",
                "state": "open",
                "source": "owner",
                "deadline": {
                    "at": "2026-11-20T22:00:00+00:00",
                    "date": "2026-11-20",
                    "time": None,
                    "time_zone": "America/New_York",
                },
                "work": {
                    "start": "2026-11-20T19:00:00+00:00",
                    "minutes": 45,
                    "time_zone": "America/New_York",
                },
                "created_at": "2026-11-20T15:00:00+00:00",
                "updated_at": "2026-11-20T15:00:00+00:00",
            },
            {
                "id": "t4",
                "title": "Synthetic tonight",
                "state": "open",
                "source": "owner",
                "deadline": {
                    "at": "2026-11-21T03:30:00+00:00",
                    "date": "2026-11-20",
                    "time": "22:30",
                    "time_zone": "America/New_York",
                },
                "work": None,
                "created_at": "2026-11-20T15:00:00+00:00",
                "updated_at": "2026-11-20T15:00:00+00:00",
            },
        ],
        "next_after": None,
    }
    assert listing(built, "open")["tasks"][0] == {
        "id": "t1",
        "title": "Synthetic no deadline",
        "state": "open",
        "source": "owner",
        "deadline": None,
        "work": None,
        "created_at": "2026-11-20T15:00:00+00:00",
        "updated_at": "2026-11-20T15:00:00+00:00",
    }


@pytest.mark.parametrize(
    ("moment", "deadlines"),
    [
        ("2026-11-01T04:30", ["2026-11-01T04:15", "2026-11-02T04:45", "2026-11-02T05:15"]),
        ("2027-03-14T05:00", ["2027-03-14T04:30", "2027-03-15T03:30", "2027-03-15T04:30"]),
    ],
    ids=["fall-back-25-hour-day", "spring-forward-23-hour-day"],
)
def test_due_follows_the_home_zones_day_across_daylight_saving(
    ticker: Clock, moment: str, deadlines: list[str]
) -> None:
    """t1 passed minutes ago; t2 is 23:45 or 23:30 local today; t3 is just after local midnight."""
    ticker.moment = at(moment)
    with open_store(config.get_settings()) as store:
        for deadline in deadlines:
            add(store, "Synthetic edge", deadline)
    built = server()
    assert page(built, "due") == (["t2"], None)
    assert page(built, "overdue") == (["t1"], None)
    assert page(built, "open") == (["t1", "t2", "t3"], None)


def test_a_page_holds_fifty_tasks_and_names_the_next(ticker: Clock) -> None:
    with open_store(config.get_settings()) as store:
        for _ in range(50):
            add(store, "Synthetic page")
    built = server()
    tasks, after = page(built, "open")
    assert (len(tasks), tasks[0], tasks[-1], after) == (50, "t1", "t50", None)
    with open_store(config.get_settings()) as store:
        add(store, "Synthetic page")
    tasks, after = page(built, "open")
    assert (len(tasks), tasks[0], tasks[-1], after) == (50, "t1", "t50", "t50")
    assert page(built, "open", "t50") == (["t51"], None)
    assert page(built, "open", "t49") == (["t50", "t51"], None)
    assert page(built, "open", "t51") == ([], None)


@pytest.mark.parametrize(
    ("tool", "arguments", "text"),
    [
        ("list_tasks", {"status": "closed"}, "Error executing tool list_tasks: invalid_status"),
        ("list_tasks", {"status": "Open"}, "Error executing tool list_tasks: invalid_status"),
        ("list_tasks", {"status": ""}, "Error executing tool list_tasks: invalid_status"),
        (
            "list_tasks",
            {"status": "Synthetic secret", "after": "x"},
            "Error executing tool list_tasks: invalid_status",
        ),
        (
            "list_tasks",
            {"status": "open", "after": "t0"},
            "Error executing tool list_tasks: invalid_cursor",
        ),
        (
            "list_tasks",
            {"status": "open", "after": "t01"},
            "Error executing tool list_tasks: invalid_cursor",
        ),
        (
            "list_tasks",
            {"status": "open", "after": "T1"},
            "Error executing tool list_tasks: invalid_cursor",
        ),
        (
            "list_tasks",
            {"status": "open", "after": ""},
            "Error executing tool list_tasks: invalid_cursor",
        ),
        (
            "list_tasks",
            {"status": "open", "after": "Synthetic secret"},
            "Error executing tool list_tasks: invalid_cursor",
        ),
        ("get_task", {"id": "t99"}, "Error executing tool get_task: unknown_task"),
        ("get_task", {"id": "T1"}, "Error executing tool get_task: unknown_task"),
        ("get_task", {"id": "t0"}, "Error executing tool get_task: unknown_task"),
        ("get_task", {"id": "Synthetic secret"}, "Error executing tool get_task: unknown_task"),
    ],
    ids=[
        "unknown-status",
        "status-is-case-sensitive",
        "empty-status",
        "status-checked-before-cursor",
        "cursor-t0",
        "cursor-leading-zero",
        "cursor-capital",
        "cursor-empty",
        "cursor-text",
        "task-beyond-every-id",
        "task-capital",
        "task-t0",
        "task-text",
    ],
)
def test_refusals_are_constant_codes(ticker: Clock, tool: str, arguments: dict, text: str) -> None:
    with open_store(config.get_settings()) as store:
        add(store, "Synthetic only task")
    assert refusal(call(server(), tool, arguments)) == (True, None, [text])


@pytest.mark.parametrize(
    ("tool", "method", "arguments", "text"),
    [
        ("list_tasks", "tasks", {"status": "open"}, "Error executing tool list_tasks"),
        ("get_task", "task", {"id": "t1"}, "Error executing tool get_task"),
    ],
    ids=["list-tasks", "get-task"],
)
def test_an_unexpected_error_reaches_the_caller_without_its_text(
    ticker: Clock, monkeypatch: pytest.MonkeyPatch, tool: str, method: str, arguments, text: str
) -> None:
    with open_store(config.get_settings()) as store:
        add(store, "Synthetic secret title")
    built = server()

    def broken(*args: object, **kwargs: object) -> None:
        raise SyntheticBug("Synthetic secret title")

    monkeypatch.setattr(Store, method, broken)
    assert refusal(call(built, tool, arguments)) == (True, None, [text])


def test_get_task_returns_sent_and_pending_reminders_and_leaves_out_voided(
    ticker: Clock,
) -> None:
    """Due soon and start are sent at 15:06; the 15:07 deadline change voids the rest.

    The pending reminders listed are the ones planned for the new deadline.
    """
    with open_store(config.get_settings()) as store:
        core.create_task(
            store,
            title="Synthetic report",
            source="owner",
            deadline=Deadline(at("2026-11-20T15:20"), HOME, True),
            work=WorkTime(at("2026-11-20T15:05"), 10, HOME),
        )
        ticker.moment = at("2026-11-20T15:06")
        assert reminders.run_pass(store, FakeNotifier(), zone=HOME, at=time(7)).sent == 1
        ticker.moment = at("2026-11-20T15:07")
        core.edit_task(
            store, "t1", actor="owner", deadline=Deadline(at("2026-11-20T22:00"), HOME, False)
        )
    built = server()
    ticker.reads = 0
    result = call(built, "get_task", {"id": "t1"})
    assert result.is_error is False
    assert ticker.reads == 0
    assert result.structured_content == {
        "id": "t1",
        "title": "Synthetic report",
        "state": "open",
        "source": "owner",
        "deadline": {
            "at": "2026-11-20T22:00:00+00:00",
            "date": "2026-11-20",
            "time": None,
            "time_zone": "America/New_York",
        },
        "work": {
            "start": "2026-11-20T15:05:00+00:00",
            "minutes": 10,
            "time_zone": "America/New_York",
        },
        "created_at": "2026-11-20T15:00:00+00:00",
        "updated_at": "2026-11-20T15:07:00+00:00",
        "reminders": [
            {
                "kind": "due_soon",
                "fire_at": "2026-11-20T15:00:00+00:00",
                "sent_at": "2026-11-20T15:06:00+00:00",
            },
            {
                "kind": "start",
                "fire_at": "2026-11-20T15:05:00+00:00",
                "sent_at": "2026-11-20T15:06:00+00:00",
            },
            {"kind": "before", "fire_at": "2026-11-20T21:00:00+00:00", "sent_at": None},
            {"kind": "due", "fire_at": "2026-11-20T22:00:00+00:00", "sent_at": None},
            {"kind": "late", "fire_at": "2026-11-20T22:30:00+00:00", "sent_at": None},
            {"kind": "late", "fire_at": "2026-11-20T23:00:00+00:00", "sent_at": None},
            {"kind": "late", "fire_at": "2026-11-21T00:00:00+00:00", "sent_at": None},
            {"kind": "late", "fire_at": "2026-11-21T01:00:00+00:00", "sent_at": None},
            {"kind": "late", "fire_at": "2026-11-21T02:00:00+00:00", "sent_at": None},
            {"kind": "late", "fire_at": "2026-11-21T06:00:00+00:00", "sent_at": None},
            {"kind": "late", "fire_at": "2026-11-21T10:00:00+00:00", "sent_at": None},
        ],
    }


def dump(path: Path) -> list[str]:
    connection = sqlite3.connect(path)
    try:
        return list(connection.iterdump())
    finally:
        connection.close()


def test_the_tools_write_nothing(ticker: Clock, tmp_path: Path) -> None:
    seed()
    path = tmp_path / "data" / "docket.sqlite3"
    before = dump(path)
    built = server()
    for status in ("open", "in_progress", "due", "overdue", "done", "cancelled", "closed"):
        call(built, "list_tasks", {"status": status})
    for task_id in ("t1", "t2", "t6", "t99"):
        call(built, "get_task", {"id": task_id})
    assert dump(path) == before
