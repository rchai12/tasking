"""Synthetic reminder-pass properties: with every row sound, a walk of passes sends exactly
what the spec commit's code sends and leaves the same rows; with one task's reminder row
undecodable, every other task's notices and every digest still go out, and only that task is
skipped, on every pass."""

import json
import random
import subprocess
import sys
import tarfile
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
PROBE = "docs/verification/probe-05e.py"
# Two hours before the 07:00 digest slot, so every walk crosses one.
T0 = "2026-11-20T05:00:00+00:00"
NAIVE = "2026-11-20T05:00:00"
WALKS = (7, 19, 43)
TASKS = 6
PASSES = 25
# Run under one source tree: create the tasks, plant the bad row if asked, run the passes, and
# print every pass result, every delivered notice and digest, and the reminder tables.
CHILD = r"""
import json, sqlite3, sys
from datetime import datetime, time, timedelta
from pathlib import Path
sys.path[:0] = [sys.argv[1]]
from docket import clock, core, ids, reminders
from docket.deadlines import Deadline, WorkTime
from docket.notifier import NotifierError
from docket.store import Store

case, path = json.loads(sys.argv[2]), Path(sys.argv[3])
moment = [datetime.fromisoformat(case["start"])]
clock.now = lambda: moment[0]
keys = iter(f"probe-key-{n}" for n in range(1, 10000))
ids.new_id = lambda: next(keys)
step = [0]

class Notifier:
    def __init__(self):
        self.notices, self.digests = [], []

    def send(self, notice):
        if (int(notice.task_id[1:]) * 7 + step[0]) % 5 == 0:
            raise NotifierError("synthetic delivery failure")
        self.notices.append([notice.key, notice.task_id, notice.text])

    def send_digest(self, digest):
        if step[0] % 4 == 1:
            raise NotifierError("synthetic delivery failure")
        lines = [[line.task_id, line.text] for line in digest.lines]
        self.digests.append([digest.key, digest.heading, lines])

notifier, passes = Notifier(), []
with Store(path) as store:
    for task in case["tasks"]:
        due = task["deadline"]
        work = task["work"]
        core.create_task(
            store, title="Synthetic probe task", source="owner",
            deadline=due and Deadline(datetime.fromisoformat(due), "UTC", True),
            work=work and WorkTime(datetime.fromisoformat(work[0]), work[1], "UTC"),
        )
    if case["bad"] is not None:
        store._connection.execute(
            "INSERT INTO reminders (task, kind, fire_at, planned_at) VALUES (?, 'before', ?, ?)",
            (case["bad"], case["start"].replace("+00:00", ".000000+00:00"), case["naive"]),
        )
    for minutes in case["steps"]:
        moment[0] += timedelta(minutes=minutes)
        result = reminders.run_pass(store, notifier, zone="UTC", at=time(7))
        passes.append([result.sent, result.digest, list(result.failed),
                       list(getattr(result, "skipped", ()))])
        step[0] += 1
with sqlite3.connect(path) as db:
    tables = {
        name: [list(row) for row in db.execute(f"SELECT * FROM {name} ORDER BY rowid")]
        for name in ("reminders", "posts", "post_reminders", "digests", "digest_tasks")
    }
print(json.dumps({"passes": passes, "notices": notifier.notices,
                  "digests": notifier.digests, "tables": tables}))
"""


def walk(seed: int) -> dict:
    chance = random.Random(seed)
    start = datetime.fromisoformat(T0)
    tasks = []
    for index in range(TASKS):
        # The first task is always overdue, so each digest has a line to send.
        hours = -20 if index == 0 else chance.choice((-30, -20, 1, 2, 3, 5, 8))
        deadline = (start + timedelta(hours=hours)).isoformat()
        work = None
        if hours > 2 and chance.random() < 0.5:
            work = [(start + timedelta(hours=1)).isoformat(), chance.choice((30, 60))]
        tasks.append({"deadline": deadline, "work": work})
    steps = [chance.choice((1, 20, 45, 90)) for _ in range(PASSES)]
    return {"start": T0, "naive": NAIVE, "tasks": tasks, "steps": steps, "bad": None}


def oracle() -> None:
    assert walk(WALKS[0]) == walk(WALKS[0]), "a walk is not repeatable"
    for seed in WALKS:
        case = walk(seed)
        assert len(case["tasks"]) == TASKS and len(case["steps"]) == PASSES
        assert any(task["deadline"] < T0 for task in case["tasks"]), "no overdue task"
        assert sum(case["steps"]) > 2 * 60, "the walk never reaches the digest slot"


