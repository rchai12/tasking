"""Phase 6a: the MCP server's names, hints and schemas, as Conductor's tool check reads them."""

import importlib.util

import pytest

from tests.mcp_cases import HOME, listed, server

LIST_TASKS = (
    "List tasks by status: open, in_progress, due (deadline later today), overdue, done or "
    "cancelled. Up to 50 a page; pass next_after back as after for the next page."
)
GET_TASK = "One task by id, with its sent and pending reminders."
INSTRUCTIONS = "The owner's tasks in docket. These tools only read: none of them changes a task."


@pytest.fixture(autouse=True)
def home(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCKET_TIME_ZONE", HOME)


def joined(schema: dict, defs: dict) -> str:
    """A property's JSON types, sorted and joined with |, as Conductor's tool check joins them."""
    if "$ref" in schema:
        return joined(defs[schema["$ref"].rsplit("/", 1)[-1]], defs)
    if "anyOf" in schema:
        found = set()
        for member in schema["anyOf"]:
            found.update(joined(member, defs).split("|"))
        return "|".join(sorted(found))
    return schema.get("type", "any")


def shape(schema: dict, defs: dict | None = None) -> tuple[dict, list]:
    """An object schema as ({property: types}, sorted required names)."""
    defs = schema.get("$defs", {}) if defs is None else defs
    properties = {name: joined(value, defs) for name, value in schema["properties"].items()}
    return properties, sorted(schema.get("required", []))


def tools() -> dict:
    return {tool.name: tool for tool in listed(server())}


def test_the_server_is_named_and_logs_nothing_below_critical() -> None:
    from docket.mcp_server import server as module

    built = server()
    assert (module.SERVER_NAME, module.INSTRUCTIONS) == ("docket", INSTRUCTIONS)
    assert (built.name, built.instructions, built.settings.log_level) == (
        "docket",
        INSTRUCTIONS,
        "CRITICAL",
    )


def test_it_lists_exactly_two_read_only_tools() -> None:
    found = tools()
    assert sorted(found) == ["get_task", "list_tasks"]
    assert (found["list_tasks"].description, found["get_task"].description) == (
        LIST_TASKS,
        GET_TASK,
    )
    for tool in found.values():
        hints = tool.annotations
        assert (
            hints.read_only_hint,
            hints.destructive_hint,
            hints.idempotent_hint,
            hints.open_world_hint,
        ) == (True, False, True, False)


def test_the_input_schemas_take_plain_strings() -> None:
    found = tools()
    assert shape(found["list_tasks"].input_schema) == (
        {"status": "string", "after": "null|string"},
        ["status"],
    )
    assert found["list_tasks"].input_schema["properties"]["after"]["default"] is None
    assert shape(found["get_task"].input_schema) == ({"id": "string"}, ["id"])
    for tool in found.values():
        for value in tool.input_schema["properties"].values():
            assert "enum" not in value
            assert all("enum" not in member for member in value.get("anyOf", []))


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
DEFS = {
    "DeadlineResult": (
        {"at": "string", "date": "string", "time": "null|string", "time_zone": "string"},
        ["at", "date", "time", "time_zone"],
    ),
    "WorkResult": (
        {"start": "string", "minutes": "integer", "time_zone": "string"},
        ["minutes", "start", "time_zone"],
    ),
    "TaskResult": (TASK_FIELDS, sorted(TASK_FIELDS)),
    "ReminderResult": (
        {"kind": "string", "fire_at": "string", "sent_at": "null|string"},
        ["fire_at", "kind", "sent_at"],
    ),
}


def test_the_output_schemas_promise_every_field() -> None:
    found = tools()
    page = found["list_tasks"].output_schema
    assert shape(page) == (
        {"tasks": "array", "next_after": "null|string"},
        ["next_after", "tasks"],
    )
    assert page["properties"]["tasks"]["items"] == {"$ref": "#/$defs/TaskResult"}
    detail = found["get_task"].output_schema
    assert shape(detail) == (
        TASK_FIELDS | {"reminders": "array"},
        sorted([*TASK_FIELDS, "reminders"]),
    )
    assert detail["properties"]["reminders"]["items"] == {"$ref": "#/$defs/ReminderResult"}
    for schema, names in (
        (page, ["DeadlineResult", "TaskResult", "WorkResult"]),
        (detail, ["DeadlineResult", "ReminderResult", "WorkResult"]),
    ):
        defs = schema["$defs"]
        assert sorted(defs) == names
        for name in names:
            assert shape(defs[name], defs) == DEFS[name], name


def test_no_tracing_backend_is_installed() -> None:
    """The SDK's OpenTelemetry API is a no-op without an SDK or exporter; keep it that way."""
    for name in ("opentelemetry.sdk", "opentelemetry.exporter", "opentelemetry.instrumentation"):
        assert importlib.util.find_spec(name) is None, name
