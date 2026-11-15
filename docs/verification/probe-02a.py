"""Phase 2a probe: what the given tests do not reach. Run from the repository root:
.venv/bin/python docs/verification/probe-02a.py

A random walk of keyed creates and follow-up links through two stores on one file, checked
against the probe's own model of the keys; and races of two threads sending the same key at once.
`--oracle-only` runs the walk with the model alone and prints its reach counts, for the architect.
It uses temporary folders and touches no network, Keychain or real data folder.
"""

import json
import random
import sys
import tempfile
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

FAILURES = 0
ORACLE_ONLY = "--oracle-only" in sys.argv
CLIENTS = ["email", "agent"]
KEYS = ["k1", "k2", "k3", "gmail:personal/1", "gmail:personal/2", "r1:s1"]
TITLES = ["Pay rent", "Book flights", "Café ☕"]
STEPS = 700
UNKNOWN = "t99999"  # never created: the walk makes at most STEPS tasks
assert int(UNKNOWN[1:]) > STEPS


def canonical(request: dict[str, object]) -> str:
    return json.dumps(request, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def expect(model: dict, client: str, key: str, kind: str, request: dict, task_id: str | None):
    """'new', 'same' or 'reused', by the probe's own rules for a keyed request."""
    found = model.get((client, key))
    if found is None:
        return "new"
    same = found["kind"] == kind and found["request"] == canonical(request)
    if kind == "link":
        same = same and found["task"] == task_id
    return "same" if same else "reused"


demo: dict = {}
assert expect(demo, "email", "k", "task", {"a": 1}, None) == "new"
demo[("email", "k")] = {"kind": "task", "request": canonical({"a": 1}), "task": "t1"}
assert expect(demo, "email", "k", "task", {"a": 1}, None) == "same"
assert expect(demo, "email", "k", "task", {"a": 2}, None) == "reused"
assert expect(demo, "email", "k", "link", {"a": 1}, "t1") == "reused"
assert expect(demo, "agent", "k", "task", {"a": 1}, None) == "new"
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


def clock_at(start: datetime):
    lock, count = threading.Lock(), [0]

    def now() -> datetime:
        with lock:
            count[0] += 1
            return start + timedelta(seconds=count[0])

    return now


def walk() -> bool:
    rng = random.Random(61)
    model: dict = {}
    tasks: list[str] = []
    links: dict[str, int] = {}
    reached = {"new-task": 0, "new-link": 0, "same": 0, "reused": 0, "unknown-task": 0}
    if not ORACLE_ONLY:
        from docket import clock, core
        from docket.store import Store

        clock.now = clock_at(datetime(2026, 11, 14, 14, 0, tzinfo=UTC))
        path = Path(tempfile.mkdtemp()) / "docket.sqlite3"
        stores = [Store(path), Store(path)]
    for step in range(STEPS):
        client = rng.choice(CLIENTS)
        used = [k for (c, k) in model if c == client]
        key = f"fresh-{step}" if rng.random() < 0.5 or not used else rng.choice([*used, *KEYS])
        title = rng.choice(TITLES)
        forced = step % 20 == 10 and bool(tasks)
        if forced:
            # Forced: a link to an unknown task under a fresh key, so that answer is reached.
            client, key = "email", f"fresh-{step}"
        as_link = forced or (client == "email" and tasks and rng.random() < 0.4)
        if as_link:
            task_id = UNKNOWN if forced else rng.choice([*tasks, UNKNOWN])
            request = {
                "provider": "gmail",
                "message_id": f"personal/{title}",
                "link": "https://m/x",
            }
            outcome = expect(model, client, key, "link", request, task_id)
            if outcome == "new" and task_id == UNKNOWN:
                outcome = "unknown-task"
        else:
            task_id = None
            request = {"source": client, "title": title}
            outcome = expect(model, client, key, "task", request, None)
        if not ORACLE_ONLY:
            store = stores[step % 2]
            try:
                if as_link:
                    result = core.add_link(
                        store,
                        task_id,
                        client=client,
                        key=key,
                        request=request,
                        provider="gmail",
                        message_id=request["message_id"],
                        link="https://m/x",
                    )
                    got = "new" if result.changed else "same"
                    if got == "same" and result.link.id != model[(client, key)]["link"]:
                        return False
                else:
                    reference = {}
                    if client == "email":
                        reference = {
                            "provider": "gmail",
                            "message_id": f"m/{key}",
                            "link": "https://m/",
                        }
                    result = core.create_task_once(
                        store,
                        client=client,
                        key=key,
                        request=request,
                        title=title,
                        source=client,
                        **reference,
                    )
                    got = "new" if result.changed else "same"
                    if got == "same" and result.task.id != model[(client, key)]["task"]:
                        return False
            except core.CoreError as error:
                got = {"key_reused": "reused", "unknown_task": "unknown-task"}.get(
                    error.code, error.code
                )
            if got != outcome:
                kind = "link" if as_link else "task"
                print(f"  step {step}: {client} {key} {kind}: {got} != {outcome}")
                return False
        if outcome == "new":
            if as_link:
                links[task_id] = links.get(task_id, 0) + 1
                number = sum(links.values())
                model[(client, key)] = {
                    "kind": "link",
                    "request": canonical(request),
                    "task": task_id,
                    "link": f"l{number}",
                }
                reached["new-link"] += 1
            else:
                tasks.append(f"t{len(tasks) + 1}")
                model[(client, key)] = {
                    "kind": "task",
                    "request": canonical(request),
                    "task": tasks[-1],
                }
                reached["new-task"] += 1
        else:
            reached[outcome] += 1
        if not ORACLE_ONLY:
            seen = [task.id for task in stores[0].tasks()]
            if seen != tasks or any(len(stores[1].links(t)) != n for t, n in links.items()):
                print(f"  step {step}: tasks {seen} != {tasks}")
                return False
    if ORACLE_ONLY:
        print(f"  reached {reached}")
    elif not all(value >= 15 for value in reached.values()):
        print(f"  reached {reached}")
        return False
    return True


def races() -> bool:
    from docket import clock, core
    from docket.store import Store

    clock.now = clock_at(datetime(2026, 11, 14, 14, 0, tzinfo=UTC))
    for trial in range(40):
        path = Path(tempfile.mkdtemp()) / "docket.sqlite3"
        Store(path).close()
        differ = trial % 2 == 1
        results: list[str] = []
        gate = threading.Barrier(2)

        def send(number: int, path=path, gate=gate, results=results, differ=differ) -> None:
            title = f"Pay rent {number}" if differ else "Pay rent"
            with Store(path) as mine:
                gate.wait()
                try:
                    outcome = core.create_task_once(
                        mine,
                        client="agent",
                        key="r1:s1",
                        request={"title": title},
                        title=title,
                        source="agent",
                    )
                    results.append("new" if outcome.changed else "same")
                except core.CoreError as error:
                    results.append(error.code)
                except Exception as error:  # noqa: BLE001
                    results.append(type(error).__name__)

        threads = [threading.Thread(target=send, args=(n,)) for n in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)
        with Store(path) as store:
            count = len(store.tasks())
        wanted = ["key_reused", "new"] if differ else ["new", "same"]
        if sorted(results) != wanted or count != 1:
            print(f"  trial {trial}: {results}, {count} tasks")
            return False
    return True


check("700 keyed creates and links follow the model of the keys", walk)
if not ORACLE_ONLY:
    check("two senders of one key at once make one task", races)

print(f"FAILURES {FAILURES}")
