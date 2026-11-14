"""Phase 1e probe: what the given tests do not reach. Run from the repository root:
.venv/bin/python docs/verification/probe-01e.py

It runs `docket tasks add` on random dates, times and titles and checks each answer against its
own rules, lists random sets of tasks against its own sort, and shows every task. It sets its own
temporary data folder and time zone, and touches no network, Keychain or real data folder.
"""

import os
import random
import re
import tempfile
from datetime import UTC, date, datetime, time, timedelta

FAILURES = 0
DATE_SHAPE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
TIME_SHAPE = re.compile(r"[0-9]{2}:[0-9]{2}")
TITLE_SENTENCE = "A title is 1 to 100 characters on one line, with no space at either end."


def oracle_date(text: str) -> date | None:
    if not DATE_SHAPE.fullmatch(text):
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def oracle_time(text: str) -> time | None:
    if not TIME_SHAPE.fullmatch(text):
        return None
    try:
        return time.fromisoformat(text)
    except ValueError:
        return None


assert oracle_date("2026-11-20") == date(2026, 11, 20)
assert oracle_date("20261120") is None and oracle_date("2026-11-31") is None
assert oracle_date("2026-11-2٠") is None
assert oracle_time("17:00") == time(17, 0) and oracle_time("24:00") is None
assert oracle_time("1700") is None and oracle_time("17:00Z") is None
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


def fresh(zone: str) -> None:
    os.environ["DOCKET_DATA_DIR"] = tempfile.mkdtemp()
    os.environ["DOCKET_TIME_ZONE"] = zone
    os.environ.pop("DOCKET_WORK_MINUTES", None)


def clock_at(start: datetime):
    count = [0]

    def now() -> datetime:
        count[0] += 1
        return start + timedelta(seconds=count[0])

    return now


def adding_follows_the_rules() -> bool:
    from typer.testing import CliRunner

    from docket import clock
    from docket.cli import AT_MESSAGE, AT_WITHOUT_DUE_MESSAGE, DUE_MESSAGE, app
    from docket.config import get_settings
    from docket.deadlines import make_deadline
    from docket.store import open_store

    rng = random.Random(31)
    runner = CliRunner(env={"COLUMNS": "200"})
    clock.now = clock_at(datetime(2026, 11, 14, 14, 0, tzinfo=UTC))
    dates = ["2026-11-20", "2027-03-14", "2026-11-01", "2026-02-29", "2028-02-29", "20261120"]
    dates += ["2026-1-05", "2026-11-31", "2026-13-01", "", "２０２６-11-20", "2026-11-20 "]
    times = ["17:00", "02:30", "01:30", "00:00", "23:59", "24:00", "7:00", "1700", "17", "17:00Z"]
    times += ["T17:00", "17:00:30", "17:60", " 17:00", "１7:00"]
    titles = ["Pay rent", "x" * 100, "Café ☕", " Pay rent", "Pay rent ", "Pay\trent", "x" * 101]
    reached = {"added": 0, "due": 0, "at": 0, "at-without-due": 0, "title": 0}
    fresh("America/New_York")
    count = 0
    for _ in range(1500):
        title = rng.choice(titles)
        due = rng.choice(dates) if rng.random() < 0.7 else None
        at = rng.choice(times) if rng.random() < 0.6 else None
        args = ["tasks", "add", "--", title]
        if due is not None:
            args[2:2] = ["--due", due]
        if at is not None:
            args[2:2] = ["--at", at]
        result = runner.invoke(app, args)
        if at is not None and due is None:
            expected, kind = AT_WITHOUT_DUE_MESSAGE, "at-without-due"
        elif due is not None and oracle_date(due) is None:
            expected, kind = DUE_MESSAGE, "due"
        elif at is not None and oracle_time(at) is None:
            expected, kind = AT_MESSAGE, "at"
        elif title in (" Pay rent", "Pay rent ", "Pay\trent", "x" * 101):
            expected, kind = TITLE_SENTENCE, "title"
        else:
            expected, kind = None, "added"
        reached[kind] += 1
        if expected is not None:
            if (result.exit_code, result.stdout, result.stderr) != (1, "", expected + "\n"):
                print(f"  {args}: {result.exit_code} {result.stdout!r} {result.stderr!r}")
                return False
            continue
        count += 1
        if result.exit_code != 0 or not result.stdout.startswith(f"Added t{count}: {title}"):
            print(f"  {args}: {result.exit_code} {result.stdout!r} {result.stderr!r}")
            return False
        with open_store(get_settings()) as store:
            made = store.task(f"t{count}")
        wanted = None
        if due is not None:
            wanted = make_deadline(
                oracle_date(due), oracle_time(at) if at else None, "America/New_York"
            )
        if made is None or made.deadline != wanted or made.title != title:
            print(f"  {args}: stored {made}")
            return False
    if not all(value >= 20 for value in reached.values()):
        print(f"  reached {reached}")
        return False
    return True


def lists_and_shows_follow_the_store() -> bool:
    from typer.testing import CliRunner

    from docket import clock, core
    from docket.cli import app
    from docket.config import get_settings
    from docket.deadlines import Deadline
    from docket.store import open_store
    from docket.views import task_detail, task_line

    rng = random.Random(32)
    runner = CliRunner(env={"COLUMNS": "200"})
    for trial in range(30):
        zone = rng.choice(["America/New_York", "Asia/Tokyo", "UTC", "Europe/London"])
        fresh(zone)
        start = datetime(2026, 11, 14, 14, 0, tzinfo=UTC)
        clock.now = clock_at(start)
        with open_store(get_settings()) as store:
            for number in range(rng.randrange(0, 25)):
                deadline = None
                if rng.random() < 0.7:
                    at = start + timedelta(hours=rng.choice((-50, -1, 0, 1, 1, 3, 72, 72)))
                    deadline = Deadline(
                        at, rng.choice(["America/New_York", "UTC"]), rng.random() < 0.5
                    )
                core.create_task(store, title=f"Task {number}", source="owner", deadline=deadline)
                action = rng.choice(["start", "done", "cancel", None, None])
                if action is not None:
                    core.change_state(store, f"t{number + 1}", action, actor="owner")
            everything = store.tasks()
        now_at = [start + timedelta(days=1)]
        clock.now = lambda moment=now_at[0]: moment
        for flag, states in (([], {"open", "in_progress"}), (["--all"], None)):
            chosen = [task for task in everything if states is None or task.state in states]
            chosen.sort(
                key=lambda task: (
                    task.deadline is None,
                    task.deadline.at if task.deadline else start,
                    int(task.id[1:]),
                )
            )
            expected = "\n".join(task_line(task, zone, now_at[0]) for task in chosen) or "No tasks."
            result = runner.invoke(app, ["tasks", "list", *flag])
            if (result.exit_code, result.stdout) != (0, expected + "\n"):
                print(f"  trial {trial} list {flag}")
                return False
        for task in everything:
            result = runner.invoke(app, ["tasks", "show", task.id])
            if result.stdout != "\n".join(task_detail(task, zone, now_at[0])) + "\n":
                print(f"  trial {trial} show {task.id}")
                return False
    return True


check("1500 random adds answer exactly as the rules say", adding_follows_the_rules)
check("list and show match the store in four zones", lists_and_shows_follow_the_store)

print(f"FAILURES {FAILURES}")
