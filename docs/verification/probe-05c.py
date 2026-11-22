"""Synthetic import-direction properties: the modules import in any order in a fresh
interpreter, and the moved planner and notice text answer exactly as the spec commit's
`reminders` module did."""

import itertools
import json
import random
import subprocess
import sys
import tarfile
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
PROBE = "docs/verification/probe-05c.py"
# The modules the old cycle ran through, each pair imported first in both orders.
CYCLE = (
    "docket.store",
    "docket._store_migrate",
    "docket.reminders",
    "docket.reminder_plan",
    "docket.views",
    "docket.core",
)
ORDER_SEEDS = (5, 17, 29, 41)
TASK_SEEDS = (3, 13, 31)
STATES = ("open", "in_progress", "done", "cancelled")
ZONES = ("America/New_York", "Europe/London", "Asia/Tokyo")
# Instants either side of both 2026-11-01 and 2027-03-14 New York changes.
MOMENTS = (
    "2026-10-31T20:00:00+00:00",
    "2026-11-01T05:30:00+00:00",
    "2026-11-01T06:30:00+00:00",
    "2026-11-01T21:45:00+00:00",
    "2027-03-14T06:30:00+00:00",
    "2027-03-14T07:30:00+00:00",
)
KINDS = ("start", "before", "due_soon", "due", "late")
# Run under one source tree: answer every planner case and every text case as JSON.
CHILD = r"""
import json, sys
from datetime import datetime
sys.path[:0] = [sys.argv[1]]
from docket import reminders
from docket.deadlines import Deadline, WorkTime
from docket.store import Task

cases = json.loads(sys.argv[2])
answers = {"plans": [], "notices": [], "headings": []}
for case in cases["plans"]:
    due, hours = case["deadline"], case["work"]
    task = Task(
        id="t1", title="Synthetic probe task", state=case["state"],
        deadline=due and Deadline(datetime.fromisoformat(due[0]), due[1], due[2]),
        work=hours and WorkTime(datetime.fromisoformat(hours[0]), hours[1], hours[2]),
        source="owner", provider=None, message_id=None, link=None,
        created_at=datetime.fromisoformat(case["now"]),
        updated_at=datetime.fromisoformat(case["now"]),
    )
    plans = reminders.plan_reminders(task, datetime.fromisoformat(case["now"]))
    answers["plans"].append([[row.kind, row.fire_at.isoformat()] for row in plans])
for kind, missed in cases["notices"]:
    answers["notices"].append(reminders.notice_text(kind, missed))
for count in cases["headings"]:
    answers["headings"].append(reminders.digest_heading(count))
print(json.dumps(answers))
"""


def plan_cases(seed: int) -> list[dict]:
    chance = random.Random(seed)
    cases = []
    for _ in range(40):
        deadline = None
        if chance.random() < 0.8:
            deadline = [chance.choice(MOMENTS), chance.choice(ZONES), bool(chance.randrange(2))]
        work = None
        if chance.random() < 0.5:
            work = [chance.choice(MOMENTS), chance.randrange(5, 721), chance.choice(ZONES)]
        cases.append(
            {
                "state": chance.choice(STATES),
                "deadline": deadline,
                "work": work,
                "now": chance.choice(MOMENTS),
            }
        )
    return cases


def text_cases() -> dict:
    return {
        "notices": [[kind, missed] for kind in KINDS for missed in range(4)],
        "headings": list(range(4)),
    }


def oracle() -> None:
    assert plan_cases(TASK_SEEDS[0]) == plan_cases(TASK_SEEDS[0]), "a walk is not repeatable"
    for seed in TASK_SEEDS:
        cases = plan_cases(seed)
        assert any(case["deadline"] for case in cases) and any(case["work"] for case in cases)
        assert any(case["state"] in ("done", "cancelled") for case in cases)
        for case in cases:
            if case["work"]:
                assert 5 <= case["work"][1] <= 720
    assert len(text_cases()["notices"]) == 20
    assert len(set(itertools.permutations(CYCLE, 2))) == 30


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


def answers(source: Path, cases: dict) -> dict:
    finished = subprocess.run(
        [sys.executable, "-I", "-c", CHILD, str(source), json.dumps(cases)],
        capture_output=True,
        text=True,
    )
    if finished.returncode:
        last = (finished.stderr.strip().splitlines() or ["no output"])[-1]
        raise AssertionError(f"the child under {source.parent.name} stopped: {last}")
    return json.loads(finished.stdout)


def importing(order: tuple[str, ...]) -> subprocess.Popen:
    lines = [f"sys.path.insert(0, {str(ROOT / 'src')!r})", *(f"import {name}" for name in order)]
    return subprocess.Popen(
        [sys.executable, "-I", "-c", "import sys\n" + "\n".join(lines)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )


def every_module() -> list[str]:
    package = ROOT / "src" / "docket"
    names = []
    for path in sorted(package.rglob("*.py")):
        parts = path.relative_to(package.parent).with_suffix("").parts
        names.append(".".join(parts[:-1] if parts[-1] == "__init__" else parts))
    return names


def orders(_root: Path) -> None:
    runs: list[tuple[str, ...]] = list(itertools.permutations(CYCLE, 2))
    for seed in ORDER_SEEDS:
        shuffled = every_module()
        random.Random(seed).shuffle(shuffled)
        runs.append(tuple(shuffled))
    started = [(order, importing(order)) for order in runs]
    for order, process in started:
        _, error = process.communicate(timeout=120)
        if process.returncode:
            last = (error.strip().splitlines() or ["no output"])[-1]
            first = " then ".join(order[:2]) + (" ..." if len(order) > 2 else "")
            raise AssertionError(f"importing {first} stopped: {last}")


def same_answers(root: Path) -> None:
    spec = spec_source(root)
    for seed in TASK_SEEDS:
        cases = {"plans": plan_cases(seed), **text_cases()}
        old, new = answers(spec, cases), answers(ROOT / "src", cases)
        for part in ("plans", "notices", "headings"):
            for index, (left, right) in enumerate(zip(old[part], new[part], strict=True)):
                if left != right:
                    raise AssertionError(
                        f"seed {seed} {part} case {index}: spec {left!r}, now {right!r}"
                    )


def standalone(_root: Path) -> None:
    sys.path.insert(0, str(ROOT / "src"))
    from types import SimpleNamespace

    from docket import reminder_plan, reminders, views

    for name in ("plan_reminders", "PlannedReminder", "LATE_MINUTES"):
        if getattr(reminders, name) is not getattr(reminder_plan, name):
            raise AssertionError(f"reminders.{name} is not reminder_plan.{name}")
    for name in ("notice_text", "digest_heading"):
        if getattr(reminders, name) is not getattr(views, name):
            raise AssertionError(f"reminders.{name} is not views.{name}")
    ended = SimpleNamespace(state="done", deadline=None, work=None)
    from datetime import UTC, datetime

    if reminder_plan.plan_reminders(ended, datetime(2026, 11, 1, tzinfo=UTC)) != ():
        raise AssertionError("an ended task with no times was planned reminders")


def leaf(error: BaseException) -> BaseException:
    while isinstance(error, BaseExceptionGroup):
        error = error.exceptions[0]
    return error


def main() -> None:
    oracle()
    print("case oracle ok")
    if "--oracle-only" in sys.argv:
        print("FAILURES 0")
        return
    failures = 0
    checks = (
        ("import orders", orders, "every pair of the old cycle and four full shuffles import"),
        ("same answers", same_answers, "the spec commit's plans, notices and headings"),
        ("standalone planner", standalone, "the moved names reachable from reminders"),
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
