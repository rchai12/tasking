"""Phase 6c: core refuses a deadline or work time that is not a Deadline, WorkTime or None."""

import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import pytest

from docket import core
from docket.core import create_task, create_task_once, edit_task
from docket.deadlines import Deadline, WorkTime
from docket.store import UNCHANGED, Store
from tests.support import fixed_times
from tests.support import path as path
from tests.support import refused as refused
from tests.support import store as store

NY = "America/New_York"
NOW = "2026-11-14T14:00:00+00:00"
FRIDAY_5PM = Deadline(datetime(2026, 11, 20, 22, 0, tzinfo=UTC), NY, True)
FRIDAY_WORK = WorkTime(datetime(2026, 11, 20, 19, 0, tzinfo=UTC), 60, NY)
REQUEST = {"source": "agent", "title": "Pay rent", "deadline": None}

BAD_DEADLINES = [
    "2026-11-20",
    {"date": "2026-11-20", "time": "17:00", "time_zone": NY},
    1795219200,
    1.5,
    True,
    ["2026-11-20", "17:00"],
    FRIDAY_WORK,
]
BAD_DEADLINE_IDS = ["string", "dict", "int", "float", "bool", "list", "work-time"]
BAD_WORK = [
    "2026-11-20T19:00:00Z",
    {"start": "2026-11-20T19:00:00Z", "minutes": 60, "time_zone": NY},
    60,
    False,
    FRIDAY_5PM,
]
BAD_WORK_IDS = ["string", "dict", "int", "bool", "deadline"]
FIELDS = [("deadline", value, "invalid_deadline") for value in [*BAD_DEADLINES, UNCHANGED]] + [
    ("work", value, "invalid_work") for value in [*BAD_WORK, UNCHANGED]
]
FIELD_IDS = [f"deadline-{name}" for name in [*BAD_DEADLINE_IDS, "unchanged"]] + [
    f"work-{name}" for name in [*BAD_WORK_IDS, "unchanged"]
]


def dump(path: Path) -> list[str]:
    with closing(sqlite3.connect(path)) as connection:
        return list(connection.iterdump())


