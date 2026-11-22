"""Synthetic loop-status properties: a walk of restarted loops with injected half failures,
skipped tasks and one corrupted status row sends exactly what the spec commit's code sends; after
every pass the stored status matches the probe's own count of each half's failures; and
`docket status`, run in another process, prints that status."""

import json
import os
import random
import subprocess
import sys
import tarfile
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
PROBE = "docs/verification/probe-05f.py"
# Ten minutes before the 07:00 digest slot, so every walk crosses it.
T0 = "2026-11-20T06:50:00+00:00"
SEEDS = (5, 23, 61)
SEGMENTS = (12, 9, 11, 8)
PASSES = sum(SEGMENTS)
# Corrupt the stored status before this segment: counts must start again there.
CORRUPT_BEFORE = 2
# Run one segment of the walk under one source tree, in its own process (a restart). Each pass's
# failures and bad row are set before it runs; each pass's stored row and deliveries are printed.
LOOP = r"""
import json, sqlite3, sys
from datetime import datetime, time, timedelta
from pathlib import Path
sys.path[:0] = [sys.argv[1]]
from docket import clock, core, ids, reminders
from docket.deadlines import Deadline
from docket.notifier import NotifierError
from docket.store import Store

case, path, segment = json.loads(sys.argv[2]), Path(sys.argv[3]), int(sys.argv[4])
first = sum(case["segments"][:segment])
count = case["segments"][segment]
start = datetime.fromisoformat(case["start"])
moment = [start + timedelta(seconds=30 * first)]
clock.now = lambda: moment[0]
keys = iter(f"probe-{segment}-key-{n}" for n in range(1, 10000))
ids.new_id = lambda: next(keys)
failing = set()


class Boom(Exception):
    pass


pending_task_ids = Store.pending_task_ids
send_digest = reminders.send_digest


def broken_pending(self, *args, **kwargs):
    if "reminders" in failing:
        raise Boom()
    return pending_task_ids(self, *args, **kwargs)


def broken_digest(*args, **kwargs):
    if "digest" in failing:
        raise Boom()
    return send_digest(*args, **kwargs)


Store.pending_task_ids = broken_pending
reminders.send_digest = broken_digest


class Notifier:
    def __init__(self):
        self.notices, self.digests = [], []

    def send(self, notice):
        if (int(notice.task_id[1:]) + len(self.notices)) % 4 == 0:
            raise NotifierError("synthetic delivery failure")
        self.notices.append([notice.key, notice.task_id, notice.text])

    def send_digest(self, digest):
        self.digests.append([digest.key, digest.heading, [l.task_id for l in digest.lines]])


notifier = Notifier()
seen = []


def row():
    with sqlite3.connect(path) as other:
        found = other.execute(
            "SELECT pass_at, sent, digest, reminders_failures, digest_failures, skipped "
            "FROM loop_status"
        ).fetchall()
    return [list(one) for one in found]


def prepare(index):
    failing.clear()
    failing.update(case["fail"][index])
    store._connection.execute("UPDATE reminders SET voided_at = ? WHERE task = 1 AND "
                              "planned_at NOT LIKE '%+00:00'", (case["start"],))
    if case["skip"][index]:
        store._connection.execute(
            "INSERT INTO reminders (task, kind, fire_at, planned_at) VALUES (1, 'before', ?, ?)",
            (case["start"].replace("+00:00", ".000000+00:00"), case["start"][:19]),
        )


class Stop:
    def __init__(self):
        self.waits = 0
        self.mark = (0, 0)

    def is_set(self):
        return self.waits >= count

    def wait(self, timeout):
        sent = len(notifier.notices) - self.mark[0]
        digests = len(notifier.digests) - self.mark[1]
        seen.append({"row": row(), "sent": sent, "digests": digests})
        self.mark = (len(notifier.notices), len(notifier.digests))
        self.waits += 1
        moment[0] += timedelta(seconds=timeout)
        if not self.is_set():
            prepare(first + self.waits)
        return self.is_set()


with Store(path) as store:
    if segment == 0:
        for hours in case["deadlines"]:
            core.create_task(
                store, title="Synthetic probe task", source="owner",
                deadline=Deadline(start + timedelta(hours=hours), "UTC", True),
            )
    if segment == case["corrupt_before"]:
        store._connection.execute("UPDATE loop_status SET pass_at = '2026-11-20T06:00:00'")
    prepare(first)
    reminders.run_loop(store, notifier, zone="UTC", at=time(7), stop=Stop())
with sqlite3.connect(path) as db:
    tables = {
        name: [list(one) for one in db.execute(f"SELECT * FROM {name} ORDER BY rowid")]
        for name in ("tasks", "reminders", "posts", "post_reminders", "digests", "digest_tasks")
    }
print(json.dumps({"seen": seen, "notices": notifier.notices, "digests": notifier.digests,
                  "tables": tables}))
"""
# Run `docket status` in its own process, with its clock fixed.
STATUS = r"""
import sys
from datetime import datetime
sys.path[:0] = [sys.argv[1]]
from docket import clock
from docket.cli import app
clock.now = lambda: datetime.fromisoformat(sys.argv[2])
app(["status"], prog_name="docket")
"""


