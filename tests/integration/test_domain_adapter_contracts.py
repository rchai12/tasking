import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest

from docket import core, web
from docket.config import (
    DATA_DIR_MESSAGE,
    TIME_ZONE_MESSAGE,
    WEB_PORT_MESSAGE,
    WORK_MINUTES_MESSAGE,
    get_settings,
)
from docket.deadlines import WORK_LENGTH_MESSAGE, DeadlineError, WorkTime
from docket.intake import accept_task
from docket.store import Store, open_store
from tests.http_cases import Exchange, Opened
from tests.support import fixed_times, run

NOW = "2026-11-17T14:00:00+00:00"
MARKER = "PRIVATE_SYNTHETIC"


def test_a_non_string_zone_is_an_invalid_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_times(monkeypatch)
    with Store(tmp_path / "docket.sqlite3") as store:
        answer = accept_task(
            store,
            client="email",
            key="synthetic",
            body={
                "source": "email",
                "title": "Synthetic task",
                "deadline": {"date": "2026-11-20", "time": None, "time_zone": 1},
                "provider": "gmail",
                "message_id": "synthetic/1",
                "link": "https://mail.example/1",
            },
        )
        assert (answer.status, answer.body) == (422, {"error": "invalid_deadline"})
        assert store.tasks() == []
        assert store.request_key("email", "synthetic") is None


def test_bounds_stay_at_title_key_and_work(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixed_times(monkeypatch, NOW, NOW)
    path = tmp_path / "docket.sqlite3"
    with Store(path) as store:
        made = core.create_task(store, title="x" * 100, source="owner")
        assert made.title == "x" * 100
        keyed = core.create_task_once(
            store,
            client="agent",
            key="k" * 200,
            request={"source": "agent"},
            title="Synthetic keyed task",
            source="agent",
        )
        assert keyed.changed is True
        fixed_times(monkeypatch)
        with pytest.raises(core.CoreError, match="^invalid_title$"):
            core.create_task(store, title="x" * 101, source="owner")
        with pytest.raises(core.CoreError, match="^invalid_key$"):
            core.create_task_once(
                store,
                client="agent",
                key="k" * 201,
                request={"source": "agent"},
                title=" ",
                source="camera",
            )
        assert [task.id for task in store.tasks()] == [made.id, keyed.task.id]
        assert store.request_key("agent", "k" * 201) is None
    start = datetime(2026, 11, 20, 17, tzinfo=UTC)
    assert WorkTime(start, 5, "UTC").minutes == 5
    assert WorkTime(start, 720, "UTC").minutes == 720
    for minutes in (4, 721):
        with pytest.raises(DeadlineError, match=f"^{WORK_LENGTH_MESSAGE}$"):
            WorkTime(start, minutes, "UTC")


def test_http_refuses_an_overlong_key_before_json_or_a_store(tmp_path: Path) -> None:
    opened = Opened(tmp_path / "docket.sqlite3")
    app = web.create_app(open_store=opened, tokens={"synthetic-token": "email"}, port=8767)
    exchange = Exchange(
        app,
        [b"{"],
        headers={"authorization": "Bearer synthetic-token", "idempotency-key": "k" * 201},
    )
    status, body, headers = asyncio.run(exchange.run())
    assert (status, body) == (400, {"error": "missing_key"})
    assert headers["cache-control"] == "no-store"
    assert exchange.reads == 1
    assert opened.opens == []
    assert not opened.path.exists()


@pytest.mark.parametrize(
    ("key", "client", "body", "error"),
    [
        ("", "agent", None, "missing_key"),
        ("synthetic", "agent", None, "invalid_client"),
        ("synthetic", "email", {"title": "Synthetic task"}, "invalid_body"),
    ],
    ids=["key", "client", "body"],
)
def test_intake_keeps_key_client_and_body_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, key: str, client: str, body: object, error: str
) -> None:
    fixed_times(monkeypatch)
    with Store(tmp_path / "docket.sqlite3") as store:
        answer = accept_task(store, client=client, key=key, body=body)
        assert (answer.status, answer.body) == (
            400 if error == "missing_key" else 422,
            {"error": error},
        )
        assert store.tasks() == []
        assert store.request_key("email", "synthetic") is None


