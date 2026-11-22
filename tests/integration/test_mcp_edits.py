"""Phase 6e: change_deadline and plan_work_time, through an in-memory MCP client."""

from datetime import UTC, datetime

import pytest

from docket import clock, config, core
from docket.deadlines import Deadline
from docket.store import Store, open_store
from tests.mcp_cases import HOME, Clock, call, listed, refusal, server
from tests.notifier_cases import SyntheticBug

MARK = "Phase 6e given test: remove this marker when the edit tools are built"
INSTRUCTIONS = (
    "The owner's tasks in docket. list_tasks and get_task only read; the other tools change "
    "tasks once Conductor's step is approved. Each write takes a request_key, and the same key "
    "with the same arguments changes nothing twice."
)
CHANGE_DEADLINE = (
    "Set, move or remove a task's deadline, as the owner's edit does. deadline is null to "
    "remove it, or {date, time, time_zone} as in create_task. Reminders are planned again. "
    "The same request_key with the same arguments returns the first answer."
)
PLAN_WORK_TIME = (
    "Plan or move the one time to work on a task. start is {date, time, time_zone} with time "
    "HH:MM; minutes is 5 to 720; the work must end by midnight and by the deadline. "
    "The same request_key with the same arguments returns the first answer."
)
FRIDAY = {"date": "2026-11-20", "time": None, "time_zone": HOME}
MONDAY = {"date": "2026-11-23", "time": None, "time_zone": HOME}
TWO_PM = {"date": "2026-11-20", "time": "14:00", "time_zone": HOME}
EDITS = ("change_deadline", "plan_work_time")
TASK = {
    "id": "t1",
    "title": "Pay rent",
    "state": "open",
    "source": "owner",
    "deadline": {
        "at": "2026-11-20T22:00:00+00:00",
        "date": "2026-11-20",
        "time": None,
        "time_zone": HOME,
    },
    "work": None,
    "created_at": "2026-11-20T15:00:00+00:00",
    "updated_at": "2026-11-20T15:00:00+00:00",
}


@pytest.fixture
def ticker(monkeypatch: pytest.MonkeyPatch) -> Clock:
    """DOCKET_TIME_ZONE is New York and the clock stands at 10:00 there on 2026-11-20."""
    found = Clock()
    monkeypatch.setenv("DOCKET_TIME_ZONE", HOME)
    monkeypatch.setattr(clock, "now", found.now)
    return found


def joined(schema: dict, defs: dict) -> str:
    if "$ref" in schema:
        return joined(defs[schema["$ref"].rsplit("/", 1)[-1]], defs)
    if "anyOf" in schema:
        found = set()
        for member in schema["anyOf"]:
            found.update(joined(member, defs).split("|"))
        return "|".join(sorted(found))
    return schema.get("type", "any")


def shape(schema: dict, defs: dict | None = None) -> tuple[dict, list]:
    defs = schema.get("$defs", {}) if defs is None else defs
    properties = {name: joined(value, defs) for name, value in schema["properties"].items()}
    return properties, sorted(schema.get("required", []))


def tools() -> dict:
    return {tool.name: tool for tool in listed(server())}


def answer(built, name: str, arguments: dict) -> dict:
    result = call(built, name, arguments)
    assert result.is_error is False, [part.text for part in result.content]
    return result.structured_content


def seed() -> None:
    """t1 is the owner's, due Friday 17:00 in New York; t2 is done."""
    friday = Deadline(datetime(2026, 11, 20, 22, 0, tzinfo=UTC), HOME, False)
    with open_store(config.get_settings()) as store:
        core.create_task(store, title="Pay rent", source="owner", deadline=friday)
        core.create_task(store, title="Call the bank", source="owner")
        core.change_state(store, "t2", "done", actor="owner")


def test_it_lists_the_two_edit_tools_with_the_write_hints(ticker: Clock) -> None:
    assert server().instructions == INSTRUCTIONS
    found = tools()
    assert sorted(found) == [
        "cancel_task",
        "change_deadline",
        "complete_task",
        "create_task",
        "get_task",
        "list_tasks",
        "plan_work_time",
    ]
    assert (found["change_deadline"].description, found["plan_work_time"].description) == (
        CHANGE_DEADLINE,
        PLAN_WORK_TIME,
    )
    for name in EDITS:
        hints = found[name].annotations
        assert (
            hints.read_only_hint,
            hints.destructive_hint,
            hints.idempotent_hint,
            hints.open_world_hint,
        ) == (False, False, True, False), name


def test_the_edit_schemas(ticker: Clock) -> None:
    found = tools()
    change = found["change_deadline"].input_schema
    assert shape(change) == (
        {"id": "string", "request_key": "string", "deadline": "null|object"},
        ["deadline", "id", "request_key"],
    )
    assert "default" not in change["properties"]["deadline"]
    plan = found["plan_work_time"].input_schema
    assert shape(plan) == (
        {"id": "string", "start": "object", "minutes": "integer", "request_key": "string"},
        ["id", "minutes", "request_key", "start"],
    )
    start = plan["$defs"]["WorkStartInput"]
    assert shape(start, plan["$defs"]) == (
        {"date": "string", "time": "string", "time_zone": "string"},
        ["date", "time", "time_zone"],
    )
    assert start["additionalProperties"] is False
    for name in EDITS:
        output = found[name].output_schema
        assert "changed" in output["required"], name
        assert sorted(output["$defs"]) == ["DeadlineResult", "WorkResult"], name


