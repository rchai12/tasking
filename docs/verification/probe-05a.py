"""Synthetic store-decoding properties: a bad row is refused with one constant message, a good
row decodes, a read writes nothing, and the store's files are private."""

import os
import random
import sqlite3
import stat
import sys
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

START = datetime(2026, 11, 17, 14, tzinfo=UTC)
TASKS = 4
MISSING_KEY = "probe-key-9999"
# Each stored time text, and the UTC instant it must decode to (None: refused).
TIMES = (
    ("2026-11-17T14:00:00.000000+00:00", datetime(2026, 11, 17, 14, tzinfo=UTC)),
    ("2026-11-17T14:00:00+00:00", datetime(2026, 11, 17, 14, tzinfo=UTC)),
    ("2026-11-17T14:00:00Z", datetime(2026, 11, 17, 14, tzinfo=UTC)),
    ("2026-11-01T05:30:00.000000+00:00", datetime(2026, 11, 1, 5, 30, tzinfo=UTC)),
    ("synthetic-invalid-instant", None),
    ("2026-11-17T14:00:00", None),
    ("2026-11-17T09:00:00-05:00", None),
    ("2026-11-17T15:00:00+01:00", None),
    ("", None),
)
# Each stored JSON text, and the dict it must decode to (None: refused).
OBJECTS = (
    ("{}", {}),
    ('{"title": "Synthetic probe title"}', {"title": "Synthetic probe title"}),
    ('{"tool": "create_task", "deadline": null}', {"tool": "create_task", "deadline": None}),
    ("{not json", None),
    ("[]", None),
    ("null", None),
    ("7", None),
    ('"synthetic text"', None),
    ("", None),
)
GOOD_TIMES = tuple(text for text, value in TIMES if value is not None)
GOOD_OBJECTS = tuple(text for text, value in OBJECTS if value is not None)


def decoded_time(text: str) -> datetime | None:
    for stored, value in TIMES:
        if stored == text:
            return value
    raise AssertionError(f"the probe has no time {text!r}")


def decoded_object(text: str) -> dict | None:
    for stored, value in OBJECTS:
        if stored == text:
            return value
    raise AssertionError(f"the probe has no object {text!r}")


class Model:
    """The oracle: every planted row, in insertion order, per table."""

    def __init__(self) -> None:
        # Per task: each audit row's decoded time, or None when any of its fields is refused.
        self.audit: dict[int, list[datetime | None]] = {n: [] for n in range(1, TASKS + 1)}
        self.links: list[tuple[int, int, str]] = []
        self.keys: dict[str, tuple[int, str, str]] = {}

    def add_audit(self, task: int, at: str, before: str, after: str) -> None:
        parts = (decoded_time(at), decoded_object(before), decoded_object(after))
        self.audit[task].append(None if None in parts else parts[0])

    def audit_answer(self, task: int) -> object:
        rows = self.audit[task]
        if None in rows:
            return f"invalid stored audit entry: t{task}"
        return rows

    def link_answer(self, task: int) -> object:
        mine = [(number, created) for number, owner, created in self.links if owner == task]
        for number, created in mine:
            if decoded_time(created) is None:
                return f"invalid stored link: l{number}"
        return [(f"l{number}", decoded_time(created)) for number, created in mine]

    def key_answer(self, key: str) -> object:
        if key not in self.keys:
            return None
        task, request, created = self.keys[key]
        if decoded_object(request) is None or decoded_time(created) is None:
            return f"invalid stored request key: t{task}"
        return (decoded_object(request), f"t{task}", decoded_time(created))


def oracle() -> None:
    assert len({text for text, _ in TIMES}) == len(TIMES)
    assert len({text for text, _ in OBJECTS}) == len(OBJECTS)
    assert all(value is None or value.tzinfo is UTC for _, value in TIMES)
    assert GOOD_TIMES and len(GOOD_TIMES) < len(TIMES)
    assert GOOD_OBJECTS and len(GOOD_OBJECTS) < len(OBJECTS)
    model = Model()
    model.add_audit(1, GOOD_TIMES[0], "{}", '{"title": "Synthetic probe title"}')
    assert model.audit_answer(1) == [START]
    model.add_audit(2, GOOD_TIMES[0], "{}", "[]")
    assert model.audit_answer(2) == "invalid stored audit entry: t2"
    model.add_audit(1, "2026-11-17T14:00:00", "{}", "{}")
    assert model.audit_answer(1) == "invalid stored audit entry: t1"
    model.links += [(1, 2, GOOD_TIMES[2]), (2, 2, "synthetic-invalid-instant"), (3, 2, "")]
    assert model.link_answer(2) == "invalid stored link: l2"
    assert model.link_answer(3) == []
    model.keys["k"] = (3, "[]", GOOD_TIMES[0])
    assert model.key_answer("k") == "invalid stored request key: t3"
    assert model.key_answer(MISSING_KEY) is None
    assert MISSING_KEY not in {f"probe-key-{n}" for n in range(200)}


