"""Synthetic process entry points for store-startup tests and the probe."""

import sqlite3
from multiprocessing.connection import Connection
from multiprocessing.queues import Queue
from multiprocessing.synchronize import Event
from pathlib import Path

from docket.schema import MIGRATION_1
from docket.store import Store
from tests.reference_cases import STAMP, version_two


def prepare(path: Path, version: int) -> None:
    if version == 0:
        return
    if version == 2:
        version_two(path)
        return
    if version == 3:
        with Store(path):
            pass
        return
    assert version == 1
    db = sqlite3.connect(path, isolation_level=None)
    try:
        db.executescript(MIGRATION_1)
        db.execute(
            "INSERT INTO tasks(title,state,source,created_at,updated_at) "
            "VALUES ('Synthetic old task','open','owner',?,?)",
            (STAMP, STAMP),
        )
        db.execute("PRAGMA user_version = 1")
    finally:
        db.close()


def open_child(path: str, start: Event, messages: Queue) -> None:
    messages.put(("ready",))
    try:
        assert start.wait(10), "start signal missing"
        with Store(Path(path)) as store:
            tasks = [task.id for task in store.tasks()]
            links = [link.id for link in store.links("t1")]
        with sqlite3.connect(path) as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            problems = db.execute("PRAGMA foreign_key_check").fetchall()
        messages.put(("ok", tasks, links, version, problems))
    except BaseException as error:
        messages.put(("error", type(error).__name__))


def held_gate(path: str, ready: Connection) -> None:
    import fcntl

    lock = Path(path).with_name(Path(path).name + ".startup.lock")
    with lock.open("a+b") as handle:
        lock.chmod(0o600)
        fcntl.flock(handle, fcntl.LOCK_EX)
        ready.send(True)
        # The parent terminates this process; the OS must release its descriptor lock.
        ready.recv()