def spec_source(root: Path) -> Path:
    found = subprocess.run(
        ["git", "log", "-1", "--format=%H", "--", PROBE],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if not found:
        raise AssertionError("the probe is not committed, so there is no spec commit to compare")
    archive = subprocess.run(
        ["git", "archive", found, "src"], cwd=ROOT, capture_output=True, check=True
    ).stdout
    with tarfile.open(fileobj=BytesIO(archive)) as tar:
        tar.extractall(root / "spec", filter="data")
    return root / "spec" / "src"


def answers(source: Path, case: dict, path: Path) -> dict:
    finished = subprocess.run(
        [sys.executable, "-I", "-c", CHILD, str(source), json.dumps(case), str(path)],
        capture_output=True,
        text=True,
    )
    if finished.returncode:
        last = (finished.stderr.strip().splitlines() or ["no output"])[-1]
        raise AssertionError(f"the child under {source.parent.name} stopped: {last}")
    return json.loads(finished.stdout)


def first_difference(left: object, right: object, where: str, names=("spec", "now")) -> str:
    """Name the innermost differing item, so a long list prints one entry."""
    if isinstance(left, dict) and isinstance(right, dict):
        for key in left:
            if left[key] != right.get(key):
                return first_difference(left[key], right.get(key), f"{where} {key}", names)
    if isinstance(left, list) and isinstance(right, list):
        for index, (inner_left, inner_right) in enumerate(zip(left, right, strict=False)):
            if inner_left != inner_right:
                return first_difference(inner_left, inner_right, f"{where} item {index}", names)
        return f"{where}: {names[0]} has {len(left)} items, {names[1]} {len(right)}"
    return f"{where}: {names[0]} {left!r}, {names[1]} {right!r}"


def same_answers(root: Path) -> None:
    spec = spec_source(root)
    for seed in WALKS:
        case = walk(seed)
        old = answers(spec, case, root / f"old-{seed}.sqlite3")
        new = answers(ROOT / "src", case, root / f"new-{seed}.sqlite3")
        old["passes"] = [one[:3] for one in old["passes"]]
        new["passes"] = [one[:3] for one in new["passes"]]
        if not any(new["digests"]):
            raise AssertionError(f"walk {seed} sent no digest, so it proves nothing about one")
        if old != new:
            raise AssertionError(first_difference(old, new, f"walk {seed}"))


def isolated(root: Path) -> None:
    for seed in WALKS:
        case = walk(seed)
        bad = random.Random(seed).randrange(1, TASKS + 1)
        task = f"t{bad}"
        clean = answers(ROOT / "src", case, root / f"clean-{seed}.sqlite3")
        broken = answers(ROOT / "src", {**case, "bad": bad}, root / f"bad-{seed}.sqlite3")
        others = [entry[1:] for entry in clean["notices"] if entry[1] != task]
        if [entry[1:] for entry in broken["notices"]] != others:
            raise AssertionError(
                first_difference(
                    others,
                    [entry[1:] for entry in broken["notices"]],
                    f"walk {seed} notices",
                    ("clean", "with a bad row"),
                )
                + f" (bad row on {task})"
            )
        if [entry[1:] for entry in broken["digests"]] != [e[1:] for e in clean["digests"]]:
            raise AssertionError(f"walk {seed}: the digests changed with a bad row on {task}")
        for index, one in enumerate(broken["passes"]):
            if one[2:] != [[], [task]]:
                raise AssertionError(
                    f"walk {seed} pass {index}: failed {one[2]}, skipped {one[3]}; "
                    f"expected none failed and {task} skipped"
                )
        if any(row[1] == bad for row in broken["tables"]["posts"]):
            raise AssertionError(f"walk {seed}: a post was queued for {task}, whose row is bad")


def leaf(error: BaseException) -> BaseException:
    while isinstance(error, BaseExceptionGroup):
        error = error.exceptions[0]
    return error


def main() -> None:
    oracle()
    print("walk oracle ok")
    if "--oracle-only" in sys.argv:
        print("FAILURES 0")
        return
    failures = 0
    checks = (
        ("same answers", same_answers, "the spec commit's results, notices, digests and rows"),
        ("one bad row", isolated, "every other task sent and only the bad task skipped"),
    )
    for name, check, expected in checks:
        with TemporaryDirectory() as directory:
            try:
                check(Path(directory))
            except Exception as raised:
                error = leaf(raised)
                detail = str(error) if isinstance(error, AssertionError) else ""
                print(
                    f"FAIL {name}: expected {expected}; "
                    f"{detail or type(error).__name__ + ' ' + str(error)}"
                )
                failures += 1
            else:
                print(name + " ok")
    print(f"FAILURES {failures}")


if __name__ == "__main__":
    main()
