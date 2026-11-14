"""Phase 1f probe: what the given tests do not reach. Run from the repository root:
.venv/bin/python docs/verification/probe-01f.py

A random walk of `docket tasks start/done/cancel/reopen` over several tasks, each answer checked
against the probe's own table, sentences and audit rows. It sets its own temporary data folder
and time zone, and touches no network, Keychain or real data folder.
"""

import os
import random
import tempfile
from datetime import UTC, datetime, timedelta

FAILURES = 0
WORDS = {"open": "open", "in_progress": "in progress", "done": "done", "cancelled": "cancelled"}
VERBS = {"start": "Started", "done": "Done", "cancel": "Cancelled", "reopen": "Reopened"}
# (state, command) -> new state, "same" for a repeat, or "ended" for a refusal.
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


def expected(task_id: str, title: str, state: str, command: str) -> tuple[int, str, str, str]:
    """Exit code, stdout, stderr and the state after, by the probe's own rules."""
    outcome = TABLE[(state, command)]
    if outcome == "ended":
        return 1, "", f"Task {task_id} has ended; reopen it first.\n", state
    if outcome == "same":
        return 0, f"{task_id} is already {WORDS[state]}.\n", "", state
    return 0, f"{VERBS[command]} {task_id}: {title}\n", "", outcome


assert len(TABLE) == 16
assert expected("t2", "Pay rent", "open", "done") == (0, "Done t2: Pay rent\n", "", "done")
assert expected("t2", "x", "in_progress", "reopen")[1] == "t2 is already in progress.\n"
assert expected("t2", "x", "done", "cancel")[0] == 1
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

    os.environ["DOCKET_DATA_DIR"] = tempfile.mkdtemp()
    os.environ["DOCKET_TIME_ZONE"] = "America/New_York"
    count = [0]
    start = datetime(2026, 11, 14, 14, 0, tzinfo=UTC)

    def now() -> datetime:
        count[0] += 1
        return start + timedelta(seconds=count[0])

    clock.now = now
    rng = random.Random(41)
    runner = CliRunner(env={"COLUMNS": "200"})
    titles = ["Pay rent", "Café ☕ receipt", "x" * 100, "-dash first", "t1"]
    states: dict[str, str] = {}
    actions: dict[str, int] = {}
    with open_store(get_settings()) as store:
        for number, title in enumerate(titles, start=1):
            core.create_task(store, title=title, source="owner")
            states[f"t{number}"] = "open"
            actions[f"t{number}"] = 1
    reached = {"changed": 0, "same": 0, "ended": 0, "unknown": 0}
    for _ in range(600):
        command = rng.choice(list(VERBS))
        if rng.random() < 0.08:
            task_id = rng.choice(["t0", "t9", "T1", "x", "t01"])
            before = count[0]
            result = runner.invoke(app, ["tasks", command, task_id])
            wanted = (1, "", f"There is no task {task_id}.\n")
            if (result.exit_code, result.stdout, result.stderr) != wanted:
                print(f"  {command} {task_id}: {result.stdout!r} {result.stderr!r}")
                return False
            if count[0] - before > 1:
                return False
            reached["unknown"] += 1
            continue
        task_id = rng.choice(list(states))
        title = titles[int(task_id[1:]) - 1]
        code, out, err, after = expected(task_id, title, states[task_id], command)
        before = count[0]
        result = runner.invoke(app, ["tasks", command, task_id])
        if (result.exit_code, result.stdout, result.stderr) != (code, out, err):
            print(
                f"  {command} {task_id} from {states[task_id]}: {result.stdout!r} {result.stderr!r}"
            )
            return False
        if count[0] - before != 1:
            print(f"  {command} {task_id}: {count[0] - before} clock reads")
            return False
        kind = TABLE[(states[task_id], command)]
        reached["changed" if kind not in ("same", "ended") else kind] += 1
        if kind not in ("same", "ended"):
            actions[task_id] += 1
        states[task_id] = after
        with open_store(get_settings()) as store:
            task = store.task(task_id)
            rows = store.audit(task_id)
        if task is None or task.state != after or len(rows) != actions[task_id]:
            print(f"  {task_id}: stored {task} with {len(rows)} audit rows")
            return False
        if kind not in ("same", "ended") and (rows[-1].action, rows[-1].actor) != (
            command,
            "owner",
        ):
            return False
    if not all(value >= 20 for value in reached.values()):
        print(f"  reached {reached}")
        return False
    return True


check("600 random state commands follow the table, sentences and audit", walk)

print(f"FAILURES {FAILURES}")
