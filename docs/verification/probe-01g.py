"""Phase 1g probe: what the given tests do not reach. Run from the repository root:
.venv/bin/python docs/verification/probe-01g.py

A random walk of `docket tasks edit` and `docket tasks plan` over several tasks with random valid
and invalid input, each answer checked against the probe's own order of checks and its model of
the tasks. Expected text comes from Phase 1d's views, which this phase does not change. It sets its
own temporary data folder and time zone, and touches no network, Keychain or real data folder.
"""

import os
import random
import re
import tempfile
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

FAILURES = 0
NY = "America/New_York"
DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
TIME = re.compile(r"[0-9]{2}:[0-9]{2}")
BAD = {"Cc", "Cf", "Zl", "Zp"}
TITLE_SENTENCE = "A title is 1 to 100 characters on one line, with no space at either end."


def read_date(text: str) -> date | None:
    if not DATE.fullmatch(text):
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def read_time(text: str) -> time | None:
    if not TIME.fullmatch(text):
        return None
    try:
        return time.fromisoformat(text)
    except ValueError:
        return None


def instant(day: date, at: time) -> datetime:
    return datetime.combine(day, at, tzinfo=ZoneInfo(NY)).astimezone(UTC)


def title_ok(title: str) -> bool:
    import unicodedata

    if not 1 <= len(title) <= 100 or title != title.strip():
        return False
    return all(unicodedata.category(char) not in BAD for char in title)


assert read_date("2026-11-20") == date(2026, 11, 20) and read_date("20261120") is None
assert read_time("14:00") == time(14) and read_time("24:00") is None
assert instant(date(2027, 3, 14), time(2, 30)) == datetime(2027, 3, 14, 7, 30, tzinfo=UTC)
assert title_ok("Pay rent") and not title_ok(" Pay rent")
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


def walk() -> bool:
    from typer.testing import CliRunner

    from docket import clock, core
    from docket.cli import app
    from docket.config import get_settings
    from docket.store import open_store
    from docket.views import deadline_text, work_text

    os.environ["DOCKET_DATA_DIR"] = tempfile.mkdtemp()
    os.environ["DOCKET_TIME_ZONE"] = NY
    os.environ["DOCKET_WORK_MINUTES"] = "60"
    count = [0]
    start = datetime(2026, 11, 14, 14, 0, tzinfo=UTC)

    def now() -> datetime:
        count[0] += 1
        return start + timedelta(seconds=count[0])

    clock.now = now
    rng = random.Random(51)
    runner = CliRunner(env={"COLUMNS": "200"})
    model: dict[str, dict[str, object]] = {}
    with open_store(get_settings()) as store:
        for number in range(1, 5):
            made = core.create_task(store, title=f"Task {number}", source="owner")
            model[made.id] = {"title": made.title, "deadline": None, "work": None, "state": "open"}
        core.change_state(store, "t4", "done", actor="owner")
        model["t4"]["state"] = "done"
    dates = ["2026-11-20", "2026-11-21", "2027-03-14", "20261120", "2026-11-31", "2026-02-29"]
    times = ["09:00", "14:00", "17:00", "02:30", "23:00", "23:30", "1400", "24:00", "7:00"]
    titles = ["Pay rent", "Pay rent today", " Pay rent", "", "x" * 100, "x" * 101, "Pay\trent"]
    minutes = [None, None, "30", "60", "90", "4", "721", "720"]
    reached = {"updated": 0, "planned": 0, "cleared": 0, "same": 0, "cli": 0, "core": 0}
    for _ in range(900):
        task_id = rng.choice(list(model) + ["t9"])
        task = model.get(task_id)
        if rng.random() < 0.5:
            args, outcome = edit_case(rng, dates, times, titles, task)
        else:
            args, outcome = plan_case(rng, dates, times, minutes, task)
        kind, payload = outcome
        before = count[0]
        result = runner.invoke(app, ["tasks", *args[:1], task_id, *args[1:]])
        got = (result.exit_code, result.stdout, result.stderr)
        if kind == "refuse":
            wanted = (1, "", payload.replace("<id>", task_id) + "\n")
            reached["cli" if count[0] == before else "core"] += 1
        elif kind == "same":
            wanted = (0, f"Nothing changed for {task_id}.\n", "")
            reached["same"] += 1
        else:
            task.update(payload)
            updated = start + timedelta(seconds=before + 1)
            if args[0] == "edit":
                tail = ", no deadline"
                if task["deadline"] is not None:
                    tail = f", due {deadline_text(task['deadline'], NY, updated)}"
                wanted = (0, f"Updated {task_id}: {task['title']}{tail}\n", "")
                reached["updated"] += 1
            elif task["work"] is None:
                wanted = (0, f"Cleared the work time of {task_id}.\n", "")
                reached["cleared"] += 1
            else:
                wanted = (0, f"Planned {task_id}: {work_text(task['work'], NY, updated)}\n", "")
                reached["planned"] += 1
        if got != wanted or count[0] - before > 1:
            print(f"  {args} on {task_id} {task}: got {got!r}, wanted {wanted!r}")
            return False
        if task is not None:
            with open_store(get_settings()) as store:
                stored = store.task(task_id)
            seen = (stored.title, stored.deadline, stored.work)
            if seen != (task["title"], task["deadline"], task["work"]):
                print(f"  {task_id}: stored {seen}, model {task}")
                return False
    if not all(value >= 15 for value in reached.values()):
        print(f"  reached {reached}")
        return False
    return True


