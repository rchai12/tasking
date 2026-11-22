"""Synthetic migration and task-column properties: the moved migrations upgrade every old
database to the same rows the spec commit's code writes, a reopen changes nothing, task writes
land in the same columns as before, and an unknown update column is refused."""

import random
import sqlite3
import subprocess
import sys
import tarfile
from contextlib import closing
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

PROBE = "docs/verification/probe-05b.py"
STAMP = "2026-10-31T12:00:00.000000+00:00"
# Deadlines planted before an upgrade, each side of the 2026-11-01 New York change.
DEADLINES = (
    ("2026-11-01T05:30:00.000000+00:00", "America/New_York", 1),
    ("2026-11-01T22:00:00.000000+00:00", "America/New_York", 0),
    ("2027-03-14T06:30:00.000000+00:00", "America/New_York", 1),
    ("2026-11-20T15:00:00.000000+00:00", "Europe/London", 1),
)
STATES = ("open", "in_progress", "done", "cancelled")
ZONES = ("America/New_York", "Europe/London", "Asia/Tokyo")
WALKS = (11, 23, 37)
MOVED = (
    "_migrate",
    "_apply_migration",
    "_user_version",
    "_migrate_references",
    "_refuse_invalid_references",
    "_refuse_reference",
    "_backfill_reminders",
)
# Run in a child under one source tree: open (and so migrate) the database, then, for a walk,
# write the given tasks and changes through the public Store methods.
CHILD = r"""
import json, sys
from datetime import datetime
from pathlib import Path
sys.path[:0] = [sys.argv[1], sys.argv[2]]
from docket.deadlines import Deadline, WorkTime
from docket.store import Store

def instant(text):
    return None if text is None else datetime.fromisoformat(text)

path, steps = Path(sys.argv[3]), json.loads(sys.argv[4])
with Store(path) as store:
    for step in steps:
        due, hours = step["deadline"], step["work"]
        deadline = due and Deadline(instant(due[0]), *due[1:])
        work = hours and WorkTime(instant(hours[0]), *hours[1:])
        with store.transaction():
            if step["op"] == "insert":
                store.insert_task(
                    title=step["title"], state=step["state"], deadline=deadline, work=work,
                    source=step["source"], provider=step["provider"],
                    message_id=step["message_id"], link=step["link"], at=instant(step["at"]),
                )
            else:
                store.update_task(
                    step["task"], at=instant(step["at"]), title=step["title"],
                    state=step["state"], deadline=deadline, work=work,
                )
"""


def oracle() -> None:
    for at, zone, given in DEADLINES:
        assert at.endswith("+00:00") and zone in ZONES and given in (0, 1)
    steps = walk_steps(WALKS[0])
    assert steps == walk_steps(WALKS[0]), "a walk is not repeatable"
    inserts = [step for step in steps if step["op"] == "insert"]
    assert len(inserts) >= 3 and any(step["source"] == "email" for step in inserts)
    for step in inserts:
        assert 1 <= len(step["title"]) <= 100
        assert (step["source"] == "email") == (step["provider"] is not None)
    for step in steps:
        if step["work"]:
            assert 5 <= step["work"][1] <= 720
        if step["op"] == "update":
            assert int(step["task"][1:]) <= len(inserts)


def walk_steps(seed: int) -> list[dict]:
    chance = random.Random(seed)
    steps: list[dict] = []
    for number in range(1, 7):
        at = f"2026-11-{number + 10:02d}T{chance.randrange(24):02d}:15:00.000000+00:00"
        source = ("email", "agent", "owner")[number % 3]
        if number > 3 and chance.random() < 0.5:
            steps.append(
                {
                    "op": "update",
                    "task": f"t{chance.randrange(1, 4)}",
                    "at": at,
                    "title": f"Synthetic changed title {number}",
                    "state": chance.choice(STATES),
                    "deadline": deadline(chance),
                    "work": work(chance),
                }
            )
            continue
        steps.append(
            {
                "op": "insert",
                "at": at,
                "title": f"Synthetic walk title {number}",
                "state": chance.choice(STATES),
                "deadline": deadline(chance),
                "work": work(chance),
                "source": source,
                "provider": "outlook" if source == "email" else None,
                "message_id": f"synthetic-message-{number}" if source == "email" else None,
                "link": f"https://mail.example.test/{number}" if source == "email" else None,
            }
        )
    return steps


def deadline(chance: random.Random) -> list | None:
    if chance.random() < 0.3:
        return None
    return list(chance.choice(DEADLINES)[:2]) + [bool(chance.randrange(2))]


