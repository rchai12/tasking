"""Stage 3's own test: the reminder engine, run by its loop through the fake notifier."""

from datetime import timedelta

import pytest

from docket import clock, core, ids, reminders
from docket.deadlines import Deadline, WorkTime
from docket.store import Store
from tests.loop_cases import AT, T0, ZONE, Ticker, text
from tests.notifier_cases import FakeNotifier, Killed


def due(minutes: float) -> Deadline:
    return Deadline(T0 + timedelta(minutes=minutes), "UTC", True)


def counter(monkeypatch, ticker: Ticker) -> None:
    keys = iter(f"k{n}" for n in range(1, 100))
    monkeypatch.setattr(clock, "now", ticker.now)
    monkeypatch.setattr(ids, "new_id", lambda: next(keys))


def loop(opened: Store, notifier, ticker) -> int:
    return reminders.run_loop(opened, notifier, zone=ZONE, at=AT, stop=ticker)


THREE = [
    ("k1", "t1", "This is due soon."),
    ("k2", "t2", "This is due soon."),
    ("k3", "t3", "This is due soon."),
    ("k4", "t1", "This is now due."),
    ("k5", "t2", "This is now due."),
    ("k6", "t3", "This is now due."),
]


def test_deadlines_one_two_and_three_minutes_out_fire_in_order(tmp_path, monkeypatch) -> None:
    ticker = Ticker(8)
    counter(monkeypatch, ticker)
    notifier = FakeNotifier()
    with Store(tmp_path / "docket.sqlite3") as opened:
        for minutes in (1, 2, 3):
            core.create_task(
                opened, title=f"Synthetic {minutes}", source="owner", deadline=due(minutes)
            )
        assert loop(opened, notifier, ticker) == 8
    assert [text(sent) for sent in notifier.delivered] == THREE
    assert notifier.attempts == notifier.delivered


def test_a_work_times_start_reminder_fires_once(tmp_path, monkeypatch) -> None:
    ticker = Ticker(10)
    counter(monkeypatch, ticker)
    notifier = FakeNotifier()
    with Store(tmp_path / "docket.sqlite3") as opened:
        core.create_task(
            opened,
            title="Synthetic start",
            source="owner",
            deadline=due(2880),
            work=WorkTime(T0 + timedelta(minutes=1), 30, "UTC"),
        )
        assert loop(opened, notifier, ticker) == 10
    assert [text(sent) for sent in notifier.attempts] == [("k1", "t1", "Time to start.")]


@pytest.mark.parametrize("hook", ["before", "after"], ids=["before-delivery", "after-delivery"])
def test_a_restart_mid_run_loses_nothing_and_sends_one_status_message(
    tmp_path, monkeypatch, hook
) -> None:
    ticker = Ticker(8)
    counter(monkeypatch, ticker)
    notifier = FakeNotifier()
    path = tmp_path / "docket.sqlite3"
    ticker.between[1] = lambda: setattr(notifier, hook, Killed())
    with Store(path) as opened:
        core.create_task(opened, title="Synthetic report", source="owner", deadline=due(1))
        with pytest.raises(Killed):
            loop(opened, notifier, ticker)
    assert ticker.waits == [30, 30]
    ticker.moment = T0 + timedelta(minutes=125)
    ticker.passes = 4
    with Store(path) as reopened:
        assert loop(reopened, notifier, ticker) == 2
    assert [text(sent) for sent in notifier.delivered] == [
        ("k1", "t1", "This is due soon."),
        ("k2", "t1", "This is now due."),
        ("k3", "t1", "Missed while docket was offline: 3 reminders.\nThis is late."),
    ]
    assert [sent.key for sent in notifier.attempts] == ["k1", "k2", "k2", "k3"]


def test_two_loops_never_send_twice(tmp_path, monkeypatch) -> None:
    ticker = Ticker(8)
    counter(monkeypatch, ticker)
    notifier = FakeNotifier()
    path = tmp_path / "docket.sqlite3"
    inner: list = []
    with Store(path) as opened, Store(path) as other:
        for minutes in (1, 2, 3):
            core.create_task(
                opened, title=f"Synthetic {minutes}", source="owner", deadline=due(minutes)
            )
        for index in range(8):
            ticker.between[index] = lambda: inner.append(
                reminders.run_pass(other, notifier, zone=ZONE, at=AT)
            )
        notifier.during = lambda: inner.append(
            reminders.run_pass(other, notifier, zone=ZONE, at=AT)
        )
        assert loop(opened, notifier, ticker) == 8
    assert [text(sent) for sent in notifier.delivered] == THREE
    assert notifier.attempts == notifier.delivered
    assert [result.sent for result in inner] == [0, 0, 1, 0, 1, 0, 1, 0, 0]
    assert all(result.failed == () for result in inner)


def test_done_voids_everything_pending_and_a_second_done_changes_nothing(
    tmp_path, monkeypatch
) -> None:
    ticker = Ticker(4)
    counter(monkeypatch, ticker)
    notifier = FakeNotifier()
    with Store(tmp_path / "docket.sqlite3") as opened:
        core.create_task(opened, title="Synthetic report", source="owner", deadline=due(1))
        ticker.between[0] = lambda: core.change_state(opened, "t1", "done", actor="owner")
        ticker.between[1] = lambda: setattr(ticker, "moment", T0 + timedelta(hours=13))
        assert loop(opened, notifier, ticker) == 4
        assert core.change_state(opened, "t1", "done", actor="owner").changed is False
        ticker.passes = 6
        assert loop(opened, notifier, ticker) == 2
    assert [text(sent) for sent in notifier.attempts] == [("k1", "t1", "This is due soon.")]
