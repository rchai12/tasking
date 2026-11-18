"""Synthetic digest properties: one a home day, keyed, claimed, live lines only; a fake only."""

import random
import sqlite3
import sys
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

START = datetime(2026, 10, 30, 4, tzinfo=UTC)
ZONE = "America/New_York"
AT = time(7)
LATE = timedelta(minutes=720)
OPEN = ("open", "in_progress")
TASKS = (
    ("Synthetic overdue", -48),
    ("Synthetic soon late", 12),
    ("Synthetic far", 200),
    ("Synthetic undated", None),
)


def slot_of(now: datetime) -> tuple[date, datetime]:
    zone = ZoneInfo(ZONE)
    day = now.astimezone(zone).date()
    return day, datetime.combine(day, AT, tzinfo=zone).astimezone(UTC)


def heading(count: int) -> str:
    return f"Still open past their deadlines: {count} task{'' if count == 1 else 's'}."


def oracle() -> None:
    from docket import schema

    assert schema.SCHEMA_VERSION == 6
    assert slot_of(START + timedelta(hours=56)) == (
        date(2026, 11, 1),
        datetime(2026, 11, 1, 12, tzinfo=UTC),
    )
    assert slot_of(START + timedelta(hours=31)) == (
        date(2026, 10, 31),
        datetime(2026, 10, 31, 11, tzinfo=UTC),
    )
    assert slot_of(datetime(2026, 11, 3, 4, 30, tzinfo=UTC))[0] == date(2026, 11, 2)
    assert heading(1) == "Still open past their deadlines: 1 task."
    assert heading(3) == "Still open past their deadlines: 3 tasks."


class World:
    """One data folder, a recording fake notifier, and the clock and ids the sender may read."""

    def __init__(self, root: Path) -> None:
        from tests.notifier_cases import FakeNotifier

        world = self

        class Recorder(FakeNotifier):
            def send_digest(self, digest) -> None:
                world.inspect(digest)
                super().send_digest(digest)

        self.path = root / "docket.sqlite3"
        self.notifier = Recorder()
        self.hours = 0.0
        self.reads = 0
        self.keys = 0
        self.dropped = 0
        self.quiet: set[date] = set()

    @property
    def moment(self) -> datetime:
        return START + timedelta(hours=self.hours)

    def now(self) -> datetime:
        self.reads += 1
        return self.moment

    def new_id(self) -> str:
        self.keys += 1
        return f"k{self.keys}"

    def insert(self, opened, title: str, due: float | None) -> None:
        from docket.deadlines import Deadline

        deadline = None if due is None else Deadline(START + timedelta(hours=due), ZONE, True)
        with opened.transaction():
            opened.insert_task(
                title=title,
                state="open",
                deadline=deadline,
                work=None,
                source="owner",
                provider=None,
                message_id=None,
                link=None,
                at=START - timedelta(days=5),
            )

    def inspect(self, digest) -> None:
        """Every attempt: sent on its own home day after the slot, listing live members only."""
        day, slot = slot_of(self.moment)
        assert self.moment >= slot, f"hour {self.hours}: digest sent before the {day} slot"
        with sqlite3.connect(self.path) as db:
            found = db.execute("SELECT number, day FROM digests WHERE key = ?", (digest.key,))
            number, stored = found.fetchone()
            members = db.execute(
                "SELECT t.number, t.title, t.state, t.deadline_at FROM digest_tasks d "
                "JOIN tasks t ON t.number = d.task WHERE d.digest = ?",
                (number,),
            ).fetchall()
        assert stored == day.isoformat(), f"hour {self.hours}: {digest.key} is for {stored}"
        live = sorted(
            (at, n, title)
            for n, title, state, at in members
            if state in OPEN and at and datetime.fromisoformat(at) + LATE <= slot
        )
        expected = [(f"t{n}", title) for _, n, title in live]
        lines = [(line.task_id, line.title) for line in digest.lines]
        assert lines == expected, f"hour {self.hours}: lines {lines}, live members {expected}"
        assert lines, f"hour {self.hours}: {digest.key} sent with no live task"
        assert digest.heading == heading(len(lines)), f"hour {self.hours}: {digest.heading!r}"
        assert all(line.text.startswith("Was due ") for line in digest.lines)
        self.dropped += len(members) - len(lines)

    def run(self, opened, action: str) -> None:
        from docket import reminders
        from tests.notifier_cases import Killed

        if action == "fail":
            self.notifier.fail = 1
        if action in ("crash-before", "crash-after"):
            setattr(self.notifier, action.split("-")[1], Killed())
        reads, keys, made = self.reads, self.keys, count(self.path)
        try:
            reminders.send_digest(opened, self.notifier, zone=ZONE, at=AT)
        except Killed:
            pass
        self.notifier.fail, self.notifier.before, self.notifier.after = 0, None, None
        assert self.reads == reads + 1, f"hour {self.hours}: clock read {self.reads - reads}"
        added = count(self.path) - made
        assert added <= 1, f"hour {self.hours}: {added} digests queued in one pass"
        assert self.keys == keys + added, f"hour {self.hours}: {self.keys - keys} keys, {added}"
        if action == "check":
            self.check_day(opened)

    def check_day(self, opened) -> None:
        """After a healthy pass past the slot: no digest only if nothing was due in one."""
        day, slot = slot_of(self.moment)
        if self.moment < slot:
            return
        row = opened.digest(day)
        overdue = [
            task.id
            for task in opened.tasks(OPEN)
            if task.deadline is not None and task.deadline.at + LATE <= slot
        ]
        if row is None:
            assert not overdue, f"hour {self.hours}: no {day} digest though {overdue} overdue"
            self.quiet.add(day)
            return
        live = [task_id for task_id in row.task_ids if task_id in overdue]
        fresh = row.claimed_at is not None and self.moment - row.claimed_at <= timedelta(minutes=5)
        assert not live or row.sent_at or fresh, f"hour {self.hours}: {day} unsent, {live} live"