def test_open_states_labels_and_actors_come_from_the_shared_domain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DOCKET_TIME_ZONE", "UTC")
    fixed_times(monkeypatch, NOW, NOW, NOW, NOW, NOW, NOW, NOW, NOW, NOW)
    with open_store(get_settings()) as store:
        core.create_task(store, title="Synthetic open task", source="owner")
        core.create_task(store, title="Synthetic active task", source="agent")
        core.create_task(store, title="Synthetic done task", source="proposal")
        core.create_task(
            store,
            title="Synthetic email task",
            source="email",
            provider="gmail",
            message_id="synthetic/1",
            link="https://mail.example/1",
        )
        core.change_state(store, "t2", "start", actor="owner")
        core.change_state(store, "t3", "done", actor="owner")
        core.change_state(store, "t4", "cancel", actor="email")
        assert [store.audit(task_id)[0].actor for task_id in ("t1", "t2", "t3", "t4")] == [
            "owner",
            "agent",
            "owner",
            "email",
        ]
    listed = run("tasks", "list")
    assert listed.exit_code == 0
    assert "t1" in listed.stdout and "t2" in listed.stdout
    assert "in progress" in listed.stdout
    assert "t3" not in listed.stdout and "t4" not in listed.stdout
    everything = run("tasks", "list", "--all")
    assert all(task_id in everything.stdout for task_id in ("t1", "t2", "t3", "t4"))
    assert "cancelled" in everything.stdout


def test_cli_keeps_date_only_and_maximum_work_after_the_time_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DOCKET_TIME_ZONE", "America/New_York")
    fixed_times(monkeypatch, NOW, NOW)
    added = run("tasks", "add", "Synthetic DST task", "--due", "2026-11-21")
    assert (added.exit_code, added.stderr) == (0, "")
    assert added.stdout == (
        "Added t1: Synthetic DST task, due Sat Nov 21 17:00 EST, no time given\n"
    )
    planned = run("tasks", "plan", "t1", "2026-11-20", "12:00", "--minutes", "720")
    assert (planned.exit_code, planned.stderr) == (0, "")
    assert planned.stdout == "Planned t1: Fri Nov 20 12:00 EST to Sat Nov 21 00:00 EST\n"
    with open_store(get_settings()) as store:
        task = store.task("t1")
        assert task is not None and task.deadline is not None and task.work is not None
        assert (task.deadline.at, task.deadline.time_given, task.deadline.zone) == (
            datetime(2026, 11, 21, 22, tzinfo=UTC),
            False,
            "America/New_York",
        )
        assert (task.work.start, task.work.minutes, task.work.zone) == (
            datetime(2026, 11, 20, 17, tzinfo=UTC),
            720,
            "America/New_York",
        )


def test_real_settings_keep_field_priority_and_hide_markers(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("DOCKET_DATA_DIR", "relative")
    monkeypatch.setenv("DOCKET_TIME_ZONE", MARKER)
    monkeypatch.setenv("DOCKET_WORK_MINUTES", "4")
    monkeypatch.setenv("DOCKET_WEB_PORT", "80")
    with pytest.raises(Exception, match=f"^{DATA_DIR_MESSAGE}$") as first:
        get_settings()
    assert type(first.value).__name__ == "ConfigError"
    assert MARKER not in str(first.value)
    monkeypatch.setenv("DOCKET_DATA_DIR", "/tmp/synthetic-docket")
    with pytest.raises(Exception, match=f"^{TIME_ZONE_MESSAGE}$") as second:
        get_settings()
    assert MARKER not in str(second.value)
    monkeypatch.setenv("DOCKET_TIME_ZONE", "UTC")
    with pytest.raises(Exception, match=f"^{WORK_MINUTES_MESSAGE}$"):
        get_settings()
    monkeypatch.setenv("DOCKET_WORK_MINUTES", "60")
    with pytest.raises(Exception, match=f"^{WEB_PORT_MESSAGE}$"):
        get_settings()
    captured = capsys.readouterr()
    assert (captured.out, captured.err) == ("", "")
    assert MARKER not in captured.out and MARKER not in captured.err