def seeded(store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    fixed_times(monkeypatch, NOW)
    create_task(store, title="Pay rent", source="owner", deadline=FRIDAY_5PM, work=FRIDAY_WORK)
    fixed_times(monkeypatch)


@pytest.mark.xfail(
    strict=True, reason="Phase 6c given test: remove this marker when core checks value types"
)
def test_the_new_codes() -> None:
    assert (core.INVALID_DEADLINE, core.INVALID_WORK) == ("invalid_deadline", "invalid_work")


@pytest.mark.xfail(
    strict=True, reason="Phase 6c given test: remove this marker when core checks value types"
)
@pytest.mark.parametrize("value", BAD_DEADLINES, ids=BAD_DEADLINE_IDS)
def test_edit_task_refuses_a_deadline_that_is_not_one(
    store: Store, path: Path, monkeypatch: pytest.MonkeyPatch, value: object
) -> None:
    seeded(store, monkeypatch)
    before = dump(path)
    refused("invalid_deadline", lambda: edit_task(store, "t1", actor="agent", deadline=value))
    assert dump(path) == before


@pytest.mark.xfail(
    strict=True, reason="Phase 6c given test: remove this marker when core checks value types"
)
@pytest.mark.parametrize("value", BAD_WORK, ids=BAD_WORK_IDS)
def test_edit_task_refuses_a_work_time_that_is_not_one(
    store: Store, path: Path, monkeypatch: pytest.MonkeyPatch, value: object
) -> None:
    seeded(store, monkeypatch)
    before = dump(path)
    refused("invalid_work", lambda: edit_task(store, "t1", actor="agent", work=value))
    assert dump(path) == before


@pytest.mark.xfail(
    strict=True, reason="Phase 6c given test: remove this marker when core checks value types"
)
def test_edit_task_checks_the_deadline_before_the_work_time(
    store: Store, path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seeded(store, monkeypatch)
    before = dump(path)
    refused(
        "invalid_deadline",
        lambda: edit_task(store, "t1", actor="agent", deadline="2026-11-20", work=60),
    )
    refused(
        "invalid_title",
        lambda: edit_task(store, "t1", actor="agent", title="", deadline="2026-11-20"),
    )
    assert dump(path) == before


@pytest.mark.xfail(
    strict=True, reason="Phase 6c given test: remove this marker when core checks value types"
)
@pytest.mark.parametrize(("field", "value", "code"), FIELDS, ids=FIELD_IDS)
def test_create_task_refuses_a_value_that_is_not_one(
    store: Store, path: Path, monkeypatch: pytest.MonkeyPatch, field: str, value: object, code: str
) -> None:
    fixed_times(monkeypatch)
    before = dump(path)
    refused(
        code,
        lambda: create_task(store, title="Pay rent", source="owner", **{field: value}),  # type: ignore[arg-type]
    )
    assert dump(path) == before


@pytest.mark.xfail(
    strict=True, reason="Phase 6c given test: remove this marker when core checks value types"
)
@pytest.mark.parametrize(("field", "value", "code"), FIELDS, ids=FIELD_IDS)
def test_create_task_once_refuses_a_value_and_keeps_the_key_free(
    store: Store, path: Path, monkeypatch: pytest.MonkeyPatch, field: str, value: object, code: str
) -> None:
    fixed_times(monkeypatch, NOW)
    before = dump(path)
    values: dict[str, object] = {
        "client": "agent",
        "key": "conductor:1",
        "request": REQUEST,
        "title": "Pay rent",
        "source": "agent",
    }
    refused(code, lambda: create_task_once(store, **values, **{field: value}))  # type: ignore[arg-type]
    assert dump(path) == before
    outcome = create_task_once(store, **values)  # type: ignore[arg-type]
    assert (outcome.task.id, outcome.changed) == ("t1", True)


@pytest.mark.xfail(
    strict=True, reason="Phase 6c given test: remove this marker when core checks value types"
)
def test_the_create_paths_check_the_deadline_before_the_work_time(
    store: Store, path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_times(monkeypatch)
    before = dump(path)
    refused(
        "invalid_deadline",
        lambda: create_task(store, title="Pay rent", source="owner", deadline=1, work=1),  # type: ignore[arg-type]
    )
    refused(
        "invalid_deadline",
        lambda: create_task_once(
            store,
            client="agent",
            key="conductor:1",
            request=REQUEST,
            title="Pay rent",
            source="agent",
            deadline=1,  # type: ignore[arg-type]
            work=1,  # type: ignore[arg-type]
        ),
    )
    assert dump(path) == before


def test_earlier_checks_still_come_first(store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    fixed_times(monkeypatch)
    refused(
        "invalid_title",
        lambda: create_task(store, title="", source="owner", deadline="2026-11-20"),  # type: ignore[arg-type]
    )
    refused(
        "invalid_source",
        lambda: create_task(store, title="Pay rent", source="nobody", work=60),  # type: ignore[arg-type]
    )
    refused(
        "invalid_key",
        lambda: create_task_once(
            store,
            client="agent",
            key="",
            request=REQUEST,
            title="Pay rent",
            source="agent",
            deadline="2026-11-20",  # type: ignore[arg-type]
        ),
    )
    refused(
        "invalid_actor",
        lambda: edit_task(store, "t1", actor="nobody", deadline="2026-11-20"),
    )


def test_real_values_and_none_are_still_accepted(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_times(monkeypatch, NOW, NOW, NOW)
    task = create_task(store, title="Pay rent", source="owner", deadline=FRIDAY_5PM, work=None)
    assert (task.deadline, task.work) == (FRIDAY_5PM, None)
    outcome = edit_task(store, "t1", actor="owner", deadline=None, work=None)
    assert (outcome.task.deadline, outcome.task.work, outcome.changed) == (None, None, True)
    outcome = edit_task(store, "t1", actor="owner", deadline=FRIDAY_5PM, work=FRIDAY_WORK)
    assert (outcome.task.deadline, outcome.task.work) == (FRIDAY_5PM, FRIDAY_WORK)
