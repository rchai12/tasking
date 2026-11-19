"""Synthetic MCP read properties: listings match the store, pages join, nothing is written."""

import asyncio
import os
import random
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

HOME = "America/New_York"
START = datetime(2026, 10, 31, 12, tzinfo=UTC)
STATUSES = ("open", "in_progress", "due", "overdue", "done", "cancelled")
LIVE = ("open", "in_progress")
JUNK = ("closed", "OPEN", "t0", "t01", "", " open", "due\n", "Synthetic secret", "x" * 300)


def expected(rows: list[tuple], status: str, now: datetime) -> list[str]:
    """The oracle: task ids for a status, from the tasks table alone, in id order."""
    home = ZoneInfo(HOME)
    today = now.astimezone(home).date()
    found = []
    for number, state, deadline_at in rows:
        at = None if deadline_at is None else datetime.fromisoformat(deadline_at)
        if status in LIVE + ("done", "cancelled"):
            keep = state == status
        elif state not in LIVE or at is None:
            keep = False
        elif status == "overdue":
            keep = at <= now
        else:
            keep = at > now and at.astimezone(home).date() == today
        if keep:
            found.append(f"t{number}")
    return found


def oracle() -> None:
    now = datetime(2026, 11, 1, 4, 30, tzinfo=UTC)
    rows = [
        (1, "open", "2026-11-01T04:15:00+00:00"),
        (2, "open", "2026-11-02T04:45:00+00:00"),
        (3, "in_progress", "2026-11-02T05:15:00+00:00"),
        (4, "done", "2026-10-30T00:00:00+00:00"),
        (5, "open", None),
        (6, "in_progress", "2026-11-01T04:30:00+00:00"),
    ]
    assert expected(rows, "due", now) == ["t2"]
    assert expected(rows, "overdue", now) == ["t1", "t6"]
    assert expected(rows, "open", now) == ["t1", "t2", "t5"]
    assert expected(rows, "in_progress", now) == ["t3", "t6"]
    assert expected(rows, "done", now) == ["t4"]
    assert expected(rows, "cancelled", now) == []


