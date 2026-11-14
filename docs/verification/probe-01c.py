"""Phase 1c probe: what the given tests do not reach. Run from the repository root:
.venv/bin/python docs/verification/probe-01c.py

A random walk through create_task, change_state and edit_task checked against the probe's own
transition table; a replay of every task's audit rows; two threads pressing Done at once; and
fuzzed titles. It uses temporary folders and touches no network, Keychain or real data folder.
"""

import random
import tempfile
import threading
import unicodedata
from datetime import UTC, datetime, timedelta
from pathlib import Path

FAILURES = 0
NY = "America/New_York"

# Oracle: (state, action) -> new state, "same" for no change, or "ended" for a refusal.
TABLE = {
    ("open", "start"): "in_progress",
    ("open", "done"): "done",
    ("open", "cancel"): "cancelled",
    ("open", "reopen"): "same",
    ("in_progress", "start"): "same",
    ("in_progress", "done"): "done",
    ("in_progress", "cancel"): "cancelled",
    ("in_progress", "reopen"): "same",
    ("done", "start"): "ended",
    ("done", "done"): "same",
    ("done", "cancel"): "ended",
    ("done", "reopen"): "open",
    ("cancelled", "start"): "ended",
    ("cancelled", "done"): "ended",
    ("cancelled", "cancel"): "same",
    ("cancelled", "reopen"): "open",
}
BAD = {"Cc", "Cf", "Zl", "Zp"}


def oracle_title(title: object) -> bool:
    if not isinstance(title, str) or not 1 <= len(title) <= 100 or title != title.strip():
        return False
    return all(unicodedata.category(char) not in BAD for char in title)


assert len(TABLE) == 16
assert oracle_title("Pay rent") and oracle_title("a b") and oracle_title("x" * 100)
assert not oracle_title(" a") and not oracle_title("a​b") and not oracle_title("x" * 101)
assert not oracle_title("") and not oracle_title(None)
print("oracle: ok")


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


def clock_from(start: datetime):
    lock = threading.Lock()
    count = [0]

    def now() -> datetime:
        with lock:
            count[0] += 1
            return start + timedelta(seconds=count[0])

    return now


def snapshot(value):
    if value is None:
        return None
    if hasattr(value, "time_given"):
        return {
            "at": value.at.isoformat(timespec="microseconds"),
            "zone": value.zone,
            "time_given": value.time_given,
        }
    return {
        "start": value.start.isoformat(timespec="microseconds"),
        "minutes": value.minutes,
        "zone": value.zone,
    }


def replay(entries) -> dict[str, object]:
    folded: dict[str, object] = {}
    for entry in entries:
        folded.update(entry.after)
    return folded


