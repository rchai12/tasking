"""Synthetic MCP edit properties: one change per request_key, the work-time rules, no loss."""

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
MISSING = "t9999"
ENDS = {"complete_task": "done", "cancel_task": "cancelled"}
EDITS = ("change_deadline", "plan_work_time")
TOOLS = ("create_task", "complete_task", "cancel_task", *EDITS)


def at(text: str) -> datetime:
    return datetime.fromisoformat(text)


def day(date: str, time: str | None) -> dict:
    return {"date": date, "time": time, "time_zone": HOME}


# Each deadline argument, and the instant and time-given flag it must be stored as.
DEADLINES = (
    (None, None),
    (day("2026-11-20", None), (at("2026-11-20T22:00:00+00:00"), False)),
    (day("2026-11-20", "17:00"), (at("2026-11-20T22:00:00+00:00"), True)),
    (day("2026-11-20", "12:00"), (at("2026-11-20T17:00:00+00:00"), True)),
    (day("2026-11-23", None), (at("2026-11-23T22:00:00+00:00"), False)),
    (day("2026-11-01", "01:30"), (at("2026-11-01T05:30:00+00:00"), True)),
    (day("2026-02-30", None), "invalid"),
)
# Each work-time argument, and the start and end instants it must be stored as.
WORKS = (
    ((day("2026-11-20", "09:00"), 60), (at("2026-11-20T14:00:00+00:00"), 60)),
    ((day("2026-11-20", "14:00"), 60), (at("2026-11-20T19:00:00+00:00"), 60)),
    ((day("2026-11-20", "16:30"), 60), (at("2026-11-20T21:30:00+00:00"), 60)),
    ((day("2026-11-20", "11:30"), 30), (at("2026-11-20T16:30:00+00:00"), 30)),
    ((day("2026-11-20", "23:30"), 45), "invalid"),
    ((day("2026-11-20", "14:00"), 4), "invalid"),
)


def stored_deadline(value: object) -> object:
    for argument, stored in DEADLINES:
        if argument == value:
            return stored
    raise AssertionError(f"the probe has no deadline {value}")


def stored_work(start: object, minutes: object) -> object:
    for (argument, length), stored in WORKS:
        if (argument, length) == (start, minutes):
            return stored
    raise AssertionError(f"the probe has no work time {start} {minutes}")


def late(deadline: object, work: object) -> bool:
    """A work time that ends after the deadline: the one rule core refuses on an edit."""
    if deadline is None or work is None:
        return False
    start, minutes = work
    return start + timedelta(minutes=minutes) > deadline[0]


class Model:
    """The oracle: each task's state, deadline and work time, and the kept keys."""

    def __init__(self) -> None:
        self.tasks: dict[str, dict] = {}
        self.keys: dict[str, tuple[dict, str]] = {}
        self.changes = 0

    def expect(self, tool: str, arguments: dict) -> tuple[str, str | None, bool | None]:
        """("ok", task id, changed) or ("refused", code, None); applies the change it expects."""
        key = arguments["request_key"]
        request = {"tool": tool, **{n: v for n, v in arguments.items() if n != "request_key"}}
        if tool == "create_task":
            request.setdefault("deadline", None)
        value = None
        if tool in ("create_task", "change_deadline"):
            value = stored_deadline(request["deadline"])
            if value == "invalid":
                return ("refused", "invalid_deadline", None)
        if tool == "plan_work_time":
            value = stored_work(request["start"], request["minutes"])
            if value == "invalid":
                return ("refused", "invalid_work", None)
        if key in self.keys:
            kept, task_id = self.keys[key]
            if kept != request:
                return ("refused", "key_reused", None)
            return ("ok", task_id, False)
        if tool == "create_task":
            task_id = f"t{len(self.tasks) + 1}"
            self.tasks[task_id] = {"state": "open", "deadline": value, "work": None}
            return self.keep(key, request, task_id, True)
        task_id = request["id"]
        task = self.tasks.get(task_id)
        if task is None:
            return ("refused", "unknown_task", None)
        ended = task["state"] in ENDS.values()
        if tool in ENDS:
            if task["state"] == ENDS[tool]:
                return self.keep(key, request, task_id, False)
            if ended:
                return ("refused", "task_ended", None)
            task["state"] = ENDS[tool]
            return self.keep(key, request, task_id, True)
        if ended:
            return ("refused", "task_ended", None)
        field = "deadline" if tool == "change_deadline" else "work"
        after = {**task, field: value}
        if late(after["deadline"], after["work"]):
            return ("refused", "work_after_deadline", None)
        if task[field] == value:
            return self.keep(key, request, task_id, False)
        task[field] = value
        return self.keep(key, request, task_id, True)

    def keep(self, key: str, request: dict, task_id: str, changed: bool) -> tuple:
        self.keys[key] = (request, task_id)
        self.changes += changed
        return ("ok", task_id, changed)