def core_outcome(task, title, deadline, work):
    """What core.edit_task does after the command's own checks."""
    if title is not None and not title_ok(title):
        return "refuse", TITLE_SENTENCE
    if task is None:
        return "refuse", "There is no task <id>."
    if task["state"] in ("done", "cancelled"):
        return "refuse", "Task <id> has ended; reopen it first."
    new = dict(task)
    if title is not None:
        new["title"] = title
    if deadline != "keep":
        new["deadline"] = deadline
    if work != "keep":
        new["work"] = work
    if new["deadline"] is not None and new["work"] is not None:
        if new["work"].end > new["deadline"].at:
            return "refuse", "The work time must end by the deadline."
    changed = {name: new[name] for name in ("title", "deadline", "work") if new[name] != task[name]}
    return ("change", changed) if changed else ("same", None)


def edit_case(rng, dates, times, titles, task):
    from docket.deadlines import make_deadline

    title = rng.choice(titles) if rng.random() < 0.4 else None
    due = rng.choice(dates) if rng.random() < 0.5 else None
    at = rng.choice(times) if rng.random() < 0.4 else None
    no_due = rng.random() < 0.15
    args = ["edit"]
    if title is not None:
        args += ["--title", title]
    if due is not None:
        args += ["--due", due]
    if at is not None:
        args += ["--at", at]
    if no_due:
        args += ["--no-due"]
    if title is None and due is None and not no_due and at is None:
        return args, ("refuse", "Give --title, --due or --no-due.")
    if due is not None and no_due:
        return args, ("refuse", "--due and --no-due can't be used together.")
    if at is not None and due is None:
        return args, ("refuse", "--at needs --due.")
    deadline = "keep"
    if due is not None:
        day = read_date(due)
        if day is None:
            return args, ("refuse", "--due must be a date like 2026-11-20.")
        clock_time = None
        if at is not None:
            clock_time = read_time(at)
            if clock_time is None:
                return args, ("refuse", "--at must be a time like 17:00.")
        deadline = make_deadline(day, clock_time, NY)
    elif no_due:
        deadline = None
    return args, core_outcome(task, title, deadline, "keep")


def plan_case(rng, dates, times, minutes, task):
    from docket.deadlines import WorkTime

    clear = rng.random() < 0.2
    day = rng.choice(dates) if rng.random() < 0.85 or not clear else None
    start = rng.choice(times) if day is not None and rng.random() < 0.9 else None
    if clear and rng.random() < 0.7:
        day, start = None, None
    length = rng.choice(minutes)
    args = ["plan"] + [value for value in (day, start) if value is not None]
    if length is not None:
        args += ["--minutes", length]
    if clear:
        args += ["--clear"]
        if day is not None or start is not None or length is not None:
            return args, ("refuse", "--clear takes no date, start time or --minutes.")
        return args, core_outcome(task, None, "keep", None)
    if day is None or start is None:
        return args, ("refuse", "Give a date and a start time, or --clear.")
    found_day = read_date(day)
    if found_day is None:
        return args, ("refuse", "The date must look like 2026-11-20.")
    found_time = read_time(start)
    if found_time is None:
        return args, ("refuse", "The start time must look like 14:00.")
    span = int(length) if length is not None else 60
    if not 5 <= span <= 720:
        return args, ("refuse", "--minutes must be 5 to 720.")
    begin = instant(found_day, found_time)
    midnight = instant(found_day + timedelta(days=1), time(0))
    if begin + timedelta(minutes=span) > midnight:
        return args, ("refuse", "A work time must end by midnight.")
    return args, core_outcome(task, None, "keep", WorkTime(begin, span, NY))


check("900 random edits and plans follow the order of checks and the model", walk)

print(f"FAILURES {FAILURES}")
