"""Phase 6a: more tool behaviour through the in-memory client."""

from datetime import UTC, datetime

import pytest

from docket import clock, config
from docket.deadlines import Deadline, WorkTime
from docket.store import open_store
from tests.mcp_cases import HOME, NOW, Clock, add, call, server


@pytest.fixture(autouse=True)
def home(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCKET_TIME_ZONE", HOME)
    monkeypatch.setattr(clock, "now", Clock(NOW).now)


def test_a_deadline_in_another_zone_is_due_by_the_home_date() -> None:
    from docket import core

    deadline = Deadline(datetime(2026, 11, 21, 4, 30, tzinfo=UTC), "Europe/London", True)
    with open_store(config.get_settings()) as store:
        core.create_task(store, title="Synthetic", source="owner", deadline=deadline, work=None)
    result = call(server(), "list_tasks", {"status": "due"})
    (task,) = result.structured_content["tasks"]
    assert task["deadline"] == {
        "at": "2026-11-21T04:30:00+00:00",
        "date": "2026-11-21",
        "time": "04:30",
        "time_zone": "Europe/London",
    }


def test_a_work_time_without_a_deadline() -> None:
    work = WorkTime(datetime(2026, 11, 20, 19, tzinfo=UTC), 45, HOME)
    with open_store(config.get_settings()) as store:
        add(store, "Synthetic work", work=work)
    result = call(server(), "get_task", {"id": "t1"})
    assert result.structured_content["deadline"] is None
    assert result.structured_content["work"] == {
        "start": "2026-11-20T19:00:00+00:00",
        "minutes": 45,
        "time_zone": HOME,
    }
