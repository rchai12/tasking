"""Synthetic sending properties: claimed, keyed, coalesced and never twice; a fake notifier only."""

import random
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

START = datetime(2026, 11, 20, 16, tzinfo=UTC)
LINES = {
    "start": "Time to start.",
    "before": "Are you working on this?",
    "due_soon": "This is due soon.",
    "due": "This is now due.",
    "late": "This is late.",
}
TASKS = (("Synthetic one", 1, None), ("Synthetic two", 120, None), ("Synthetic three", -180, None))
WORK = ("Synthetic four", 24 * 60, 10)


def text(kind: str, missed: int) -> str:
    line = LINES[kind]
    return f"Missed while docket was offline: {missed} reminders.\n{line}" if missed >= 2 else line


def oracle() -> None:
    from docket import schema

    assert schema.SCHEMA_VERSION == 6
    assert text("late", 0) == text("late", 1) == "This is late."
    assert text("due", 3) == "Missed while docket was offline: 3 reminders.\nThis is now due."
    with sqlite3.connect(":memory:") as db:
        db.executescript("".join(schema.MIGRATIONS))
        assert [row[1] for row in db.execute("PRAGMA table_info(post_reminders)")] == [
            "post",
            "reminder",
        ]


class World:
    """One data folder, a fake notifier, and the clock and ids the sender may read."""

    def __init__(self, root: Path) -> None:
        from tests.notifier_cases import FakeNotifier

        self.path = root / "docket.sqlite3"
        self.notifier = FakeNotifier()
        self.minute = 0.0
        self.reads = 0
        self.keys = 0
        self.reach: dict[str, int] = {}

    def now(self) -> datetime:
        self.reads += 1
        return START + timedelta(minutes=self.minute)

    def new_id(self) -> str:
        self.keys += 1
        return f"k{self.keys}"

    def seed(self, opened) -> None:
        from docket import core
        from docket.deadlines import Deadline, WorkTime

        for title, due, _ in TASKS:
            deadline = Deadline(START + timedelta(minutes=due), "UTC", True)
            core.create_task(opened, title=title, source="owner", deadline=deadline)
        title, due, work = WORK
        core.create_task(
            opened,
            title=title,
            source="owner",
            deadline=Deadline(START + timedelta(minutes=due), "UTC", True),
            work=WorkTime(START + timedelta(minutes=work), 30, "UTC"),
        )

    def run(self, opened, action: str) -> None:
        from docket import core, reminders
        from tests.notifier_cases import Killed

        self.reach[action] = self.reach.get(action, 0) + 1
        if action in ("done", "reopen"):
            core.change_state(opened, "t2", action, actor="owner")
            return
        if action == "fail":
            self.notifier.fail = 1
        if action in ("crash-before", "crash-after"):
            setattr(self.notifier, action.split("-")[1], Killed())
        reads, keys, posts = self.reads, self.keys, count(self.path, "posts")
        try:
            reminders.send_due(opened, self.notifier)
        except Killed:
            pass
        assert self.reads == reads + 1, f"minute {self.minute}: clock read {self.reads - reads}"
        made = count(self.path, "posts") - posts
        assert self.keys == keys + made, f"minute {self.minute}: {self.keys - keys} keys, {made}"


def count(path: Path, table: str) -> int:
    with sqlite3.connect(path) as db:
        return db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def check_store(world: World, final: datetime) -> None:
    with sqlite3.connect(world.path) as db:
        posts = db.execute("SELECT number, key, kind, missed, sent_at FROM posts").fetchall()
        for number, _key, kind, missed, sent_at in posts:
            items = db.execute(
                "SELECT r.kind, r.fire_at, r.planned_at, r.sent_at, r.voided_at FROM reminders r "
                "JOIN post_reminders p ON p.reminder = r.number WHERE p.post = ? "
                "ORDER BY r.fire_at, r.number",
                (number,),
            ).fetchall()
            assert items, f"p{number} has no reminder"
            assert kind == items[-1][0], f"p{number} kind {kind} is not its newest"
            late = sum(fire > planned for _, fire, planned, _, _ in items)
            assert missed == late, f"p{number} missed {missed}, {late} came due after planning"
            for _, fire, _, sent, voided in items:
                assert sent is None or voided is None, f"p{number} reminder sent and voided"
                assert sent in (None, sent_at), f"p{number} reminder sent {sent}, post {sent_at}"
                assert sent is None or fire <= sent, f"p{number} sent before {fire}"
        unsent = db.execute(
            "SELECT COUNT(*) FROM reminders WHERE fire_at <= ? AND sent_at IS NULL "
            "AND voided_at IS NULL",
            (final.isoformat(timespec="microseconds"),),
        ).fetchone()[0]
        assert unsent == 0, f"{unsent} due live reminders unsent after the final pass"
        texts = {key: text(kind, missed) for _, key, kind, missed, _ in posts}
    delivered = [notice.key for notice in world.notifier.delivered]
    assert len(delivered) == len(set(delivered)), "a key was delivered twice"
    for notice in world.notifier.delivered:
        assert notice.text == texts[notice.key], f"{notice.key} text {notice.text!r}"


def walk(root: Path, plan: list[tuple[float, str]]) -> World:
    from docket import clock, ids
    from docket.store import Store

    world = World(root)
    with patch.object(clock, "now", world.now), patch.object(ids, "new_id", world.new_id):
        opened = Store(world.path)
        try:
            world.seed(opened)
            for minute, action in plan:
                world.minute = minute
                if action == "restart":
                    opened.close()
                    opened = Store(world.path)
                    continue
                world.run(opened, action)
            world.minute = plan[-1][0] + 6
            world.run(opened, "pass")
            check_store(world, START + timedelta(minutes=world.minute))
        finally:
            opened.close()
    return world


SCRIPT = [
    (0, "pass"),
    (1.2, "fail"),
    (1.5, "pass"),
    (10.5, "crash-before"),
    (11, "restart"),
    (12, "pass"),
    (16, "pass"),
    (31.5, "crash-after"),
    (32, "restart"),
    (37, "pass"),
    (60.5, "crash-before"),
    (61, "done"),
    (62, "restart"),
    (70, "pass"),
    (71, "reopen"),
    (300, "pass"),
]


def scripted(root: Path) -> None:
    world = walk(root, SCRIPT)
    attempts = [notice.key for notice in world.notifier.attempts]
    repeated = len(attempts) - len(set(attempts))
    assert repeated >= 3, f"retried keys {repeated} < 3 (fail, crash-before, crash-after)"
    offline = [notice for notice in world.notifier.delivered if notice.text.startswith("Missed")]
    assert len(offline) >= 2, f"offline messages {len(offline)} < 2"
    with sqlite3.connect(world.path) as db:
        dropped = db.execute(
            "SELECT COUNT(*) FROM posts WHERE sent_at IS NULL AND task = 2"
        ).fetchone()[0]
    assert dropped == 1, f"posts left unsent for the ended task {dropped} != 1"


def randomized(root: Path) -> None:
    rng = random.Random(3)
    actions = ["pass"] * 6 + ["fail", "crash-before", "crash-after", "restart"]
    minute, plan = 0.0, []
    for _ in range(60):
        minute += rng.choice((0.5, 1, 3, 7, 30, 95))
        plan.append((minute, rng.choice(actions)))
    walk(root, plan)


def main() -> None:
    oracle()
    print("schema and literal oracle ok")
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
                    f"FAIL {name}: expected each due reminder sent once; "
                    f"{detail or type(error).__name__}"
                )
                failures += 1
            else:
                print(name + " ok")
    print(f"FAILURES {failures}")


if __name__ == "__main__":
    main()