def walk(seed: int) -> dict:
    chance = random.Random(seed)
    kinds = ([], ["reminders"], ["digest"], ["reminders", "digest"])
    fail = [chance.choices(kinds, weights=(6, 2, 2, 1))[0] for _ in range(PASSES)]
    # Forced: a run of three digest failures, then a clean pass that resets the count.
    fail[14:18] = [["digest"], ["digest"], ["digest"], []]
    skip = [5 <= index < 10 or 25 <= index < 28 for index in range(PASSES)]
    deadlines = [-20, *(chance.choice((0.05, 0.13, 0.25, 0.4, 0.6)) for _ in range(4))]
    return {
        "start": T0,
        "segments": list(SEGMENTS),
        "corrupt_before": CORRUPT_BEFORE,
        "fail": fail,
        "skip": skip,
        "deadlines": deadlines,
    }


def model(case: dict) -> list[list]:
    """Each pass's (pass_at, reminders failures, digest failures, skipped), by the probe's rule."""
    start = datetime.fromisoformat(case["start"])
    corrupt_at = sum(case["segments"][: case["corrupt_before"]])
    rows, reminders, digest = [], 0, 0
    for index in range(PASSES):
        if index == corrupt_at:
            reminders = digest = 0
        failed = case["fail"][index]
        skipped = ["t1"] if case["skip"][index] and "reminders" not in failed else []
        reminders = reminders + 1 if "reminders" in failed or skipped else 0
        digest = digest + 1 if "digest" in failed else 0
        at = (start + timedelta(seconds=30 * index)).isoformat(timespec="microseconds")
        rows.append([at, reminders, digest, json.dumps(skipped, separators=(",", ":"))])
    return rows


def oracle() -> None:
    assert walk(SEEDS[0]) == walk(SEEDS[0]), "a walk is not repeatable"
    for seed in SEEDS:
        case = walk(seed)
        rows = model(case)
        assert len(rows) == PASSES == len(case["fail"]) == len(case["skip"])
        assert rows[16][2] >= 3, "the forced digest failures do not count up"
        assert rows[17][2] == 0, "the forced clean pass does not reset the digest count"
        assert any(row[3] == '["t1"]' for row in rows), "no pass skips a task"
        assert any(case["fail"][i] == ["reminders"] for i in range(PASSES)), "reminders never fail"
    one = {**walk(SEEDS[0]), "fail": [["digest"]] * PASSES, "skip": [False] * PASSES}
    counts = [row[2] for row in model(one)]
    corrupt_at = sum(SEGMENTS[:CORRUPT_BEFORE])
    assert counts[:3] == [1, 2, 3], "failures do not count up from the first pass"
    assert counts[corrupt_at - 1 : corrupt_at + 1] == [corrupt_at, 1], "no restart at corruption"


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


