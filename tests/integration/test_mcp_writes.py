"""Phase 6d: create_task, complete_task and cancel_task, through an in-memory MCP client."""

import pytest

from docket import clock, config, core
from docket.store import Store, open_store
from tests.mcp_cases import HOME, Clock, call, listed, refusal, server
from tests.notifier_cases import SyntheticBug

MARK = "Phase 6d given test: remove this marker when the write tools are built"
CREATE_TASK = (
    "Create an approved task, source agent. deadline is null or {date, time, time_zone}: "
    "date YYYY-MM-DD, time HH:MM or null for 17:00, time_zone an IANA name. "
    "The same request_key with the same arguments returns the same task."
)
COMPLETE_TASK = (
    "Mark a task done, as the Done button does; a task already done is no change. "
    "The same request_key returns the first answer."
)
CANCEL_TASK = (
    "Cancel a task, as the Cancel button does; a task already cancelled is no change. "
    "The same request_key returns the first answer."
)
FRIDAY = {"date": "2026-11-20", "time": None, "time_zone": HOME}
TASK_FIELDS = {
    "id": "string",
    "title": "string",
    "state": "string",
    "source": "string",
    "deadline": "null|object",
    "work": "null|object",
    "created_at": "string",
    "updated_at": "string",
}
WRITES = ("cancel_task", "complete_task", "create_task")


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


def owner_task(title: str = "Pay rent") -> None:
    with open_store(config.get_settings()) as store:
        core.create_task(store, title=title, source="owner")


def test_it_lists_three_write_tools_that_are_not_read_only(ticker: Clock) -> None:
    found = tools()
    assert {"get_task", "list_tasks", *WRITES} <= set(found)
    assert (
        found["create_task"].description,
        found["complete_task"].description,
        found["cancel_task"].description,
    ) == (CREATE_TASK, COMPLETE_TASK, CANCEL_TASK)
    for name in WRITES:
        hints = found[name].annotations
        assert (
            hints.read_only_hint,
            hints.destructive_hint,
            hints.idempotent_hint,
            hints.open_world_hint,
        ) == (False, False, True, False), name


def test_the_write_input_schemas(ticker: Clock) -> None:
    found = tools()
    create = found["create_task"].input_schema
    assert shape(create) == (
        {"title": "string", "request_key": "string", "deadline": "null|object"},
        ["request_key", "title"],
    )
    assert create["properties"]["deadline"]["default"] is None
    deadline = create["$defs"]["DeadlineInput"]
    assert shape(deadline, create["$defs"]) == (
        {"date": "string", "time": "null|string", "time_zone": "string"},
        ["date", "time", "time_zone"],
    )
    assert deadline["additionalProperties"] is False
    for name in ("complete_task", "cancel_task"):
        assert shape(found[name].input_schema) == (
            {"id": "string", "request_key": "string"},
            ["id", "request_key"],
        )
    for name in WRITES:
        schema = found[name].input_schema
        for value in [*schema["properties"].values(), *schema.get("$defs", {}).values()]:
            assert "enum" not in value, name


def test_the_write_output_schema_is_the_task_and_whether_it_changed(ticker: Clock) -> None:
    found = tools()
    for name in WRITES:
        schema = found[name].output_schema
        assert shape(schema) == (
            TASK_FIELDS | {"changed": "boolean"},
            sorted([*TASK_FIELDS, "changed"]),
        ), name
        assert sorted(schema["$defs"]) == ["DeadlineResult", "WorkResult"], name


def test_create_task_answers_the_task_and_a_retry_changes_nothing(ticker: Clock) -> None:
    built = server()
    arguments = {"title": "Pay rent", "deadline": FRIDAY, "request_key": "run-1:step-1"}
    expected = {
        "id": "t1",
        "title": "Pay rent",
        "state": "open",
        "source": "agent",
        "deadline": {
            "at": "2026-11-20T22:00:00+00:00",
            "date": "2026-11-20",
            "time": None,
            "time_zone": HOME,
        },
        "work": None,
        "created_at": "2026-11-20T15:00:00+00:00",
        "updated_at": "2026-11-20T15:00:00+00:00",
        "changed": True,
    }
    assert answer(built, "create_task", arguments) == expected
    assert answer(built, "create_task", arguments) == expected | {"changed": False}
    assert answer(built, "create_task", {"title": "Call the bank", "request_key": "r:2"}) == {
        **expected,
        "id": "t2",
        "title": "Call the bank",
        "deadline": None,
    }
    with open_store(config.get_settings()) as store:
        assert [t.id for t in store.tasks()] == ["t1", "t2"]
        assert [(e.action, e.actor) for e in store.audit("t1")] == [("create", "agent")]


