"""Phase 6a: docket.reads called directly."""

from datetime import UTC, datetime

import pytest

from docket import clock, core
from docket.deadlines import Deadline, WorkTime
from docket.reads import STATUSES, ReadRefused, TaskPage, list_tasks, task_record
from docket.store import Store

ZONE = "America/New_York"
NOW = datetime(2026, 11, 20, 15, tzinfo=UTC)


@pytest.fixture
def store(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(clock, "now", lambda: NOW)
    with Store(tmp_path / "reads.sqlite3") as opened:
        yield opened


def test_bad_status_is_refused(store: Store) -> None:
    for status in (None, ["open"]):
        with pytest.raises(ReadRefused) as caught:
            list_tasks(store, status, None, zone=ZONE)
        assert caught.value.code == "invalid_status"


def test_bad_cursor_is_refused(store: Store) -> None:
    with pytest.raises(ReadRefused) as caught:
        list_tasks(store, "open", 1, zone=ZONE)
    assert caught.value.code == "invalid_cursor"


def test_missing_task_id_is_refused(store: Store) -> None:
    with pytest.raises(ReadRefused) as caught:
        task_record(store, None)
    assert caught.value.code == "unknown_task"


def test_refusal_text_is_the_code() -> None:
    assert str(ReadRefused("invalid_cursor")) == "invalid_cursor"


def test_empty_store_gives_empty_pages(store: Store) -> None:
    for status in STATUSES:
        assert list_tasks(store, status, None, zone=ZONE) == TaskPage((), None)


def test_in_progress_task_due_later_today_is_due(store: Store) -> None:
    deadline = Deadline(datetime(2026, 11, 20, 22, tzinfo=UTC), ZONE, True)
    task = core.create_task(store, title="Synthetic", source="owner", deadline=deadline, work=None)
    core.change_state(store, task.id, "start", actor="owner")
    page = list_tasks(store, "due", None, zone=ZONE)
    assert [found.id for found in page.tasks] == [task.id]


def test_work_time_without_deadline_is_never_due_or_overdue(store: Store) -> None:
    work = WorkTime(datetime(2026, 11, 20, 19, tzinfo=UTC), 30, ZONE)
    core.create_task(store, title="Synthetic", source="owner", deadline=None, work=work)
    for status in ("due", "overdue"):
        assert list_tasks(store, status, None, zone=ZONE).tasks == ()
