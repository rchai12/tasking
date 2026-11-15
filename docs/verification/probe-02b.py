"""Phase 2b probe: what the given tests do not reach. Run from the repository root:
.venv/bin/python docs/verification/probe-02b.py

It fuzzes the email service's task and link bodies one change at a time, sends each with fresh,
repeated and reused keys, and checks every answer against the probe's own rules: the status, an
answer body of only `id` or `error`, no echo of the request, and a stored task matching the body.
`--oracle-only` prints the walk's reach counts from the rules alone, for the architect.
It uses temporary folders and touches no network, Keychain or real data folder.
"""

import json
import random
import re
import sys
import tempfile
import unicodedata
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, available_timezones

FAILURES = 0
ORACLE_ONLY = "--oracle-only" in sys.argv
STEPS = 1500
ZONES = available_timezones()
FIELDS = {"source", "title", "deadline", "provider", "message_id", "link"}
LINK_FIELDS = {"source", "provider", "message_id", "link"}
BASE = {
    "source": "email",
    "title": "Pay rent",
    "deadline": {"date": "2026-11-20", "time": "17:00", "time_zone": "America/New_York"},
    "provider": "gmail",
    "message_id": "personal/1",
    "link": "https://mail.example/1",
}
LINK = {"source": "email", "provider": "outlook", "message_id": "home/2", "link": "https://o/2"}
NOISE = [None, 7, "", " ", "x" * 101, ["a"], {"a": 1}, "Pay\trent", "américa", "２０２６-11-20"]


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def deadline_ok(value: object) -> bool:
    if value is None:
        return True
    if not isinstance(value, dict) or set(value) != {"date", "time", "time_zone"}:
        return False
    day, at, zone = value["date"], value["time"], value["time_zone"]
    if not isinstance(day, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", day):
        return False
    try:
        date.fromisoformat(day)
    except ValueError:
        return False
    if at is not None:
        if not isinstance(at, str) or not re.fullmatch(r"[0-9]{2}:[0-9]{2}", at):
            return False
        try:
            time.fromisoformat(at)
        except ValueError:
            return False
    return isinstance(zone, str) and zone in ZONES


def title_ok(value: object) -> bool:
    if not isinstance(value, str) or not 1 <= len(value) <= 100 or value != value.strip():
        return False
    return all(unicodedata.category(char) not in {"Cc", "Cf", "Zl", "Zp"} for char in value)


def reference_ok(body: dict) -> bool:
    texts = (body["message_id"], body["link"])
    return body["provider"] in {"gmail", "outlook", "yahoo"} and all(
        isinstance(text, str) and text != "" for text in texts
    )


def task_rule(body: object) -> str | None:
    """The error code the probe expects for a task body, or None for an accepted one."""
    if not isinstance(body, dict) or set(body) != FIELDS:
        return "invalid_body"
    if not all(isinstance(body[name], str) for name in FIELDS - {"deadline"}):
        return "invalid_body"
    if not deadline_ok(body["deadline"]):
        return "invalid_deadline"
    if not title_ok(body["title"]):
        return "invalid_title"
    if body["source"] != "email":
        return "invalid_source"
    return None if reference_ok(body) else "invalid_reference"


def link_rule(body: object) -> str | None:
    if not isinstance(body, dict) or set(body) != LINK_FIELDS:
        return "invalid_body"
    if not all(isinstance(body[name], str) for name in LINK_FIELDS):
        return "invalid_body"
    if body["source"] != "email":
        return "invalid_source"
    return None if reference_ok(body) else "invalid_reference"


assert task_rule(BASE) is None and link_rule(LINK) is None
assert task_rule({**BASE, "title": " x"}) == "invalid_title"
assert task_rule({**BASE, "deadline": {**BASE["deadline"], "time_zone": "america/new_york"}}) == (
    "invalid_deadline"
)
assert task_rule({**BASE, "x": 1}) == "invalid_body"
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


def mutate(rng: random.Random, base: dict) -> object:
    body = json.loads(json.dumps(base))
    roll = rng.random()
    if roll < 0.12:
        return body
    if roll < 0.22:
        body.pop(rng.choice(list(body)))
        return body
    if roll < 0.3:
        body[rng.choice(["extra", "evidence", "Title"])] = "x"
        return body
    if roll < 0.34:
        return rng.choice([None, [body], "body", 7])
    name = rng.choice(list(body))
    if name == "deadline" and rng.random() < 0.8:
        deadline = body["deadline"] = dict(
            body["deadline"] or {"date": "2026-11-20", "time": None, "time_zone": "UTC"}
        )
        part = rng.choice(["date", "time", "time_zone", "drop", "null"])
        if part == "drop":
            deadline.pop(rng.choice(list(deadline)))
        elif part == "null":
            body["deadline"] = None
        elif part == "date":
            deadline["date"] = rng.choice(
                [
                    "2026-11-21",
                    "2028-02-29",
                    "2026-02-29",
                    "20261120",
                    "2026-1-5",
                    "２０２６-11-20",
                    5,
                ]
            )
        elif part == "time":
            deadline["time"] = rng.choice(
                [None, "09:30", "23:59", "24:00", "1700", "7:00", "17:00:00", "T17:00"]
            )
        else:
            deadline["time_zone"] = rng.choice(
                [
                    "UTC",
                    "Asia/Tokyo",
                    "america/new_york",
                    "AMERICA/NEW_YORK",
                    "",
                    "Mars/Base",
                    "Europe/London",
                ]
            )
        return body
    body[name] = rng.choice(
        NOISE + [base[name], "gmail", "yahoo", "email", "agent", "Pay rent today"]
    )
    return body


def walk() -> bool:
    rng = random.Random(71)
    keys: dict[str, tuple[str, str]] = {}  # key -> (canonical body, id) for accepted tasks
    links: dict[str, tuple[str, str, str]] = {}
    tasks: list[str] = []
    reached = {"201": 0, "200": 0, "409": 0, "422": 0, "400": 0, "404": 0, "link-201": 0}
    if not ORACLE_ONLY:
        from docket import clock
        from docket.intake import accept_link, accept_task
        from docket.store import Store

        start = datetime(2026, 11, 14, 14, 0, tzinfo=UTC)
        count = [0]

        def now() -> datetime:
            count[0] += 1
            return start + timedelta(seconds=count[0])

        clock.now = now
        store = Store(Path(tempfile.mkdtemp()) / "docket.sqlite3")
    for step in range(STEPS):
        as_link = bool(tasks) and rng.random() < 0.3
        roll = rng.random()
        pool = links if as_link else keys
        if roll < 0.06:
            key = rng.choice([None, "", "k" * 201])
        elif roll < 0.4 and pool:
            key = rng.choice(list(pool))
        else:
            key = f"k{step}"
        body = mutate(rng, LINK if as_link else BASE)
        task_id = None
        if as_link:
            task_id = rng.choice([*tasks, "t99999", "x"]) if step % 25 else "t99999"
        if key is None or not 1 <= len(key) <= 200:
            wanted = (400, {"error": "missing_key"})
        elif as_link and task_id not in tasks:
            wanted = (404, {"error": "unknown_task"})
        else:
            code = link_rule(body) if as_link else task_rule(body)
            if code is not None:
                wanted = (422, {"error": code})
            elif key in pool:
                first = pool[key]
                same = first[0] == canonical(body) and (not as_link or first[2] == task_id)
                wanted = (200, {"id": first[1]}) if same else (409, {"error": "key_reused"})
            elif key in (keys if as_link else links):
                wanted = (409, {"error": "key_reused"})
            elif as_link:
                links[key] = (canonical(body), f"l{len(links) + 1}", task_id)
                wanted = (201, {"id": links[key][1]})
            else:
                tasks.append(f"t{len(tasks) + 1}")
                keys[key] = (canonical(body), tasks[-1])
                wanted = (201, {"id": tasks[-1]})
        reached["link-201" if as_link and wanted[0] == 201 else str(wanted[0])] += 1
        if ORACLE_ONLY:
            continue
        if as_link:
            answer = accept_link(store, task_id, key=key, body=body)
        else:
            answer = accept_task(store, key=key, body=body)
        if (answer.status, answer.body) != wanted:
            kind = "link" if as_link else "task"
            print(f"  step {step}: {kind} {key!r} {body!r}: {answer} != {wanted}")
            return False
        if answer.status in (200, 201) and not as_link:
            stored = store.task(answer.body["id"])
            if (
                stored is None
                or stored.title != body["title"]
                or stored.message_id != body["message_id"]
            ):
                print(f"  step {step}: stored {stored}")
                return False
    if ORACLE_ONLY:
        print(f"  reached {reached}")
        return True
    if not all(value >= 15 for value in reached.values()):
        print(f"  reached {reached}")
        return False
    return [task.id for task in store.tasks()] == tasks


def deadlines_match_make_deadline() -> bool:
    from docket import clock
    from docket.deadlines import make_deadline
    from docket.intake import accept_task
    from docket.store import Store

    clock.now = lambda: datetime(2026, 11, 14, 14, 0, tzinfo=UTC)
    rng = random.Random(72)
    store = Store(Path(tempfile.mkdtemp()) / "docket.sqlite3")
    zones = ["America/New_York", "Asia/Kolkata", "Australia/Lord_Howe", "UTC"]
    for number in range(300):
        day = date(2026, 1, 1) + timedelta(days=rng.randrange(730))
        at = None if rng.random() < 0.4 else time(rng.randrange(24), rng.choice((0, 30)))
        zone = rng.choice(zones)
        deadline = {"date": day.isoformat(), "time": at and at.strftime("%H:%M"), "time_zone": zone}
        answer = accept_task(store, key=f"d{number}", body={**BASE, "deadline": deadline})
        stored = store.task(answer.body.get("id", ""))
        if answer.status != 201 or stored is None:
            return False
        if stored.deadline != make_deadline(day, at, zone) or ZoneInfo(zone) is None:
            return False
    return True


check(f"{STEPS} fuzzed task and link bodies get exactly the rules' answers", walk)
if not ORACLE_ONLY:
    check(
        "300 valid deadlines are stored as make_deadline makes them", deadlines_match_make_deadline
    )

print(f"FAILURES {FAILURES}")