def oracle() -> None:
    model = Model()
    friday, noon, monday = DEADLINES[1][0], DEADLINES[3][0], DEADLINES[4][0]
    two_pm, half_four = WORKS[1][0][0], WORKS[2][0][0]
    assert DEADLINES[1][1] == (at("2026-11-20T22:00:00+00:00"), False)
    assert model.expect("create_task", {"title": "A", "deadline": friday, "request_key": "a"}) == (
        "ok",
        "t1",
        True,
    )
    move = {"id": "t1", "deadline": monday, "request_key": "b"}
    assert model.expect("change_deadline", move) == ("ok", "t1", True)
    plan = {"id": "t1", "start": half_four, "minutes": 60, "request_key": "c"}
    assert model.expect("plan_work_time", plan) == ("ok", "t1", True)
    back = {"id": "t1", "deadline": friday, "request_key": "d"}
    assert model.expect("change_deadline", back)[1] == "work_after_deadline"
    assert "d" not in model.keys
    edge = {"id": "t1", "start": WORKS[3][0][0], "minutes": 30, "request_key": "e"}
    assert model.expect("plan_work_time", edge) == ("ok", "t1", True)
    assert model.expect("change_deadline", {**back, "deadline": noon}) == ("ok", "t1", True)
    bad = {"id": "t1", "start": two_pm, "minutes": 4, "request_key": "b"}
    assert model.expect("plan_work_time", bad)[1] == "invalid_work"
    assert model.expect("plan_work_time", {**bad, "minutes": 60})[1] == "key_reused"
    model.tasks["t1"]["deadline"] = None
    assert model.expect("change_deadline", move) == ("ok", "t1", False)
    assert model.tasks["t1"]["deadline"] is None
    assert model.expect("complete_task", {"id": "t1", "request_key": "f"}) == ("ok", "t1", True)
    assert model.expect("change_deadline", {**move, "request_key": "g"})[1] == "task_ended"
    assert model.expect("plan_work_time", {**plan, "id": MISSING, "request_key": "h"})[1] == (
        "unknown_task"
    )
    assert model.changes == 6


class World:
    """One data folder, the clock and the ids, and counts of the cases the walk reached."""

    def __init__(self, root: Path) -> None:
        self.path = root / "data" / "docket.sqlite3"
        self.moment = START
        self.ids = 0
        self.reached = {
            name: 0
            for name in (
                "moved",
                "planned",
                "replayed",
                "after-owner",
                "work_after_deadline",
                "invalid",
                "key_reused",
                "task_ended",
                "unknown_task",
                "restart",
            )
        }

    def now(self) -> datetime:
        self.moment += timedelta(seconds=7)
        return self.moment

    def new_id(self) -> str:
        self.ids += 1
        return f"k{self.ids}"

    def stored(self) -> tuple[dict[str, dict], int, int]:
        with sqlite3.connect(self.path) as db:
            rows = db.execute(
                "SELECT number, state, deadline_at, deadline_time_given, work_start, work_minutes "
                "FROM tasks"
            ).fetchall()
            keys = db.execute("SELECT count(*) FROM request_keys").fetchone()[0]
            changes = db.execute("SELECT count(*) FROM audit_log WHERE actor = 'agent'").fetchone()[
                0
            ]
        tasks = {
            f"t{number}": {
                "state": state,
                "deadline": None if when is None else (at(when), bool(given)),
                "work": None if start is None else (at(start), minutes),
            }
            for number, state, when, given, start, minutes in rows
        }
        return tasks, keys, changes


def arguments_for(model: Model, rng: random.Random, step: int) -> tuple[str, dict]:
    kept = list(model.keys)
    if kept and rng.random() < 0.2:
        key = rng.choice(kept)
        request, _ = model.keys[key]
        tool = request["tool"]
        return tool, {**{n: v for n, v in request.items() if n != "tool"}, "request_key": key}
    tool = rng.choice(TOOLS + EDITS + EDITS)
    key = rng.choice(kept) if kept and rng.random() < 0.15 else f"run-{step}:{rng.randint(1, 99)}"
    if tool == "create_task":
        deadline = rng.choice(DEADLINES[:-1])[0]
        return tool, {"title": "Synthetic probe task", "deadline": deadline, "request_key": key}
    count = len(model.tasks)
    task_id = MISSING if count == 0 or rng.random() < 0.05 else f"t{rng.randint(1, count)}"
    if tool == "change_deadline":
        return tool, {"id": task_id, "deadline": rng.choice(DEADLINES)[0], "request_key": key}
    if tool == "plan_work_time":
        (start, minutes), _ = rng.choice(WORKS)
        return tool, {"id": task_id, "start": start, "minutes": minutes, "request_key": key}
    return tool, {"id": task_id, "request_key": key}