def work(chance: random.Random) -> list | None:
    if chance.random() < 0.4:
        return None
    start = f"2026-11-{chance.randrange(1, 28):02d}T{chance.randrange(24):02d}:00:00+00:00"
    return [start, chance.randrange(5, 721), chance.choice(ZONES)]


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


def run(source: Path, path: Path, steps: list[dict]) -> None:
    import json

    finished = subprocess.run(
        [sys.executable, "-I", "-c", CHILD, str(source), str(ROOT), str(path), json.dumps(steps)],
        capture_output=True,
        text=True,
    )
    if finished.returncode:
        last = (finished.stderr.strip().splitlines() or ["no output"])[-1]
        raise AssertionError(f"the child under {source.parent.name} stopped: {last}")


def dump(path: Path) -> list[str]:
    with closing(sqlite3.connect(path)) as db:
        version = db.execute("PRAGMA user_version").fetchone()[0]
        return [f"user_version {version}", *db.iterdump()]


def first_difference(old: list[str], new: list[str]) -> str:
    for index, (left, right) in enumerate(zip(old, new, strict=False)):
        if left != right:
            return f"line {index}: spec {left[:90]!r} now {right[:90]!r}"
    return f"spec has {len(old)} lines, now {len(new)}"


def prepared(path: Path, version: int) -> None:
    from tests.startup_cases import prepare

    prepare(path, version)
    with closing(sqlite3.connect(path)) as db, db:
        for number, (at, zone, given) in enumerate(DEADLINES, start=2):
            db.execute(
                "INSERT INTO tasks (title, state, deadline_at, deadline_zone, "
                "deadline_time_given, source, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, 'owner', ?, ?)",
                (f"Synthetic old task {number}", STATES[number % 4], at, zone, given, STAMP, STAMP),
            )


def upgrades(root: Path) -> None:
    spec = spec_source(root)
    for version in (1, 2):
        old, new = root / f"old{version}.sqlite3", root / f"new{version}.sqlite3"
        prepared(old, version)
        new.write_bytes(old.read_bytes())
        run(spec, old, [])
        run(ROOT / "src", new, [])
        upgraded = dump(new)
        if upgraded[0] != "user_version 6":
            raise AssertionError(f"version {version} upgraded to {upgraded[0]}")
        if dump(old) != upgraded:
            raise AssertionError(f"version {version}: {first_difference(dump(old), upgraded)}")
        if not any('INSERT INTO "reminders"' in line for line in upgraded):
            raise AssertionError(f"version {version}: the upgrade backfilled no reminder")
        run(ROOT / "src", new, [])
        if dump(new) != upgraded:
            raise AssertionError(f"version {version}: a reopen changed the database")


def walks(root: Path) -> None:
    spec = spec_source(root)
    for seed in WALKS:
        steps = walk_steps(seed)
        old, new = root / f"old-walk{seed}.sqlite3", root / f"new-walk{seed}.sqlite3"
        run(spec, old, steps)
        run(ROOT / "src", new, steps)
        if dump(old) != dump(new):
            raise AssertionError(f"walk {seed}: {first_difference(dump(old), dump(new))}")


def refusals(root: Path) -> None:
    from docket import _store_migrate, _store_tasks
    from docket.store import Store

    kept = [name for name in MOVED if hasattr(Store, name)]
    if kept:
        raise AssertionError(f"Store still has {', '.join(kept)}")
    if not callable(getattr(_store_migrate, "migrate", None)):
        raise AssertionError("_store_migrate has no migrate")
    path = root / "docket.sqlite3"
    run(ROOT / "src", path, walk_steps(WALKS[0]))
    with closing(sqlite3.connect(path)) as db:
        db.row_factory = sqlite3.Row
        before = dump(path)
        for column in ("source", "created_at", "updated_at", "number", "link"):
            try:
                _store_tasks.update_task(db, 1, STAMP, {"title": "Synthetic refused", column: 1})
            except ValueError as raised:
                if str(raised) != "unknown task column":
                    raise AssertionError(f"{column} refused with {raised}") from None
            else:
                raise AssertionError(f"update of {column} was not refused")
            db.rollback()
        if dump(path) != before:
            raise AssertionError("a refused update changed t1")


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
    same = "the same rows as the spec commit's code"
    checks = (
        ("upgrades", upgrades, same + ", reminders backfilled, a reopen a no-op"),
        ("task walks", walks, same + " after the same inserts and updates"),
        ("refusals", refusals, "no migration step on Store, every unknown column refused"),
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
