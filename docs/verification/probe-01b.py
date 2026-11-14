"""Phase 1b probe: what the given tests do not reach. Run from the repository root:
.venv/bin/python docs/verification/probe-01b.py

A random walk of writes through two stores on one file, with failures injected inside
transactions and restarts, compared after every step with the probe's own model. It uses a
temporary folder and touches no network, Keychain or real data folder.
"""

import random
import sqlite3
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

FAILURES = 0
ZONES = ["America/New_York", "Europe/London", "Asia/Tokyo", "UTC", "Australia/Lord_Howe"]
TITLES = ["Pay rent", "Book flights", "Café ☕ receipt", "x" * 100, "Review Q4 plan", "t1"]
ACTIONS = ["create", "start", "done", "cancel", "reopen", "retitle", "deadline", "work_time"]
ACTORS = ["owner", "agent", "email"]
STATES = ["open", "in_progress", "done", "cancelled"]


def check(label: str, function) -> None:
    global FAILURES
    try:
        passed = function()
    except Exception as error:  # noqa: BLE001
        passed = False
        label = f"{label} (raised {type(error).__name__})"
    if not passed:
        FAILURES += 1
    print(f"{label}: {'ok' if passed else 'FAIL'}")


class Stop(Exception):
    pass


def instant(rng: random.Random) -> datetime:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return start + timedelta(seconds=rng.randrange(63_000_000), microseconds=rng.randrange(10**6))


# The model: one dict per task, keyed by its expected id, and a list of audit tuples per id.
def expected_id(number: int) -> str:
    return f"t{number}"


assert expected_id(1) == "t1" and expected_id(12) == "t12"
print("oracle: ok")


def walk() -> bool:
    from docket.deadlines import Deadline, WorkTime
    from docket.store import UNCHANGED, Store

    rng = random.Random(7)
    folder = Path(tempfile.mkdtemp())
    path = folder / "docket.sqlite3"
    stores = [Store(path), Store(path)]
    tasks: dict[str, dict[str, object]] = {}
    audit: dict[str, list[tuple[object, ...]]] = {}
    reached = {"insert": 0, "update": 0, "audit": 0, "rolled-back": 0, "restart": 0}

    def fields(rng: random.Random) -> dict[str, object]:
        zone = rng.choice(ZONES)
        deadline = None
        if rng.random() < 0.6:
            deadline = Deadline(instant(rng), zone, rng.random() < 0.5)
        work = None
        if rng.random() < 0.4:
            work = WorkTime(instant(rng), rng.randrange(5, 721), zone)
        return {"deadline": deadline, "work": work}

    def compare(store) -> bool:
        listed = store.tasks()
        if [task.id for task in listed] != sorted(tasks, key=lambda key: int(key[1:])):
            print(f"  ids {[task.id for task in listed]} != {sorted(tasks)}")
            return False
        for task in listed:
            model = tasks[task.id]
            seen = {name: getattr(task, name) for name in model}
            if seen != model or store.task(task.id) != task:
                print(f"  {task.id}: {seen} != {model}")
                return False
            entries = [
                (e.task_id, e.at, e.action, e.actor, e.before, e.after)
                for e in store.audit(task.id)
            ]
            if entries != audit[task.id]:
                print(f"  audit {task.id}: {entries} != {audit[task.id]}")
                return False
        return True

    for step in range(600):
        writer = stores[rng.randrange(2)]
        roll = rng.random()
        fail = rng.random() < 0.25 or step % 50 == 7
        at = instant(rng)
        try:
            if roll < 0.06:
                index = rng.randrange(2)
                stores[index].close()
                stores[index] = Store(path)
                reached["restart"] += 1
            elif roll < 0.4 or not tasks:
                source = rng.choice(["owner", "agent", "email"])
                ref = (None, None, None)
                if source == "email":
                    ref = ("gmail", f"personal/{step}", f"https://mail.example/{step}")
                extra = fields(rng)
                title = rng.choice(TITLES)
                state = rng.choice(STATES)
                with writer.transaction():
                    made = writer.insert_task(
                        title=title,
                        state=state,
                        deadline=extra["deadline"],
                        work=extra["work"],
                        source=source,
                        provider=ref[0],
                        message_id=ref[1],
                        link=ref[2],
                        at=at,
                    )
                    entry = (made.id, at, "create", "owner", {}, {"title": title})
                    writer.append_audit(
                        made.id, at=at, action="create", actor="owner", before={}, after=entry[5]
                    )
                    if fail:
                        raise Stop
                number = len(tasks) + 1
                if made.id != expected_id(number):
                    print(f"  new id {made.id} != {expected_id(number)}")
                    return False
                tasks[made.id] = {
                    "title": title,
                    "state": state,
                    "deadline": extra["deadline"],
                    "work": extra["work"],
                    "source": source,
                    "provider": ref[0],
                    "message_id": ref[1],
                    "link": ref[2],
                    "created_at": at,
                    "updated_at": at,
                }
                audit[made.id] = [entry]
                reached["insert"] += 1
            elif roll < 0.8:
                task_id = rng.choice(list(tasks))
                change: dict[str, object] = {}
                if rng.random() < 0.5:
                    change["state"] = rng.choice(STATES)
                if rng.random() < 0.3:
                    change["title"] = rng.choice(TITLES)
                extra = fields(rng)
                for name in ("deadline", "work"):
                    if rng.random() < 0.4:
                        change[name] = extra[name]
                given = {
                    name: change.get(name, UNCHANGED)
                    for name in ("title", "state", "deadline", "work")
                }
                with writer.transaction():
                    writer.update_task(task_id, at=at, **given)
                    if fail:
                        raise Stop
                tasks[task_id].update(change)
                tasks[task_id]["updated_at"] = at
                reached["update"] += 1
            else:
                task_id = rng.choice(list(tasks))
                entry = (
                    task_id,
                    at,
                    rng.choice(ACTIONS),
                    rng.choice(ACTORS),
                    {"step": step, "note": "before ☕"},
                    {"step": step, "list": [1, None, "x"]},
                )
                with writer.transaction():
                    writer.append_audit(
                        task_id,
                        at=at,
                        action=entry[2],
                        actor=entry[3],
                        before=entry[4],
                        after=entry[5],
                    )
                    if fail:
                        raise Stop
                audit[task_id].append(entry)
                reached["audit"] += 1
        except Stop:
            reached["rolled-back"] += 1
        lock = sqlite3.connect(path, timeout=0, isolation_level=None)
        lock.execute("BEGIN IMMEDIATE")
        lock.execute("ROLLBACK")
        lock.close()
        if not all(compare(store) for store in stores):
            print(f"  at step {step}")
            return False
    for store in stores:
        store.close()
    with Store(path) as fresh:
        if not compare(fresh):
            return False
    print(f"  reached {reached}")
    return all(count >= 20 for count in reached.values())


def a_task_reads_back() -> bool:
    from docket.store import Store

    folder = Path(tempfile.mkdtemp())
    with Store(folder / "docket.sqlite3") as store:
        with store.transaction():
            made = store.insert_task(
                title="Pay rent",
                state="open",
                deadline=None,
                work=None,
                source="owner",
                provider=None,
                message_id=None,
                link=None,
                at=datetime(2026, 11, 14, 9, 0, tzinfo=UTC),
            )
        return store.task(made.id) == made and store.task(made.id).title == "Pay rent"


check("600 steps through two stores match the model after every step", walk)
check("a task reads back exactly as written", a_task_reads_back)

print(f"FAILURES {FAILURES}")