def test_change_deadline_answers_the_task(ticker: Clock) -> None:
    seed()
    built = server()
    arguments = {"id": "t1", "deadline": MONDAY, "request_key": "run-1:step-2"}
    moved = {
        **TASK,
        "deadline": {
            "at": "2026-11-23T22:00:00+00:00",
            "date": "2026-11-23",
            "time": None,
            "time_zone": HOME,
        },
        "changed": True,
    }
    assert answer(built, "change_deadline", arguments) == moved
    assert answer(built, "change_deadline", arguments) == moved | {"changed": False}
    removed = answer(
        built, "change_deadline", {"id": "t1", "deadline": None, "request_key": "run-1:step-3"}
    )
    assert removed == {**TASK, "deadline": None, "changed": True}
    with open_store(config.get_settings()) as store:
        assert [(e.action, e.actor) for e in store.audit("t1")] == [
            ("create", "owner"),
            ("deadline", "agent"),
            ("deadline", "agent"),
        ]


def test_plan_work_time_answers_the_task(ticker: Clock) -> None:
    seed()
    built = server()
    arguments = {"id": "t1", "start": TWO_PM, "minutes": 60, "request_key": "run-1:step-4"}
    planned = {
        **TASK,
        "work": {"start": "2026-11-20T19:00:00+00:00", "minutes": 60, "time_zone": HOME},
        "changed": True,
    }
    assert answer(built, "plan_work_time", arguments) == planned
    assert answer(built, "plan_work_time", arguments) == planned | {"changed": False}


@pytest.mark.parametrize(
    ("tool", "arguments", "code"),
    [
        (
            "change_deadline",
            {"id": "t1", "deadline": {**MONDAY, "date": "2026-02-30"}, "request_key": "k"},
            "invalid_deadline",
        ),
        (
            "change_deadline",
            {
                "id": "t1",
                "deadline": {**MONDAY, "time_zone": "Synthetic/Secret"},
                "request_key": "k",
            },
            "invalid_deadline",
        ),
        (
            "plan_work_time",
            {"id": "t1", "start": TWO_PM, "minutes": 4, "request_key": "k"},
            "invalid_work",
        ),
        (
            "plan_work_time",
            {"id": "t1", "start": {**TWO_PM, "time": "23:30"}, "minutes": 45, "request_key": "k"},
            "invalid_work",
        ),
        (
            "plan_work_time",
            {"id": "t1", "start": {**TWO_PM, "time": "16:30"}, "minutes": 60, "request_key": "k"},
            "work_after_deadline",
        ),
        (
            "change_deadline",
            {"id": "t2", "deadline": MONDAY, "request_key": "k"},
            "task_ended",
        ),
        (
            "plan_work_time",
            {"id": "t99", "start": TWO_PM, "minutes": 60, "request_key": "k"},
            "unknown_task",
        ),
        (
            "change_deadline",
            {"id": "t1", "deadline": None, "request_key": "used"},
            "key_reused",
        ),
        (
            "plan_work_time",
            {"id": "t1", "start": TWO_PM, "minutes": 60, "request_key": "used"},
            "key_reused",
        ),
        (
            "change_deadline",
            {"id": "t1", "deadline": MONDAY, "request_key": ""},
            "invalid_key",
        ),
    ],
    ids=[
        "no-such-day",
        "unknown-zone",
        "too-short",
        "past-midnight",
        "after-the-deadline",
        "ended",
        "beyond-every-id",
        "other-deadline",
        "other-tool",
        "empty-key",
    ],
)
def test_refusals_are_constant_codes(ticker: Clock, tool: str, arguments: dict, code: str) -> None:
    seed()
    built = server()
    answer(built, "change_deadline", {"id": "t1", "deadline": FRIDAY, "request_key": "used"})
    text = f"Error executing tool {tool}: {code}"
    assert refusal(call(built, tool, arguments)) == (True, None, [text])


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("change_deadline", {"id": "t1", "deadline": MONDAY, "request_key": "k"}),
        ("plan_work_time", {"id": "t1", "start": TWO_PM, "minutes": 60, "request_key": "k"}),
    ],
    ids=["change", "plan"],
)
def test_an_unexpected_error_reaches_the_caller_without_its_text(
    ticker: Clock, monkeypatch: pytest.MonkeyPatch, tool: str, arguments: dict
) -> None:
    seed()
    built = server()

    def broken(*args: object, **kwargs: object) -> None:
        raise SyntheticBug("Synthetic secret title")

    monkeypatch.setattr(Store, "request_key", broken)
    assert refusal(call(built, tool, arguments)) == (True, None, [f"Error executing tool {tool}"])
