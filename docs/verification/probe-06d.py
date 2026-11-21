"""Synthetic MCP write properties: one change per request_key, a reused key refused, no loss."""

import asyncio
import os
import random
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

HOME = "America/New_York"
START = datetime(2026, 10, 31, 12, tzinfo=UTC)
TITLES = ("Synthetic probe task", "Synthetic other task")
DEADLINES = (
    None,
    {"date": "2026-11-01", "time": "01:30", "time_zone": HOME},
    {"date": "2026-11-20", "time": None, "time_zone": HOME},
)
WRITES = ("cancel_task", "complete_task", "create_task")
ENDS = {"complete_task": "done", "cancel_task": "cancelled"}
MISSING = "t9999"


class Model:
    """The oracle: task states and the kept keys, from its own tables alone."""

    def __init__(self) -> None:
        self.states: dict[str, str] = {}
        self.keys: dict[str, tuple[str, dict, str]] = {}
        self.changes = 0

    def expect(self, tool: str, arguments: dict) -> tuple[str, str | None, bool | None]:
        """("ok", task id, changed) or ("refused", code, None); applies the change it expects."""
        key = arguments["request_key"]
        request = {name: value for name, value in arguments.items() if name != "request_key"}
        if tool == "create_task":
            request.setdefault("deadline", None)
        if key in self.keys:
            kept_tool, kept, task_id = self.keys[key]
            if (kept_tool, kept) != (tool, request):
                return ("refused", "key_reused", None)
            return ("ok", task_id, False)
        if tool == "create_task":
            task_id = f"t{len(self.states) + 1}"
            self.states[task_id] = "open"
            self.keys[key] = (tool, request, task_id)
            self.changes += 1
            return ("ok", task_id, True)
        task_id = request["id"]
        state = self.states.get(task_id)
        if state is None:
            return ("refused", "unknown_task", None)
        if state == ENDS[tool]:
            self.keys[key] = (tool, request, task_id)
            return ("ok", task_id, False)
        if state in ENDS.values():
            return ("refused", "task_ended", None)
        self.states[task_id] = ENDS[tool]
        self.keys[key] = (tool, request, task_id)
        self.changes += 1
        return ("ok", task_id, True)


def oracle() -> None:
    model = Model()
    create = {"title": "A", "deadline": None, "request_key": "r:1"}
    assert model.expect("create_task", create) == ("ok", "t1", True)
    assert model.expect("create_task", {"title": "A", "request_key": "r:1"}) == ("ok", "t1", False)
    assert model.expect("create_task", {"title": "B", "request_key": "r:1"})[1] == "key_reused"
    done = {"id": "t1", "request_key": "r:2"}
    assert model.expect("complete_task", done) == ("ok", "t1", True)
    assert model.expect("complete_task", done) == ("ok", "t1", False)
    assert model.expect("cancel_task", done)[1] == "key_reused"
    assert model.expect("cancel_task", {"id": "t1", "request_key": "r:3"})[1] == "task_ended"
    assert "r:3" not in model.keys
    assert model.expect("complete_task", {"id": "t1", "request_key": "r:4"}) == ("ok", "t1", False)
    assert model.expect("complete_task", {"id": MISSING, "request_key": "r:5"})[1] == "unknown_task"
    assert "r:5" not in model.keys
    model.states["t1"] = "open"
    assert model.expect("complete_task", done) == ("ok", "t1", False)
    assert (model.states["t1"], model.changes) == ("open", 2)


