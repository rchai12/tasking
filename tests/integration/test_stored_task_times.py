import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from docket import core
from docket.deadlines import Deadline, WorkTime
from docket.store import Store, StoreError
from tests.reference_cases import NOW, snapshot
from tests.support import fixed_times

NY = "America/New_York"
DUE = Deadline(datetime(2026, 11, 20, 22, tzinfo=UTC), NY, False)
WORK = WorkTime(datetime(2026, 11, 20, 19, tzinfo=UTC), 60, NY)
BAD = [
    ("deadline_at", "private-invalid-instant"),
    ("deadline_at", "2026-11-20T22:00:00"),
    ("deadline_at", "2026-11-20T17:00:00-05:00"),
    ("deadline_zone", "private-invalid-zone"),
    ("deadline_zone", "america/new_york"),
    ("work_start", "private-invalid-instant"),
    ("work_start", "2026-11-20T19:00:00"),
    ("work_start", "2026-11-20T14:00:00-05:00"),
    ("work_zone", "private-invalid-zone"),
    ("work_zone", "america/new_york"),
    ("created_at", "private-invalid-instant"),
    ("created_at", "2026-11-17T14:00:00"),
    ("created_at", "2026-11-17T09:00:00-05:00"),
    ("updated_at", "private-invalid-instant"),
    ("updated_at", "2026-11-17T14:00:00"),
    ("updated_at", "2026-11-17T09:00:00-05:00"),
]
BAD_IDS = [
    "deadline-text",
    "deadline-naive",
    "deadline-offset",
    "deadline-zone",
    "deadline-case",
    "work-text",
    "work-naive",
    "work-offset",
    "work-zone",
    "work-case",
    "created-text",
    "created-naive",
    "created-offset",
    "updated-text",
    "updated-naive",
    "updated-offset",
]


@pytest.fixture
def opened(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[Store, Path]]:
    path = tmp_path / "docket.sqlite3"
    fixed_times(monkeypatch, NOW)
    with Store(path) as store:
        core.create_task(
            store, title="Synthetic stored task", source="owner", deadline=DUE, work=WORK
        )
        fixed_times(monkeypatch)
        yield store, path


@pytest.mark.parametrize("reader", ["task", "tasks", "filtered"])
@pytest.mark.parametrize(("field", "value"), BAD, ids=BAD_IDS)
def test_invalid_task_times_refuse_at_the_store_boundary(
    opened: tuple[Store, Path], reader: str, field: str, value: str
) -> None:
    store, path = opened
    with sqlite3.connect(path) as db:
        db.execute(f"UPDATE tasks SET {field}=? WHERE number=1", (value,))
    before = snapshot(path)
    with pytest.raises(StoreError) as raised:
        if reader == "task":
            store.task("t1")
        elif reader == "tasks":
            store.tasks()
        else:
            store.tasks({"open"})
    assert str(raised.value) == "invalid stored task time: t1"
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None or raised.value.__suppress_context__
    assert snapshot(path) == before


@pytest.mark.parametrize(
    ("deadline", "work"),
    [
        (None, None),
        (DUE, WORK),
        (
            Deadline(datetime(2026, 11, 1, 5, 30, tzinfo=UTC), NY, True),
            WorkTime(datetime(2026, 11, 1, 4, 30, tzinfo=UTC), 60, NY),
        ),
        (
            Deadline(datetime(2027, 3, 14, 7, 30, tzinfo=UTC), NY, True),
            WorkTime(datetime(2027, 3, 14, 6, 30, tzinfo=UTC), 60, NY),
        ),
    ],
    ids=["undated", "date-only", "fall-back", "spring-forward"],
)
def test_valid_task_times_round_trip_without_changing_instants(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    deadline: Deadline | None,
    work: WorkTime | None,
) -> None:
    fixed_times(monkeypatch, NOW)
    path = tmp_path / "docket.sqlite3"
    with Store(path) as store:
        core.create_task(
            store, title="Synthetic stored task", source="owner", deadline=deadline, work=work
        )
    fixed_times(monkeypatch)
    with Store(path) as store:
        task = store.task("t1")
        assert task is not None
        assert (task.deadline, task.work) == (deadline, work)
        assert task.created_at == datetime(2026, 11, 17, 14, tzinfo=UTC)
        assert task.updated_at == datetime(2026, 11, 17, 14, tzinfo=UTC)
        assert task.created_at.tzinfo is UTC
        assert task.updated_at.tzinfo is UTC
        assert store.tasks() == [task]
        assert len(store.audit("t1")) == 1


def test_no_partial_task_list_or_repair_is_returned(
    opened: tuple[Store, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    store, path = opened
    fixed_times(monkeypatch, NOW)
    core.create_task(store, title="Second synthetic task", source="owner")
    fixed_times(monkeypatch)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE tasks SET created_at='private-invalid-instant' WHERE number=2")
    before = snapshot(path)
    with pytest.raises(StoreError, match="^invalid stored task time: t2$"):
        store.tasks()
    assert store.task("t1") is not None
    assert snapshot(path) == before