class World:
    """One data folder, the clock and the ids, and counts of the cases the walk reached."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.path = root / "data" / "docket.sqlite3"
        self.moment = START
        self.keys = 0
        self.reached = {
            "paged": 0,
            "due": 0,
            "overdue": 0,
            "dst-day": 0,
            "refused": 0,
            "exact-page": 0,
        }

    def now(self) -> datetime:
        return self.moment

    def new_id(self) -> str:
        self.keys += 1
        return f"k{self.keys}"

    def rows(self) -> list[tuple]:
        with sqlite3.connect(self.path) as db:
            return db.execute(
                "SELECT number, state, deadline_at FROM tasks ORDER BY number"
            ).fetchall()

    def dump(self) -> list[str]:
        db = sqlite3.connect(self.path)
        try:
            return list(db.iterdump())
        finally:
            db.close()

    def live_reminders(self, task_id: str) -> list[tuple]:
        with sqlite3.connect(self.path) as db:
            return db.execute(
                "SELECT kind, fire_at, sent_at FROM reminders "
                "WHERE task = ? AND voided_at IS NULL ORDER BY number",
                (int(task_id[1:]),),
            ).fetchall()


async def listing(client, status: str) -> tuple[list[str], int]:
    """Every page of a status joined, and how many pages it took."""
    ids: list[str] = []
    after = None
    pages = 0
    while True:
        arguments = {"status": status} if after is None else {"status": status, "after": after}
        result = await client.call_tool("list_tasks", arguments)
        assert not result.is_error, f"list_tasks {status} after {after} was refused"
        found = result.structured_content
        assert len(found["tasks"]) <= 50, f"a page of {len(found['tasks'])} tasks"
        assert found["tasks"] or after is None, f"{status}: next_after {after} led to an empty page"
        ids.extend(task["id"] for task in found["tasks"])
        pages += 1
        after = found["next_after"]
        if after is None:
            return ids, pages
        assert after == ids[-1], f"next_after {after} is not the page's last id {ids[-1]}"


async def inspect(world: World, built, rng: random.Random) -> None:
    """At one moment: each status matches the oracle, get_task the store; nothing is written."""
    from mcp.client import Client

    before = world.dump()
    rows = world.rows()
    async with Client(built) as client:
        for status in STATUSES:
            ids, pages = await listing(client, status)
            want = expected(rows, status, world.moment)
            extra = sorted(set(ids) ^ set(want), key=lambda task_id: int(task_id[1:]))[:3]
            assert ids == want, (
                f"{world.moment} {status}: listed {len(ids)}, the store has {len(want)}; "
                f"differing ids {extra or 'none (order)'}"
            )
            assert len(ids) == len(set(ids)), f"{world.moment} {status}: an id listed twice"
            world.reached["paged"] += pages > 1
            world.reached["exact-page"] += bool(ids) and len(ids) % 50 == 0
            world.reached["due"] += status == "due" and bool(ids)
            world.reached["overdue"] += status == "overdue" and bool(ids)
        for number, _, _ in rng.sample(rows, min(3, len(rows))):
            task_id = f"t{number}"
            result = await client.call_tool("get_task", {"id": task_id})
            found = [
                (item["kind"], item["fire_at"], item["sent_at"])
                for item in result.structured_content["reminders"]
            ]
            stored = [
                (
                    kind,
                    datetime.fromisoformat(fire).isoformat(),
                    sent and datetime.fromisoformat(sent).isoformat(),
                )
                for kind, fire, sent in world.live_reminders(task_id)
            ]
            assert found == stored, f"{world.moment} {task_id}: reminders differ from the store"
        for junk in JUNK:
            for name, arguments in (
                ("list_tasks", {"status": junk}),
                ("list_tasks", {"status": "open", "after": junk}),
                ("get_task", {"id": junk}),
            ):
                result = await client.call_tool(name, arguments)
                text = " ".join(part.text for part in result.content)
                assert result.is_error, f"{name} accepted {junk[:12]!r}"
                assert text.rsplit(": ", 1)[-1] in (
                    "invalid_status",
                    "invalid_cursor",
                    "unknown_task",
                ), f"{name} refused {junk[:12]!r} with a non-constant answer"
                world.reached["refused"] += 1
        missing = await client.call_tool("get_task", {"id": "t9999"})
        assert missing.is_error, "t9999 was found"
    assert world.dump() == before, f"{world.moment}: a read tool changed the store"
    local = world.moment.astimezone(ZoneInfo(HOME)).date()
    world.reached["dst-day"] += local.isoformat() == "2026-11-01"


def walk(root: Path, seed: int, steps: int) -> World:
    from docket import clock, config, core, ids
    from docket.deadlines import Deadline
    from docket.mcp_server import server as module
    from docket.store import open_store

    world = World(root)
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
        settings = config.get_settings()
        built = module.build_server(settings)
        created = 0
        for step in range(steps):
            with open_store(settings) as store:
                for _ in range(50 if step == 0 else rng.randint(1, 6)):
                    minutes = rng.choice((-3000, -700, -45, -1, 0, 1, 50, 400, 900, 1500, 4000))
                    deadline = None
                    if step > 0 and rng.random() < 0.85:
                        at = world.moment + timedelta(minutes=minutes)
                        deadline = Deadline(at, HOME, rng.random() < 0.7)
                    core.create_task(
                        store, title="Synthetic probe task", source="owner", deadline=deadline
                    )
                    created += 1
                for _ in range(rng.randint(0, 4) if step > 0 else 0):
                    task_id = f"t{rng.randint(1, max(created, 1))}"
                    action = rng.choice(("start", "done", "cancel", "reopen"))
                    if store.task(task_id) is not None:
                        try:
                            core.change_state(store, task_id, action, actor="owner")
                        except core.CoreError:
                            pass
            asyncio.run(inspect(world, built, rng))
            world.moment += timedelta(minutes=rng.choice((7, 45, 180, 400)) if step != 3 else 900)
    assert created > 100, f"created {created} tasks, too few to page"
    return world


def scripted(root: Path) -> None:
    world = walk(root, 6, 18)
    reached = world.reached
    for name, least in (
        ("paged", 4),
        ("due", 4),
        ("overdue", 4),
        ("dst-day", 1),
        ("refused", 27),
        ("exact-page", 1),
    ):
        assert reached[name] >= least, f"{name} reached {reached[name]} < {least}"


def randomized(root: Path) -> None:
    walk(root, 61, 24)


def leaf(error: BaseException) -> BaseException:
    """The first error inside the task groups the MCP client wraps a failure in."""
    while isinstance(error, BaseExceptionGroup):
        error = error.exceptions[0]
    return error


def main() -> None:
    oracle()
    print("reads oracle ok")
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
                    f"FAIL {name}: expected every listing to match the store and nothing to be "
                    f"written; {detail or type(error).__name__}"
                )
                failures += 1
            else:
                print(name + " ok")
    print(f"FAILURES {failures}")


if __name__ == "__main__":
    main()
