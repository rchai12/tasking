"""Synthetic loop properties: both halves run every pass; only a crash stops it. A fake only."""

import random
import sqlite3
import sys
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

START = datetime(2026, 11, 20, 16, tzinfo=UTC)
ZONE = "UTC"
AT = time(7)
STEP = timedelta(seconds=30)
OPEN = ("open", "in_progress")


def oracle() -> None:
    from docket import schema

    assert schema.SCHEMA_VERSION == 6
    assert STEP.total_seconds() == 30
    assert START + 10 * STEP == datetime(2026, 11, 20, 16, 5, tzinfo=UTC)


class World:
    """One data folder, a recording fake notifier, the clock, the ids and the loop's stop."""

    def __init__(self, root: Path) -> None:
        from tests.notifier_cases import FakeNotifier

        world = self

        class Recorder(FakeNotifier):
            def send(self, notice) -> None:
                world.inspect(notice.task_id)
                super().send(notice)

        self.path = root / "docket.sqlite3"
        self.notifier = Recorder()
        self.moment = START
        self.reads = 0
        self.keys = 0
        self.left = 0
        self.waits: list[float] = []
        self.reached = {"bug": 0, "kill": 0, "restart": 0, "done": 0, "digest": 0}

    def now(self) -> datetime:
        self.reads += 1
        return self.moment

    def new_id(self) -> str:
        self.keys += 1
        return f"k{self.keys}"

    def is_set(self) -> bool:
        return self.left <= 0

    def wait(self, timeout: float) -> bool:
        self.waits.append(timeout)
        self.moment += timedelta(seconds=timeout)
        self.left -= 1
        return self.is_set()

    def inspect(self, task_id: str) -> None:
        """Every notice attempt is for a task still open when it is sent."""
        with sqlite3.connect(self.path) as db:
            (state,) = db.execute(
                "SELECT state FROM tasks WHERE number = ?", (int(task_id[1:]),)
            ).fetchone()
        assert state in OPEN, f"{self.moment}: a notice for {task_id}, which is {state}"

    def run(self, opened, passes: int, hook: str) -> None:
        """Run the loop for `passes` passes with one injected failure, and check the pass shape."""
        from docket import reminders
        from tests.notifier_cases import Killed, SyntheticBug

        if hook in ("bug-before", "bug-after"):
            setattr(self.notifier, hook.split("-")[1], SyntheticBug())
            self.reached["bug"] += 1
        if hook == "refuse":
            self.notifier.fail = 2
        if hook == "kill":
            self.notifier.before = Killed()
        self.left = passes
        reads, waits, digests = self.reads, len(self.waits), count(self.path, "digests")
        try:
            done = reminders.run_loop(opened, self.notifier, zone=ZONE, at=AT, stop=self)
        except Killed:
            done = len(self.waits) - waits
            crashed = True
        else:
            crashed = False
            assert done == passes, f"{self.moment}: run_loop ran {done} of {passes} passes"
        if crashed:
            self.reached["kill"] += 1
        self.notifier.fail, self.notifier.before, self.notifier.after = 0, None, None
        extra = self.reads - reads - 2 * done
        if crashed:
            assert extra in (1, 2), f"{self.moment}: {extra} clock reads in the crashed pass"
        else:
            assert extra == 0, f"{self.moment}: {extra} clock reads beyond 2 a pass"
        assert all(seconds == 30 for seconds in self.waits[waits:]), (
            f"{self.moment}: waited {sorted(set(self.waits[waits:]))}, not 30"
        )
        self.reached["digest"] += count(self.path, "digests") - digests


def count(path: Path, table: str) -> int:
    with sqlite3.connect(path) as db:
        return db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def finish(world: World) -> None:
    """After a healthy stretch past every claim's expiry: every due live reminder was sent."""
    delivered = [sent.key for sent in world.notifier.delivered]
    assert len(delivered) == len(set(delivered)), "a key was delivered twice"
    now = world.moment.isoformat()
    with sqlite3.connect(world.path) as db:
        lost = db.execute(
            "SELECT r.number, t.number FROM reminders r JOIN tasks t ON t.number = r.task "
            "WHERE r.sent_at IS NULL AND r.voided_at IS NULL AND r.fire_at <= ? "
            "AND t.state IN ('open', 'in_progress')",
            (now,),
        ).fetchall()
        unsent = db.execute("SELECT key FROM posts WHERE sent_at IS NOT NULL").fetchall()
    assert not lost, f"{now}: due reminders never sent {lost[:3]}"
    assert {key for (key,) in unsent} <= set(delivered), "a post marked sent was never delivered"