class World:
    """One data folder, the clock and the ids, and counts of the cases the walk reached."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.path = root / "data" / "docket.sqlite3"
        self.moment = START
        self.ids = 0
        self.reached = {
            "created": 0,
            "replayed": 0,
            "reused": 0,
            "ended": 0,
            "unknown": 0,
            "no-change": 0,
            "after-reopen": 0,
            "restart": 0,
        }

    def now(self) -> datetime:
        self.moment += timedelta(minutes=1)
        return self.moment

    def new_id(self) -> str:
        self.ids += 1
        return f"k{self.ids}"

    def stored(self) -> tuple[dict[str, str], int, int]:
        with sqlite3.connect(self.path) as db:
            states = dict(db.execute("SELECT 't' || number, state FROM tasks").fetchall())
            keys = db.execute("SELECT count(*) FROM request_keys").fetchone()[0]
            changes = db.execute(
                "SELECT count(*) FROM audit_log WHERE actor = 'agent' AND action IN "
                "('create', 'done', 'cancel')"
            ).fetchone()[0]
        return states, keys, changes


def arguments_for(model: Model, rng: random.Random, step: int) -> tuple[str, dict]:
    """A write: a new key, a kept key with its own request, or a kept key with another one."""
    tool = rng.choice(WRITES)
    kept = list(model.keys)
    roll = rng.random()
    if kept and roll < 0.25:
        key = rng.choice(kept)
        kept_tool, request, _ = model.keys[key]
        return kept_tool, {**request, "request_key": key}
    key = rng.choice(kept) if kept and roll < 0.4 else f"run-{step}:step-{rng.randint(1, 9)}"
    if tool == "create_task":
        arguments = {"title": rng.choice(TITLES), "request_key": key}
        deadline = rng.choice(DEADLINES)
        if deadline is not None or rng.random() < 0.5:
            arguments["deadline"] = deadline
        return tool, arguments
    count = len(model.states)
    task_id = MISSING if rng.random() < 0.1 or count == 0 else f"t{rng.randint(1, count)}"
    return tool, {"id": task_id, "request_key": key}


async def write(client, world: World, model: Model, tool: str, arguments: dict, step: int) -> None:
    known = arguments["request_key"] in model.keys
    kind, value, changed = model.expect(tool, arguments)
    result = await client.call_tool(tool, arguments)
    where = f"step {step} {tool} key {arguments['request_key']}"
    if kind == "refused":
        text = " ".join(part.text for part in result.content)
        assert result.is_error, f"{where}: expected {value}, the call succeeded"
        assert text == f"Error executing tool {tool}: {value}", (
            f"{where}: expected {value}, answered {text[-40:]!r}"
        )
        name = {"key_reused": "reused", "task_ended": "ended", "unknown_task": "unknown"}[value]
        world.reached[name] += 1
        return
    assert not result.is_error, f"{where}: expected {value} changed {changed}, it was refused"
    found = result.structured_content
    assert (found["id"], found["changed"]) == (value, changed), (
        f"{where}: expected {value} changed {changed}, got {found['id']} {found['changed']}"
    )
    assert found["state"] == model.states[value], (
        f"{where}: {value} answered {found['state']}, the model holds {model.states[value]}"
    )
    world.reached["created"] += tool == "create_task" and bool(changed)
    world.reached["replayed"] += known
    world.reached["no-change"] += tool != "create_task" and not changed


def owner(world: World, model: Model, rng: random.Random) -> None:
    """The owner reopens or starts a task, as a press would; the model follows."""
    from docket import config, core
    from docket.store import open_store

    if not model.states:
        return
    task_id = f"t{rng.randint(1, len(model.states))}"
    action = "reopen" if model.states[task_id] in ENDS.values() else "start"
    with open_store(config.get_settings()) as store:
        core.change_state(store, task_id, action, actor="owner")
    model.states[task_id] = "open" if action == "reopen" else "in_progress"
    world.reached["after-reopen"] += action == "reopen"


async def batch(built, world: World, model: Model, rng: random.Random, step: int) -> None:
    from mcp.client import Client

    async with Client(built) as client:
        for _ in range(rng.randint(3, 8)):
            tool, arguments = arguments_for(model, rng, step)
            await write(client, world, model, tool, arguments, step)
            if rng.random() < 0.3:
                await write(client, world, model, tool, arguments, step)


def walk(root: Path, seed: int, steps: int) -> World:
    from docket import clock, config, ids
    from docket.mcp_server import server as module

    world = World(root)
    model = Model()
    rng = random.Random(seed)
    environment = {
        "DOCKET_DATA_DIR": str(root / "data"),
        "DOCKET_TIME_ZONE": HOME,
        "HOME": str(root),
    }
    with (
        patch.dict(os.environ, environment),
        patch.object(clock, "now", world.now),
        patch.object(ids, "new_id", world.new_id),
    ):
        built = module.build_server(config.get_settings())
        for step in range(steps):
            asyncio.run(batch(built, world, model, rng, step))
            if rng.random() < 0.4:
                owner(world, model, rng)
            if step % 5 == 4:
                built = module.build_server(config.get_settings())
                world.reached["restart"] += 1
            states, keys, changes = world.stored()
            assert states == model.states, f"step {step}: the stored states differ from the model"
            assert keys == len(model.keys), (
                f"step {step}: {keys} request keys stored, the model kept {len(model.keys)}"
            )
            assert changes == model.changes, (
                f"step {step}: {changes} agent changes audited, the model made {model.changes}"
            )
    assert MISSING not in model.states, f"{MISSING} was created; it must lie beyond every id"
    return world


async def hints(built) -> None:
    from mcp.client import Client

    async with Client(built) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}
    assert {*WRITES, "get_task", "list_tasks"} <= set(tools), (
        f"listed {sorted(tools)}, expected the two read tools and the three writes among them"
    )
    for name in WRITES:
        found = tools[name].annotations
        assert found is not None and not found.read_only_hint, f"{name} is marked read-only"
        assert found.idempotent_hint and not found.destructive_hint, f"{name}: wrong hints"
        assert tools[name].output_schema, f"{name} declares no output schema"
        assert "request_key" in tools[name].input_schema["required"], f"{name}: no request_key"


def listing(root: Path) -> None:
    from docket import config
    from docket.mcp_server import server as module

    environment = {
        "DOCKET_DATA_DIR": str(root / "data"),
        "DOCKET_TIME_ZONE": HOME,
        "HOME": str(root),
    }
    with patch.dict(os.environ, environment):
        asyncio.run(hints(module.build_server(config.get_settings())))


def scripted(root: Path) -> None:
    reached = walk(root, 6, 40).reached
    for name, least in (
        ("created", 5),
        ("replayed", 5),
        ("reused", 3),
        ("ended", 1),
        ("unknown", 1),
        ("no-change", 3),
        ("after-reopen", 1),
        ("restart", 3),
    ):
        assert reached[name] >= least, f"{name} reached {reached[name]} < {least}"


def randomized(root: Path) -> None:
    walk(root, 61, 60)


def leaf(error: BaseException) -> BaseException:
    """The first error inside the task groups the MCP client wraps a failure in."""
    while isinstance(error, BaseExceptionGroup):
        error = error.exceptions[0]
    return error


def main() -> None:
    oracle()
    print("writes oracle ok")
    if "--oracle-only" in sys.argv:
        print("FAILURES 0")
        return
    failures = 0
    for name, check in (
        ("listing", listing),
        ("scripted walk", scripted),
        ("random walk", randomized),
    ):
        with TemporaryDirectory() as directory:
            try:
                check(Path(directory))
            except Exception as raised:
                error = leaf(raised)
                detail = str(error) if isinstance(error, AssertionError) else ""
                print(
                    f"FAIL {name}: expected one change per request_key and the store to match "
                    f"the model; {detail or type(error).__name__}"
                )
                failures += 1
            else:
                print(name + " ok")
    print(f"FAILURES {failures}")


if __name__ == "__main__":
    main()