def plant(path: Path, sql: str, values: tuple[object, ...]) -> int:
    with closing(sqlite3.connect(path)) as db, db:
        return int(db.execute(sql, values).lastrowid)


def dump(path: Path) -> list[str]:
    with closing(sqlite3.connect(path)) as db:
        return list(db.iterdump())


def answer(call) -> object:
    from docket.store import StoreError

    try:
        return call()
    except StoreError as raised:
        if raised.__cause__ is not None or not (
            raised.__context__ is None or raised.__suppress_context__
        ):
            raise AssertionError(f"{raised} carries the library's exception") from None
        return str(raised)


def seeded(root: Path) -> tuple[Path, Model]:
    from docket import core
    from docket.store import Store

    path = root / "docket.sqlite3"
    model = Model()
    with patch("docket.clock.now", return_value=START), Store(path) as store:
        for n in range(1, TASKS + 1):
            core.create_task(store, title=f"Synthetic probe task {n}", source="owner")
            model.audit[n].append(START)
    return path, model


def read_all(path: Path, model: Model) -> list[str]:
    from docket.store import Store

    problems: list[str] = []
    before = dump(path)
    with Store(path) as store:
        for n in range(1, TASKS + 1):
            got = answer(lambda n=n: store.audit(f"t{n}"))
            if isinstance(got, list):
                got = [entry.at for entry in got]
            want = model.audit_answer(n)
            if got != want:
                problems.append(f"audit t{n}: expected {want!r}, got {got!r}")
            got = answer(lambda n=n: store.links(f"t{n}"))
            if isinstance(got, list):
                got = [(link.id, link.created_at) for link in got]
            want = model.link_answer(n)
            if got != want:
                problems.append(f"links t{n}: expected {want!r}, got {got!r}")
        for key in [*model.keys, MISSING_KEY]:
            got = answer(lambda key=key: store.request_key("agent", key))
            if got is not None and not isinstance(got, str):
                got = (got.request, got.task_id, got.created_at)
            want = model.key_answer(key)
            if got != want:
                problems.append(f"key {key}: expected {want!r}, got {got!r}")
    if dump(path) != before:
        problems.append("a read changed the database")
    return problems


def plant_audit(path: Path, model: Model, task: int, at: str, before: str, after: str) -> None:
    plant(
        path,
        "INSERT INTO audit_log (task, at, action, actor, before, after) "
        "VALUES (?, ?, 'retitle', 'owner', ?, ?)",
        (task, at, before, after),
    )
    model.add_audit(task, at, before, after)


def plant_link(path: Path, model: Model, task: int, created: str) -> None:
    number = plant(
        path,
        "INSERT INTO links (task, provider, message_id, link, created_at) "
        "VALUES (?, 'gmail', ?, 'https://mail.example.test/probe', ?)",
        (task, f"synthetic-message-{len(model.links) + 1}", created),
    )
    model.links.append((number, task, created))


def plant_key(path: Path, model: Model, task: int, request: str, created: str) -> None:
    key = f"probe-key-{len(model.keys) + 1}"
    plant(
        path,
        "INSERT INTO request_keys (client, key, request, task, link, created_at) "
        "VALUES ('agent', ?, ?, ?, NULL, ?)",
        (key, request, task, created),
    )
    model.keys[key] = (task, request, created)