def walk(root: Path, plan: list[tuple[str, float]]) -> World:
    from docket import clock, core, ids
    from docket.deadlines import Deadline
    from docket.store import Store

    world = World(root)
    with patch.object(clock, "now", world.now), patch.object(ids, "new_id", world.new_id):
        opened = Store(world.path)
        try:
            for action, value in plan:
                if action == "add":
                    deadline = Deadline(world.moment + timedelta(minutes=value), "UTC", True)
                    core.create_task(
                        opened, title="Synthetic task", source="owner", deadline=deadline
                    )
                elif action in ("done", "reopen"):
                    task = f"t{int(value)}"
                    if opened.task(task) is not None:
                        outcome = core.change_state(opened, task, action, actor="owner")
                        world.reached["done"] += outcome.changed and action == "done"
                elif action == "jump":
                    world.moment += timedelta(minutes=value)
                elif action == "restart":
                    opened.close()
                    opened = Store(world.path)
                    world.reached["restart"] += 1
                else:
                    world.run(opened, int(value), action)
            world.moment += timedelta(minutes=1)
            world.run(opened, 14, "pass")
            finish(world)
        finally:
            opened.close()
    return world


SCRIPT = [
    ("add", 1),
    ("add", 2),
    ("add", -1500),
    ("bug-before", 2),
    ("bug-after", 2),
    ("refuse", 3),
    ("kill", 12),
    ("restart", 0),
    ("jump", 90),
    ("pass", 2),
    ("done", 1),
    ("add", 3),
    ("kill", 3),
    ("jump", 600),
    ("restart", 0),
    ("bug-before", 3),
    ("reopen", 1),
    ("jump", 900),
    ("pass", 3),
]


def scripted(root: Path) -> None:
    world = walk(root, SCRIPT)
    reached = world.reached
    assert reached["bug"] >= 3, f"injected pass failures {reached['bug']} < 3"
    assert reached["kill"] >= 2, f"crashes {reached['kill']} < 2"
    assert reached["restart"] >= 2, f"restarts {reached['restart']} < 2"
    assert reached["done"] >= 1, f"tasks done mid-run {reached['done']} < 1"
    assert reached["digest"] >= 2, f"digests queued by the loop {reached['digest']} < 2"


def randomized(root: Path) -> None:
    rng = random.Random(5)
    actions = ["pass"] * 6 + ["bug-before", "bug-after", "refuse", "kill", "restart"]
    actions += ["add", "add", "done", "reopen", "jump"]
    plan = [("add", 1), ("add", -1500)]
    for _ in range(80):
        action = rng.choice(actions)
        value = {
            "add": rng.choice((-1500, -30, 1, 3, 70)),
            "done": rng.randint(1, 6),
            "reopen": rng.randint(1, 6),
            "jump": rng.choice((1, 7, 45, 400)),
        }.get(action, rng.randint(1, 4))
        plan.append((action, value))
    walk(root, plan)


def main() -> None:
    oracle()
    print("loop oracle ok")
    if "--oracle-only" in sys.argv:
        print("FAILURES 0")
        return
    failures = 0
    for name, check in (("scripted walk", scripted), ("random walk", randomized)):
        with TemporaryDirectory() as directory:
            try:
                check(Path(directory))
            except Exception as error:
                detail = str(error) if isinstance(error, AssertionError) else ""
                print(
                    f"FAIL {name}: expected every pass to run both halves and the loop "
                    f"to stop only on a crash; {detail or type(error).__name__}"
                )
                failures += 1
            else:
                print(name + " ok")
    print(f"FAILURES {failures}")


if __name__ == "__main__":
    main()
