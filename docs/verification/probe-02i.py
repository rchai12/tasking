"""Synthetic process startup, corrupt-task read and failed-constructor properties."""

import multiprocessing
import sqlite3
import stat
import sys
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
FAILURES = 0
CASES = (
    ("deadline_at", "2026-11-20T22:00:00"),
    ("deadline_zone", "america/new_york"),
    ("work_start", "2026-11-20T14:00:00-05:00"),
    ("work_zone", "private-invalid-zone"),
    ("created_at", "private-invalid-time"),
    ("updated_at", "2026-11-17T14:00:00"),
)


def check(label: str, action: Callable[[], None]) -> None:
    global FAILURES
    try:
        action()
    except Exception as error:
        FAILURES += 1
        print(f"{label}: FAIL (observed {type(error).__name__})")
    else:
        print(f"{label}: ok")


def startup() -> None:
    from tests.reference_cases import snapshot, version_two
    from tests.startup_cases import open_child

    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "docket.sqlite3"
        version_two(path)
        before = snapshot(path)
        ctx = multiprocessing.get_context("spawn")
        start = ctx.Event()
        messages = ctx.Queue()
        workers = [
            ctx.Process(target=open_child, args=(str(path), start, messages)) for _ in range(2)
        ]
        try:
            for worker in workers:
                worker.start()
            assert messages.get(timeout=10) == ("ready",)
            assert messages.get(timeout=10) == ("ready",)
            start.set()
            results = [messages.get(timeout=10), messages.get(timeout=10)]
            expected = [("ok", ["t1"], ["l1"], 4, []), ("ok", ["t1"], ["l1"], 4, [])]
            if results != expected:
                print(f"  expected two successful v3 openers; found {results}")
                raise AssertionError
            for worker in workers:
                worker.join(timeout=10)
                assert worker.exitcode == 0
            assert snapshot(path) == before
            lock = path.with_name(path.name + ".startup.lock")
            assert lock.exists(), "persistent startup gate missing"
            assert stat.S_IMODE(lock.stat().st_mode) == 0o600
        finally:
            start.set()
            for worker in workers:
                if worker.is_alive():
                    worker.terminate()
                worker.join(timeout=10)
            messages.close()
            messages.join_thread()


def reads() -> None:
    from docket import core
    from docket.deadlines import Deadline, WorkTime
    from docket.store import Store, StoreError
    from tests.reference_cases import snapshot

    for field, value in CASES:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "docket.sqlite3"
            with patch("docket.clock.now", return_value=datetime(2026, 11, 17, 14, tzinfo=UTC)):
                with Store(path) as store:
                    core.create_task(
                        store,
                        title="Synthetic stored task",
                        source="owner",
                        deadline=Deadline(
                            datetime(2026, 11, 20, 22, tzinfo=UTC), "America/New_York", False
                        ),
                        work=WorkTime(
                            datetime(2026, 11, 20, 19, tzinfo=UTC), 60, "America/New_York"
                        ),
                    )
            with sqlite3.connect(path) as db:
                db.execute(f"UPDATE tasks SET {field}=? WHERE number=1", (value,))
            before = snapshot(path)
            with Store(path) as store:
                try:
                    store.task("t1")
                except StoreError as error:
                    assert str(error) == "invalid stored task time: t1"
                except Exception as error:
                    print(
                        f"  {field}: expected StoreError with task ID; "
                        f"observed {type(error).__name__}"
                    )
                    raise
                else:
                    print(f"  {field}: expected StoreError with task ID; read succeeded")
                    raise AssertionError
            assert snapshot(path) == before


def cleanup() -> None:
    from docket.store import Store

    class InitializationBroke(Exception):
        pass

    closed = []
    connect = sqlite3.connect

    class Tracked(sqlite3.Connection):
        def execute(self, sql, *args, **kwargs):
            if sql.startswith("PRAGMA busy_timeout"):
                raise InitializationBroke
            return super().execute(sql, *args, **kwargs)

        def close(self) -> None:
            closed.append(True)
            super().close()

    with tempfile.TemporaryDirectory() as folder:
        with patch(
            "docket.store.sqlite3.connect", lambda *a, **k: connect(*a, **k, factory=Tracked)
        ):
            try:
                Store(Path(folder) / "docket.sqlite3")
            except InitializationBroke:
                pass
            else:
                raise AssertionError("injected setup failure did not propagate")
        if closed != [True]:
            print(f"  expected one connection close; observed {len(closed)}")
            raise AssertionError


def main() -> int:
    assert len(CASES) == 6
    assert {field for field, _ in CASES} == {
        "deadline_at",
        "deadline_zone",
        "work_start",
        "work_zone",
        "created_at",
        "updated_at",
    }
    print("oracle: ok")
    if "--oracle-only" not in sys.argv:
        check("two processes upgrade once and preserve rows plus private gate", startup)
        check("six invalid time/zone cases refuse with task ID and leave data unchanged", reads)
        check("failed startup closes its SQLite connection once", cleanup)
    print(f"FAILURES {FAILURES}")
    return bool(FAILURES)


if __name__ == "__main__":
    sys.exit(main())