def forced(root: Path) -> None:
    """Every bad form once, each alone in its own data folder, beside one good row."""
    problems: list[str] = []
    cases: list[tuple[str, tuple]] = []
    for text, value in TIMES:
        if value is None:
            cases += [("audit", (text, "{}", "{}")), ("link", (text,)), ("key", ("{}", text))]
    for text, value in OBJECTS:
        if value is None:
            cases += [
                ("audit", (GOOD_TIMES[0], text, "{}")),
                ("audit", (GOOD_TIMES[0], "{}", text)),
                ("key", (text, GOOD_TIMES[0])),
            ]
    for index, (table, values) in enumerate(cases):
        folder = root / f"case-{index}"
        folder.mkdir()
        path, model = seeded(folder)
        plant_audit(path, model, 2, GOOD_TIMES[2], GOOD_OBJECTS[1], "{}")
        plant_link(path, model, 2, GOOD_TIMES[1])
        plant_key(path, model, 2, GOOD_OBJECTS[2], GOOD_TIMES[3])
        if table == "audit":
            plant_audit(path, model, 1, *values)
        elif table == "link":
            plant_link(path, model, 1, *values)
        else:
            plant_key(path, model, 1, *values)
        problems += [f"{table} {values!r}: {p}" for p in read_all(path, model)]
    assert not problems, problems[0]


def walk(root: Path, seed: int, rows: int) -> None:
    rng = random.Random(seed)
    path, model = seeded(root)
    for _ in range(rows):
        task = rng.randint(1, TASKS)
        table = rng.choice(("audit", "link", "key"))
        good = rng.random() < 0.8
        times = GOOD_TIMES if good else tuple(text for text, _ in TIMES)
        objects = GOOD_OBJECTS if good else tuple(text for text, _ in OBJECTS)
        if table == "audit":
            plant_audit(
                path, model, task, rng.choice(times), rng.choice(objects), rng.choice(objects)
            )
        elif table == "link":
            plant_link(path, model, task, rng.choice(times))
        else:
            plant_key(path, model, task, rng.choice(objects), rng.choice(times))
    problems = read_all(path, model)
    assert not problems, f"seed {seed}: {problems[0]}"


def walks(root: Path) -> None:
    for seed in (51, 52, 53):
        folder = root / f"seed-{seed}"
        folder.mkdir()
        walk(folder, seed, 40)


def mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def files(root: Path) -> None:
    """A new database is 0600 before SQLite opens it; leftover side files become 0600."""
    from docket import store as store_module
    from docket.store import Store

    path = root / "docket.sqlite3"
    seen: list[object] = []
    connect = sqlite3.connect

    def watched(*args: object, **kwargs: object) -> sqlite3.Connection:
        seen.append(mode(path) if path.exists() else "missing")
        return connect(*args, **kwargs)

    previous = os.umask(0o022)
    try:
        with patch.object(store_module.sqlite3, "connect", watched):
            Store(path).close()
    finally:
        os.umask(previous)
    assert seen == [0o600], f"new database mode at connect: expected [0o600], got {seen}"
    with closing(sqlite3.connect(path)) as writer:
        writer.execute("PRAGMA wal_autocheckpoint = 0")
        with writer:
            writer.execute(
                "INSERT INTO tasks (title, state, source, created_at, updated_at) "
                "VALUES ('Synthetic WAL task', 'open', 'owner', ?, ?)",
                ("2026-11-17T14:00:00.000000+00:00",) * 2,
            )
        sides = [root / "docket.sqlite3-wal", root / "docket.sqlite3-shm"]
        for side in sides:
            side.chmod(0o644)
        with Store(path):
            found = [oct(mode(side)) for side in sides]
    assert found == ["0o600", "0o600"], f"leftover -wal, -shm modes: {found}"
    gitignore = (Path(__file__).resolve().parents[2] / ".gitignore").read_text().splitlines()
    missing = [
        p for p in ("*.sqlite3-wal", "*.sqlite3-shm", "*.startup.lock") if p not in gitignore
    ]
    assert not missing, f".gitignore lacks {missing}"


def leaf(error: BaseException) -> BaseException:
    while isinstance(error, BaseExceptionGroup):
        error = error.exceptions[0]
    return error


def main() -> None:
    oracle()
    print("decoding oracle ok")
    if "--oracle-only" in sys.argv:
        print("FAILURES 0")
        return
    failures = 0
    rows = "each bad row refused with its constant message, each good row decoded"
    checks = (
        ("forced bad rows", forced, rows),
        ("random rows", walks, rows),
        ("file modes", files, "the database and its side files private, the side files ignored"),
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