def child(script: str, *args: str) -> str:
    finished = subprocess.run(
        [sys.executable, "-I", "-c", script, *args], capture_output=True, text=True
    )
    if finished.returncode:
        lines = [line.strip("│╭╮╰╯─ ") for line in finished.stderr.splitlines()]
        last = ([line for line in lines if any(c.isalnum() for c in line)] or ["no output"])[-1]
        raise AssertionError(f"a child process stopped: {last}")
    return finished.stdout


def run_walk(source: Path, case: dict, folder: Path) -> dict:
    folder.mkdir()
    path = folder / "docket.sqlite3"
    merged: dict = {"seen": [], "notices": [], "digests": []}
    for segment in range(len(case["segments"])):
        found = json.loads(child(LOOP, str(source), json.dumps(case), str(path), str(segment)))
        for name in ("seen", "notices", "digests"):
            merged[name] += found[name]
        merged["tables"] = found["tables"]
    return merged


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


def same_sends(root: Path) -> None:
    spec = spec_source(root)
    for seed in SEEDS:
        case = walk(seed)
        old = run_walk(spec, case, root / f"old-{seed}")
        new = run_walk(ROOT / "src", case, root / f"new-{seed}")
        old.pop("seen")
        new.pop("seen")
        if not new["digests"]:
            raise AssertionError(f"walk {seed} sent no digest, so it proves nothing about one")
        if old != new:
            raise AssertionError(first_difference(old, new, f"walk {seed}"))


def counted(root: Path) -> None:
    for seed in SEEDS:
        case = walk(seed)
        expected = model(case)
        found = run_walk(ROOT / "src", case, root / f"walk-{seed}")["seen"]
        for index, (one, want) in enumerate(zip(found, expected, strict=True)):
            if len(one["row"]) != 1:
                raise AssertionError(f"walk {seed} pass {index}: {len(one['row'])} status rows")
            row = one["row"][0]
            got = [row[0], row[3], row[4], row[5]]
            if got != want:
                raise AssertionError(
                    f"walk {seed} pass {index} (failed {case['fail'][index]}, skip "
                    f"{case['skip'][index]}): stored {got}, expected {want}"
                )
            if [row[1], row[2]] != [one["sent"], int(one["digests"] > 0)]:
                raise AssertionError(
                    f"walk {seed} pass {index}: stored sent {row[1]} and digest {row[2]}, "
                    f"but {one['sent']} notices and {one['digests']} digests were delivered"
                )


def label(at: datetime) -> str:
    return f"{at:%a} {at:%b} {at.day} {at:%H:%M} UTC"


def health(failures: int) -> str:
    return "ok" if failures == 0 else f"failing for {failures} pass" + "es" * (failures > 1)


def another_process(root: Path) -> None:
    case = walk(SEEDS[0])
    folder = root / "data"
    seen = run_walk(ROOT / "src", case, folder)["seen"][-1]
    at_text, reminders, digest, skipped = model(case)[-1]
    at = datetime.fromisoformat(at_text)
    os.environ.update({"DOCKET_DATA_DIR": str(folder), "DOCKET_TIME_ZONE": "UTC"})
    rest = [
        f"Reminders: {health(reminders)}, {seen['sent']} sent",
        f"Digest: {health(digest)}" + (", sent" if seen["digests"] else ""),
    ] + [f"Skipped tasks: {', '.join(json.loads(skipped))}"] * (skipped != "[]")
    for later, state in ((30, "running"), (301, "not running")):
        printed = child(STATUS, str(ROOT / "src"), (at + timedelta(seconds=later)).isoformat())
        expected = [f"Reminder loop: {state}, last pass {label(at)}", *rest]
        if printed.splitlines() != expected:
            raise AssertionError(
                f"{later} s after the last pass: "
                + first_difference(
                    expected, printed.splitlines(), "status lines", ("expected", "printed")
                )
            )


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
        ("same sends", same_sends, "the spec commit's notices, digests and rows"),
        ("counted", counted, "each pass's stored status to match the probe's count"),
        ("another process", another_process, "docket status to print the stored status"),
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