async def write(client, world: World, model: Model, tool: str, arguments: dict, step: int) -> None:
    known = arguments["request_key"] in model.keys
    before = {name: dict(task) for name, task in model.tasks.items()}
    kind, value, changed = model.expect(tool, arguments)
    result = await client.call_tool(tool, arguments)
    where = f"step {step} {tool} key {arguments['request_key']}"
    text = " ".join(part.text for part in result.content)
    if kind == "refused":
        assert result.is_error, f"{where}: expected {value}, the call succeeded"
        assert text == f"Error executing tool {tool}: {value}", (
            f"{where}: expected {value}, answered {text[-40:]!r}"
        )
        world.reached["invalid" if value.startswith("invalid_") else value] += 1
        return
    assert not result.is_error, f"{where}: expected {value} changed {changed}, got {text[-40:]!r}"
    found = result.structured_content
    assert (found["id"], found["changed"]) == (value, changed), (
        f"{where}: expected {value} changed {changed}, got {found['id']} {found['changed']}"
    )
    world.reached["replayed"] += known
    if known and tool in EDITS:
        field = "deadline" if tool == "change_deadline" else "work"
        asked = (
            stored_deadline(arguments["deadline"])
            if field == "deadline"
            else stored_work(arguments["start"], arguments["minutes"])
        )
        world.reached["after-owner"] += before[value][field] != asked
    world.reached["moved"] += tool == "change_deadline" and bool(changed)
    world.reached["planned"] += tool == "plan_work_time" and bool(changed)


def owner(model: Model, rng: random.Random) -> None:
    """The owner reopens a task, or clears its deadline and work time, as a command would."""
    from docket import config, core
    from docket.store import open_store

    if not model.tasks:
        return
    task_id = f"t{rng.randint(1, len(model.tasks))}"
    task = model.tasks[task_id]
    with open_store(config.get_settings()) as store:
        if task["state"] in ENDS.values():
            core.change_state(store, task_id, "reopen", actor="owner")
            task["state"] = "open"
        else:
            core.edit_task(store, task_id, actor="owner", deadline=None, work=None)
            task["deadline"] = task["work"] = None


async def batch(built, world: World, model: Model, rng: random.Random, step: int) -> None:
    from mcp.client import Client

    async with Client(built) as client:
        for _ in range(rng.randint(3, 8)):
            tool, arguments = arguments_for(model, rng, step)
            await write(client, world, model, tool, arguments, step)
            if rng.random() < 0.25:
                await write(client, world, model, tool, arguments, step)


async def forced(built, world: World, model: Model) -> None:
    """A move, the owner clearing it, and the same step again: it must change nothing. Then a
    work time that ends exactly at the deadline, which is allowed."""
    from mcp.client import Client

    move = {"id": "t1", "deadline": DEADLINES[4][0], "request_key": "forced:2"}
    async with Client(built) as client:
        create = {"title": "Synthetic forced task", "deadline": None, "request_key": "forced:1"}
        await write(client, world, model, "create_task", create, 0)
        await write(client, world, model, "change_deadline", move, 0)
    owner(model, random.Random(0))
    async with Client(built) as client:
        await write(client, world, model, "change_deadline", move, 0)
        noon = {"id": "t1", "deadline": DEADLINES[3][0], "request_key": "forced:3"}
        await write(client, world, model, "change_deadline", noon, 0)
        (start, minutes), _ = WORKS[3]
        edge = {"id": "t1", "start": start, "minutes": minutes, "request_key": "forced:4"}
        await write(client, world, model, "plan_work_time", edge, 0)
        assert model.tasks["t1"]["work"] == WORKS[3][1], "the forced edge was not planned"


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
        asyncio.run(forced(built, world, model))
        for step in range(1, steps):
            asyncio.run(batch(built, world, model, rng, step))
            if rng.random() < 0.4:
                owner(model, rng)
            if step % 5 == 4:
                built = module.build_server(config.get_settings())
                world.reached["restart"] += 1
            tasks, keys, changes = world.stored()
            for task_id, want in model.tasks.items():
                assert tasks.get(task_id) == want, (
                    f"step {step} {task_id}: stored {tasks.get(task_id)}, the model holds {want}"
                )
            assert len(tasks) == len(model.tasks), f"step {step}: {len(tasks)} tasks stored"
            assert keys == len(model.keys), (
                f"step {step}: {keys} request keys stored, the model kept {len(model.keys)}"
            )
            assert changes == model.changes, (
                f"step {step}: {changes} agent changes audited, the model made {model.changes}"
            )
    assert MISSING not in model.tasks, f"{MISSING} was created; it must lie beyond every id"
    return world


def scripted(root: Path) -> None:
    reached = walk(root, 6, 40).reached
    for name, least in (
        ("moved", 5),
        ("planned", 5),
        ("replayed", 5),
        ("after-owner", 1),
        ("work_after_deadline", 3),
        ("invalid", 3),
        ("key_reused", 3),
        ("task_ended", 1),
        ("unknown_task", 1),
        ("restart", 3),
    ):
        assert reached[name] >= least, f"{name} reached {reached[name]} < {least}"


def randomized(root: Path) -> None:
    walk(root, 62, 60)


def leaf(error: BaseException) -> BaseException:
    """The first error inside the task groups the MCP client wraps a failure in."""
    while isinstance(error, BaseExceptionGroup):
        error = error.exceptions[0]
    return error


def main() -> None:
    oracle()
    print("edits oracle ok")
    if "--oracle-only" in sys.argv:
        print("FAILURES 0")
        return
    failures = 0
    for name, check in (("scripted walk", scripted), ("random walk", randomized)):
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