def test_complete_and_cancel_answer_the_task(ticker: Clock) -> None:
    owner_task()
    owner_task("Call the bank")
    built = server()
    done = answer(built, "complete_task", {"id": "t1", "request_key": "run-1:step-2"})
    assert (done["id"], done["state"], done["source"], done["changed"]) == (
        "t1",
        "done",
        "owner",
        True,
    )
    again = answer(built, "complete_task", {"id": "t1", "request_key": "run-2:step-1"})
    assert (again["state"], again["changed"]) == ("done", False)
    cancelled = answer(built, "cancel_task", {"id": "t2", "request_key": "run-1:step-3"})
    assert (cancelled["id"], cancelled["state"], cancelled["changed"]) == ("t2", "cancelled", True)
    with open_store(config.get_settings()) as store:
        assert [(e.action, e.actor) for e in store.audit("t1")] == [
            ("create", "owner"),
            ("done", "agent"),
        ]


@pytest.mark.parametrize(
    ("tool", "arguments", "text"),
    [
        (
            "create_task",
            {"title": "Pay rent", "deadline": {**FRIDAY, "date": "2026-02-30"}, "request_key": "k"},
            "Error executing tool create_task: invalid_deadline",
        ),
        (
            "create_task",
            {
                "title": "Pay rent",
                "deadline": {**FRIDAY, "time_zone": "Synthetic/Secret"},
                "request_key": "k",
            },
            "Error executing tool create_task: invalid_deadline",
        ),
        (
            "create_task",
            {"title": "Synthetic secret " * 7, "request_key": "k"},
            "Error executing tool create_task: invalid_title",
        ),
        (
            "create_task",
            {"title": "Pay rent", "request_key": ""},
            "Error executing tool create_task: invalid_key",
        ),
        (
            "create_task",
            {"title": "Pay the rent", "request_key": "used"},
            "Error executing tool create_task: key_reused",
        ),
        (
            "complete_task",
            {"id": "used", "request_key": "fresh"},
            "Error executing tool complete_task: unknown_task",
        ),
        (
            "complete_task",
            {"id": "t1", "request_key": "used"},
            "Error executing tool complete_task: key_reused",
        ),
        (
            "cancel_task",
            {"id": "t99", "request_key": "k"},
            "Error executing tool cancel_task: unknown_task",
        ),
        (
            "cancel_task",
            {"id": "t2", "request_key": "k"},
            "Error executing tool cancel_task: task_ended",
        ),
    ],
    ids=[
        "no-such-day",
        "unknown-zone",
        "long-title",
        "empty-key",
        "create-key-reused",
        "unknown-id",
        "create-key-on-complete",
        "beyond-every-id",
        "ended",
    ],
)
def test_refusals_are_constant_codes(ticker: Clock, tool: str, arguments: dict, text: str) -> None:
    built = server()
    answer(built, "create_task", {"title": "Pay rent", "request_key": "used"})
    owner_task("Call the bank")
    answer(built, "complete_task", {"id": "t2", "request_key": "done-t2"})
    assert refusal(call(built, tool, arguments)) == (True, None, [text])


@pytest.mark.parametrize(
    ("tool", "arguments", "text"),
    [
        (
            "create_task",
            {"title": "Synthetic secret title", "request_key": "k"},
            "Error executing tool create_task",
        ),
        ("complete_task", {"id": "t1", "request_key": "k"}, "Error executing tool complete_task"),
        ("cancel_task", {"id": "t1", "request_key": "k"}, "Error executing tool cancel_task"),
    ],
    ids=["create", "complete", "cancel"],
)
def test_an_unexpected_error_reaches_the_caller_without_its_text(
    ticker: Clock, monkeypatch: pytest.MonkeyPatch, tool: str, arguments: dict, text: str
) -> None:
    owner_task("Synthetic secret title")
    built = server()

    def broken(*args: object, **kwargs: object) -> None:
        raise SyntheticBug("Synthetic secret title")

    monkeypatch.setattr(Store, "request_key", broken)
    assert refusal(call(built, tool, arguments)) == (True, None, [text])