def count(path: Path) -> int:
    with sqlite3.connect(path) as db:
        return db.execute("SELECT COUNT(*) FROM digests").fetchone()[0]


def finish(world: World) -> None:
    delivered = [digest.key for digest in world.notifier.delivered]
    assert len(delivered) == len(set(delivered)), "a key was delivered twice"
    with sqlite3.connect(world.path) as db:
        stored = db.execute("SELECT key, day, sent_at FROM digests").fetchall()
    sent = {key for key, _, at in stored if at is not None}
    days = [day for key, day, _ in stored if key in delivered]
    assert sent <= set(delivered), (
        f"marked sent but never delivered: {sorted(sent - set(delivered))}"
    )
    assert len(days) == len(set(days)), "two digests delivered for one home day"


def walk(root: Path, plan: list[tuple[float, str]]) -> World:
    from docket import clock, ids
    from docket.store import Store

    world = World(root)
    with patch.object(clock, "now", world.now), patch.object(ids, "new_id", world.new_id):
        opened = Store(world.path)
        try:
            for title, due in TASKS:
                world.insert(opened, title, due)
            for hours, action in plan:
                world.hours = hours
                if action == "restart":
                    opened.close()
                    opened = Store(world.path)
                elif action.startswith(("done ", "reopen ", "move ")):
                    verb, task_id = action.split()
                    change = {
                        "done": {"state": "done"},
                        "reopen": {"state": "open"},
                        "move": {"deadline": None},
                    }[verb]
                    with opened.transaction():
                        opened.update_task(task_id, at=world.moment, **change)
                elif action == "new":
                    world.insert(opened, "Synthetic arrival", hours - 72)
                else:
                    world.run(opened, action)
            world.hours = plan[-1][0] + 0.1
            world.run(opened, "check")
            finish(world)
        finally:
            opened.close()
    return world


SCRIPT = [
    (6, "pass"),
    (7, "fail"),
    (7.1, "check"),
    (31, "crash-before"),
    (31.02, "restart"),
    (31.05, "pass"),
    (31.2, "check"),
    (50, "done t1"),
    (50, "done t2"),
    (56, "check"),
    (61, "reopen t1"),
    (100, "new"),
    (110, "fail"),
    (110.1, "done t5"),
    (110.2, "check"),
    (128, "crash-after"),
    (128.02, "restart"),
    (128.2, "check"),
    (152, "fail"),
    (152.1, "done t1"),
    (152.2, "check"),
]


def scripted(root: Path) -> None:
    world = walk(root, SCRIPT)
    attempts = [digest.key for digest in world.notifier.attempts]
    repeated = len(attempts) - len(set(attempts))
    assert repeated >= 4, f"retried keys {repeated} < 4 (fail, crash-before, crash-after, fail)"
    assert world.dropped >= 1, f"lines dropped for ended tasks {world.dropped} < 1"
    assert date(2026, 11, 1) in world.quiet, "the empty Nov 1 sent or stored a digest"
    with sqlite3.connect(world.path) as db:
        days = [day for (day,) in db.execute("SELECT day FROM digests ORDER BY number")]
        dead = db.execute("SELECT COUNT(*) FROM digests WHERE sent_at IS NULL").fetchone()[0]
    assert days == ["2026-10-30", "2026-10-31", "2026-11-03", "2026-11-04", "2026-11-05"], days
    assert dead == 1, f"digests left unsent once every task ended {dead} != 1"


def randomized(root: Path) -> None:
    rng = random.Random(4)
    actions = ["pass"] * 5 + ["check"] * 3 + ["fail", "crash-before", "crash-after", "restart"]
    actions += ["done t1", "reopen t1", "done t2", "reopen t2", "move t2", "new"]
    hours, plan = 0.0, []
    for _ in range(90):
        hours += rng.choice((0.05, 0.5, 2, 5, 11, 26))
        plan.append((hours, rng.choice(actions)))
    walk(root, plan)


def main() -> None:
    oracle()
    print("slot and heading oracle ok")
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
                    f"FAIL {name}: expected one live digest a home day, sent once; "
                    f"{detail or type(error).__name__}"
                )
                failures += 1
            else:
                print(name + " ok")
    print(f"FAILURES {failures}")


if __name__ == "__main__":
    main()
