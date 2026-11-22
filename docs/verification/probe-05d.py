"""Synthetic closed-list properties: every key check, intake answer, reminder plan, deadline
status and reminder replacement answers exactly as the spec commit's code did, and the
derived names are domain's own values."""

import json
import random
import subprocess
import sys
import tarfile
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
PROBE = "docs/verification/probe-05d.py"
NOW = "2026-10-31T20:00:00+00:00"
# Keys either side of each bound: none, the wrong type, empty, 1, 200 and 201 characters.
KEYS = (None, 7, "", "k", "k" * 200, "k" * 201, "é" * 200, "é" * 201)
HEADER_KEYS = (None, "", "k", "k" * 200, "k" * 201)
PLAN_SEEDS = (3, 13, 31)
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
# Minutes after a deadline: before it, at it, inside and either side of the due window's end.
STATUS_OFFSETS = (-1, 0, 29, 30, 31, 600)
# Run under one source tree: answer the named part's cases as JSON.
CHILD = r"""
import json, sqlite3, sys
from datetime import date, datetime, timedelta
from pathlib import Path
sys.path[:0] = [sys.argv[1]]
from docket import clock, core, deadlines, intake, reminder_plan
from docket.deadlines import Deadline, WorkTime
from docket.store import Store

part, cases, folder = sys.argv[2], json.loads(sys.argv[3]), Path(sys.argv[4])
now = datetime.fromisoformat(cases["now"])
clock.now = lambda: now

def body(number):
    return {
        "source": "email", "title": f"Synthetic intake task {number}", "deadline": None,
        "provider": "gmail", "message_id": f"synthetic/{number}",
        "link": f"https://mail.example/{number}",
    }

def outcome(call):
    try:
        found = call()
    except Exception as error:
        return f"{type(error).__name__}: {error}"
    return "changed" if getattr(found, "changed", True) else "replayed"

answers = []
if part == "keys":
    with Store(folder / "keys.sqlite3") as store:
        core.create_task(store, title="Synthetic key task", source="owner")
        for number, key in enumerate(cases["keys"]):
            reply = intake.accept_task(store, client="email", key=key, body=body(number))
            answers.append([reply.status, reply.body])
            answers.append(outcome(lambda: core.change_state_once(
                store, "t1", "start", client="agent", key=key, request={"n": number})))
            def digest():
                with store.transaction():
                    return store.queue_digest(
                        date(2026, 11, 1 + number), ("t1",), key=key, at=now)
            answers.append(outcome(digest))
    from fastapi.testclient import TestClient
    from docket import web
    app = web.create_app(
        open_store=lambda: Store(folder / "web.sqlite3"),
        tokens={"synthetic-token-5d": "email"}, port=8767,
    )
    with TestClient(app, base_url="http://127.0.0.1:8767") as client:
        for number, key in enumerate(cases["header_keys"]):
            headers = {"Authorization": "Bearer synthetic-token-5d"}
            if key is not None:
                headers["Idempotency-Key"] = key
            reply = client.post("/tasks", json=body(100 + number), headers=headers)
            answers.append([reply.status_code, reply.json()])
elif part == "intake":
    with Store(folder / "intake.sqlite3") as store:
        for step in cases["steps"]:
            call = intake.accept_link if step["link"] else intake.accept_task
            args = ("t1",) if step["link"] else ()
            reply = call(store, *args, client=step["client"], key=step["key"], body=step["body"])
            answers.append([reply.status, reply.body])
elif part == "plans":
    for case in cases["plans"]:
        due, hours = case["deadline"], case["work"]
        task = type("Plannable", (), {
            "state": case["state"],
            "deadline": due and Deadline(datetime.fromisoformat(due[0]), due[1], due[2]),
            "work": hours and WorkTime(datetime.fromisoformat(hours[0]), hours[1], hours[2]),
        })()
        plans = reminder_plan.plan_reminders(task, datetime.fromisoformat(case["now"]))
        answers.append([[row.kind, row.fire_at.isoformat()] for row in plans])
    for at, offset in cases["statuses"]:
        deadline = Deadline(datetime.fromisoformat(at), "America/New_York", True)
        later = deadline.at + timedelta(minutes=offset)
        answers.append(deadlines.status(deadline, later))
else:
    path = folder / "edits.sqlite3"
    with Store(path) as store:
        for step in cases["edits"]:
            due, hours = step["deadline"], step["work"]
            values = {
                "deadline": due and Deadline(datetime.fromisoformat(due[0]), due[1], True),
                "work": hours and WorkTime(datetime.fromisoformat(hours[0]), hours[1], hours[2]),
            }
            if step["op"] == "create":
                answers.append(outcome(lambda: core.create_task(
                    store, title="Synthetic edited task", source="owner", **values)))
            else:
                changed = {name: values[name] for name in step["fields"]}
                answers.append(outcome(lambda: core.edit_task(
                    store, "t1", actor="owner", **changed)))
    with sqlite3.connect(path) as db:
        answers.append([list(row) for row in db.execute("SELECT * FROM reminders ORDER BY number")])
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


def intake_steps() -> list[dict]:
    task = {
        "source": "email",
        "title": "Synthetic intake walk",
        "deadline": {"date": "2026-11-01", "time": "17:00", "time_zone": "America/New_York"},
        "provider": "outlook",
        "message_id": "synthetic/walk/1",
        "link": "https://mail.example/walk/1",
    }
    link = {
        "source": "email",
        "provider": "outlook",
        "message_id": "synthetic/walk/2",
        "link": "https://mail.example/walk/2",
    }
    other = {**task, "title": "Synthetic other title"}
    bad_zone = {**task, "deadline": {**task["deadline"], "time_zone": 5}}
    return [
        {"link": False, "client": "email", "key": "walk-1", "body": task},
        {"link": False, "client": "email", "key": "walk-1", "body": task},
        {"link": False, "client": "email", "key": "walk-1", "body": other},
        {"link": False, "client": "agent", "key": "walk-2", "body": task},
        {"link": False, "client": "email", "key": "walk-3", "body": {**task, "provider": 5}},
        {"link": False, "client": "email", "key": "walk-4", "body": bad_zone},
        {"link": True, "client": "email", "key": "walk-5", "body": link},
        {"link": True, "client": "email", "key": "walk-5", "body": link},
        {"link": True, "client": "agent", "key": "walk-6", "body": link},
        {"link": True, "client": "email", "key": "walk-7", "body": {**link, "source": "agent"}},
    ]


def edit_steps() -> list[dict]:
    due = ["2026-11-02T22:00:00+00:00", "America/New_York"]
    moved = ["2026-11-01T21:00:00+00:00", "America/New_York"]
    work = ["2026-11-01T14:00:00+00:00", 90, "America/New_York"]
    later = ["2026-11-01T16:00:00+00:00", 30, "Europe/London"]
    return [
        {"op": "create", "deadline": due, "work": work},
        {"op": "edit", "fields": ["deadline"], "deadline": moved, "work": None},
        {"op": "edit", "fields": ["work"], "deadline": None, "work": later},
        {"op": "edit", "fields": ["deadline", "work"], "deadline": due, "work": work},
        {"op": "edit", "fields": ["work"], "deadline": None, "work": None},
        {"op": "edit", "fields": ["deadline"], "deadline": None, "work": None},
    ]


def parts() -> dict[str, dict]:
    statuses = [[at, offset] for at in MOMENTS for offset in STATUS_OFFSETS]
    return {
        "keys": {"now": NOW, "keys": list(KEYS), "header_keys": list(HEADER_KEYS)},
        "intake": {"now": NOW, "steps": intake_steps()},
        "plans": {
            "now": NOW,
            "plans": [case for seed in PLAN_SEEDS for case in plan_cases(seed)],
            "statuses": statuses,
        },
        "edits": {"now": NOW, "edits": edit_steps()},
    }


def oracle() -> None:
    assert plan_cases(PLAN_SEEDS[0]) == plan_cases(PLAN_SEEDS[0]), "a walk is not repeatable"
    lengths = [len(key) for key in KEYS if isinstance(key, str)]
    assert {0, 1, 200, 201} <= set(lengths), "a key bound is not reached"
    assert all(key is None or key.isascii() for key in HEADER_KEYS)
    cases = parts()["plans"]["plans"]
    assert any(case["deadline"] for case in cases) and any(case["work"] for case in cases)
    assert any(case["state"] in ("done", "cancelled") for case in cases)
    assert {29, 30, 31} <= set(STATUS_OFFSETS)
    steps = intake_steps()
    assert steps[0] == steps[1] and steps[0]["key"] == steps[2]["key"] != steps[3]["key"]
    assert [step["op"] for step in edit_steps()].count("create") == 1


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


def answers(source: Path, part: str, cases: dict, folder: Path) -> list:
    folder.mkdir()
    finished = subprocess.run(
        [sys.executable, "-I", "-c", CHILD, str(source), part, json.dumps(cases), str(folder)],
        capture_output=True,
        text=True,
    )
    if finished.returncode:
        last = (finished.stderr.strip().splitlines() or ["no output"])[-1]
        raise AssertionError(f"the {part} child under {source.parent.name} stopped: {last}")
    return json.loads(finished.stdout)


def first_difference(left: object, right: object, where: str) -> str:
    """Name the innermost differing item, so a long row list prints one row."""
    if isinstance(left, list) and isinstance(right, list):
        for index, (inner_left, inner_right) in enumerate(zip(left, right, strict=False)):
            if inner_left != inner_right:
                return first_difference(inner_left, inner_right, f"{where} item {index}")
        return f"{where}: spec has {len(left)} items, now {len(right)}"
    return f"{where}: spec {left!r}, now {right!r}"


def same_answers(root: Path) -> None:
    spec = spec_source(root)
    for part, cases in parts().items():
        old = answers(spec, part, cases, root / f"old-{part}")
        new = answers(ROOT / "src", part, cases, root / f"new-{part}")
        if old != new:
            raise AssertionError(first_difference(old, new, part))


def derived(_root: Path) -> None:
    sys.path.insert(0, str(ROOT / "src"))
    from datetime import timedelta

    from docket import clients, deadlines, domain, reminder_plan

    checks = {
        "clients.CLIENTS is domain.API_CLIENTS": clients.CLIENTS is domain.API_CLIENTS,
        "DUE_WINDOW is DUE_WINDOW_MINUTES": deadlines.DUE_WINDOW
        == timedelta(minutes=domain.DUE_WINDOW_MINUTES),
        "LATE_MINUTES starts at DUE_WINDOW_MINUTES": reminder_plan.LATE_MINUTES[0]
        == domain.DUE_WINDOW_MINUTES,
        "REMINDER_KINDS is WORK_KINDS + DEADLINE_KINDS": domain.REMINDER_KINDS
        == domain.WORK_KINDS + domain.DEADLINE_KINDS,
        "the planner orders kinds as REMINDER_KINDS": list(reminder_plan._KIND_ORDER)
        == list(domain.REMINDER_KINDS),
    }
    failed = [name for name, held in checks.items() if not held]
    if failed:
        raise AssertionError("not held: " + "; ".join(failed))


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
        ("same answers", same_answers, "the spec commit's keys, intake, plans and edits"),
        ("derived names", derived, "each derived name equal to domain's value"),
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