def walk() -> bool:
    from docket import clock, core
    from docket.deadlines import Deadline, WorkTime
    from docket.store import Store

    clock.now = clock_from(datetime(2026, 11, 14, 9, 0, tzinfo=UTC))
    rng = random.Random(11)
    store = Store(Path(tempfile.mkdtemp()) / "docket.sqlite3")
    reached = {"changed": 0, "same": 0, "ended": 0, "conflict": 0, "edit": 0}
    base = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)

    def deadline():
        return Deadline(base + timedelta(hours=rng.randrange(0, 12)), NY, rng.random() < 0.5)

    def work():
        return WorkTime(
            base + timedelta(hours=rng.randrange(-2, 10)), rng.choice((30, 60, 120)), NY
        )

    for step in range(800):
        tasks = store.tasks()
        roll = rng.random()
        if roll < 0.15 or not tasks:
            d = deadline() if rng.random() < 0.5 else None
            w = work() if rng.random() < 0.4 else None
            try:
                core.create_task(store, title="Pay rent", source="owner", deadline=d, work=w)
                if d is not None and w is not None and w.end > d.at:
                    return False
            except core.CoreError as error:
                if error.code != "work_after_deadline" or d is None or w is None or w.end <= d.at:
                    return False
                reached["conflict"] += 1
            continue
        task = rng.choice(tasks)
        if roll < 0.6:
            action = rng.choice(["start", "done", "cancel", "reopen"])
            expected = TABLE[(task.state, action)]
            try:
                outcome = core.change_state(
                    store, task.id, action, actor=rng.choice(["owner", "agent"])
                )
            except core.CoreError as error:
                if (expected, error.code) != ("ended", "task_ended"):
                    return False
                reached["ended"] += 1
                continue
            if expected == "ended":
                return False
            if expected == "same":
                if outcome.changed or outcome.task != task:
                    return False
                reached["same"] += 1
            else:
                if not outcome.changed or outcome.task.state != expected:
                    return False
                reached["changed"] += 1
        else:
            change = {}
            if rng.random() < 0.4:
                change["title"] = rng.choice(["Pay rent", "Pay rent today", "Book flights"])
            if rng.random() < 0.5:
                change["deadline"] = rng.choice([None, deadline()])
            if rng.random() < 0.5:
                change["work"] = rng.choice([None, work()])
            new_deadline = change.get("deadline", task.deadline)
            new_work = change.get("work", task.work)
            try:
                outcome = core.edit_task(store, task.id, actor="owner", **change)
            except core.CoreError as error:
                if error.code == "task_ended" and task.state in ("done", "cancelled"):
                    reached["ended"] += 1
                    continue
                conflict = new_deadline is not None and new_work is not None
                if (
                    error.code == "work_after_deadline"
                    and conflict
                    and new_work.end > new_deadline.at
                ):
                    reached["conflict"] += 1
                    continue
                return False
            if task.state in ("done", "cancelled"):
                return False
            moved = {name for name, value in change.items() if getattr(task, name) != value}
            if outcome.changed != bool(moved):
                return False
            reached["edit"] += 1
        for each in store.tasks():
            if each.deadline and each.work and each.work.end > each.deadline.at:
                print(f"  {each.id}: work past its deadline")
                return False
            folded = replay(store.audit(each.id))
            seen = {
                "title": each.title,
                "state": each.state,
                "deadline": snapshot(each.deadline),
                "work": snapshot(each.work),
            }
            if any(folded[name] != value for name, value in seen.items()):
                print(f"  {each.id} at step {step}: audit replays to {folded}, task is {seen}")
                return False
    store.close()
    if not all(count >= 10 for count in reached.values()):
        print(f"  reached {reached}")
        return False
    return True


def two_presses_change_once() -> bool:
    from docket import clock, core
    from docket.store import Store

    clock.now = clock_from(datetime(2026, 11, 14, 9, 0, tzinfo=UTC))
    for trial in range(50):
        path = Path(tempfile.mkdtemp()) / "docket.sqlite3"
        with Store(path) as store:
            made = core.create_task(store, title="Pay rent", source="owner")
        results: list[bool] = []
        gate = threading.Barrier(2)

        def press(path=path, gate=gate, results=results, task_id=made.id) -> None:
            with Store(path) as mine:
                gate.wait()
                results.append(core.change_state(mine, task_id, "done", actor="owner").changed)

        threads = [threading.Thread(target=press) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)
        with Store(path) as store:
            rows = [entry.action for entry in store.audit(made.id)]
        if sorted(results) != [False, True] or rows != ["create", "done"]:
            print(f"  trial {trial}: changed {results}, audit {rows}")
            return False
    return True


def titles_follow_the_rule() -> bool:
    from docket import core

    rng = random.Random(12)
    alphabet = "aZ9 .-☕é  \t\n\r\x00\x1f​‍﻿  ́"
    for _ in range(5000):
        title = "".join(rng.choice(alphabet) for _ in range(rng.choice((0, 1, 2, 5, 99, 100, 101))))
        try:
            core.check_title(title)
            accepted = True
        except core.CoreError as error:
            if error.code != "invalid_title":
                return False
            accepted = False
        if accepted != oracle_title(title):
            print(f"  {title!r}: accepted {accepted}")
            return False
    return True


check("800 random steps follow the transition table and the audit replays", walk)
check("two Done presses at once change the task once", two_presses_change_once)
check("5000 fuzzed titles follow the rule", titles_follow_the_rule)

print(f"FAILURES {FAILURES}")
