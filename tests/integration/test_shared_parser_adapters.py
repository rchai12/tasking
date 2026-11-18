from datetime import UTC, datetime
from pathlib import Path

import pytest

from docket import parsing
from docket.intake import accept_task
from docket.store import Store
from tests.support import fixed_times, run

BODY = {
    "source": "email",
    "title": "Synthetic task",
    "deadline": None,
    "provider": "gmail",
    "message_id": "synthetic/1",
    "link": "https://mail.example/1",
}


@pytest.mark.parametrize(
    ("day", "at", "instant", "given"),
    [
        ("2026-11-01", "01:30", datetime(2026, 11, 1, 5, 30, tzinfo=UTC), True),
        ("2027-03-14", "02:30", datetime(2027, 3, 14, 7, 30, tzinfo=UTC), True),
        ("2026-11-01", None, datetime(2026, 11, 1, 22, tzinfo=UTC), False),
        ("2027-03-14", None, datetime(2027, 3, 14, 21, tzinfo=UTC), False),
    ],
    ids=["fall-first", "spring-forward", "fall-date-only", "spring-date-only"],
)
def test_intake_preserves_dst_and_optional_time(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    day: str,
    at: str | None,
    instant: datetime,
    given: bool,
) -> None:
    fixed_times(monkeypatch, "2026-11-17T14:00:00+00:00")
    with Store(tmp_path / "docket.sqlite3") as store:
        answer = accept_task(
            store,
            client="email",
            key="synthetic",
            body={**BODY, "deadline": {"date": day, "time": at, "time_zone": "America/New_York"}},
        )
        assert (answer.status, answer.body) == (201, {"id": "t1"})
        task = store.task("t1")
        assert task is not None and task.deadline is not None
        assert (task.deadline.at, task.deadline.zone, task.deadline.time_given) == (
            instant,
            "America/New_York",
            given,
        )


@pytest.mark.parametrize(
    ("day", "at"),
    [
        ("20261120", "17:00"),
        ("2026-11-31", "17:00"),
        ("2026-11-20", "1700"),
        ("2026-11-20", "24:00"),
    ],
    ids=["date-shape", "date-value", "time-shape", "time-value"],
)
def test_intake_keeps_deadline_refusal_and_no_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, day: str, at: str
) -> None:
    fixed_times(monkeypatch)
    with Store(tmp_path / "docket.sqlite3") as store:
        answer = accept_task(
            store,
            client="email",
            key="synthetic",
            body={**BODY, "title": "", "deadline": {"date": day, "time": at, "time_zone": "UTC"}},
        )
        assert (answer.status, answer.body) == (422, {"error": "invalid_deadline"})
        assert store.tasks() == []
        assert store.request_key("email", "synthetic") is None


@pytest.mark.parametrize("route", ["intake", "add", "edit", "plan"])
def test_all_adapters_call_the_shared_parsers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, route: str
) -> None:
    calls = []
    read_date, read_time = parsing.parse_date, parsing.parse_time

    def day(value):
        calls.append(("date", value))
        return read_date(value)

    def at(value):
        calls.append(("time", value))
        return read_time(value)

    monkeypatch.setattr(parsing, "parse_date", day)
    monkeypatch.setattr(parsing, "parse_time", at)
    monkeypatch.setenv("DOCKET_TIME_ZONE", "UTC")
    fixed_times(monkeypatch, "2026-11-17T14:00:00+00:00", "2026-11-17T14:00:00+00:00")
    if route == "intake":
        with Store(tmp_path / "docket.sqlite3") as store:
            answer = accept_task(
                store,
                client="email",
                key="synthetic",
                body={
                    **BODY,
                    "deadline": {"date": "2026-11-20", "time": "17:00", "time_zone": "UTC"},
                },
            )
            assert answer.status == 201
    else:
        if route in {"edit", "plan"}:
            assert run("tasks", "add", "Synthetic task").exit_code == 0
        if route == "plan":
            result = run("tasks", "plan", "t1", "2026-11-20", "17:00")
        else:
            args = ["tasks", route, "Synthetic task" if route == "add" else "t1"]
            result = run(*args, "--due", "2026-11-20", "--at", "17:00")
        assert result.exit_code == 0, result.output
    assert calls == [("date", "2026-11-20"), ("time", "17:00")]
