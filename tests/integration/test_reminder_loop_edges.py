import threading
from datetime import UTC, datetime, time, timedelta

from docket import clock, core, ids, reminders
from docket.deadlines import Deadline
from docket.notifier import Digest, DigestLine, Notice
from docket.store import Store
from tests.loop_cases import T0, Ticker
from tests.notifier_cases import FakeNotifier


def counter(monkeypatch, ticker: Ticker) -> None:
    keys = iter(f"k{n}" for n in range(1, 100))
    monkeypatch.setattr(clock, "now", ticker.now)
    monkeypatch.setattr(ids, "new_id", lambda: next(keys))


def test_an_event_set_during_the_first_pass_ends_the_loop(tmp_path, monkeypatch) -> None:
    ticker = Ticker(5)
    counter(monkeypatch, ticker)
    event = threading.Event()
    notifier = FakeNotifier()
    notifier.during = event.set
    with Store(tmp_path / "docket.sqlite3") as opened:
        core.create_task(
            opened,
            title="Synthetic soon",
            source="owner",
            deadline=Deadline(T0 + timedelta(minutes=1), "UTC", True),
        )
        assert reminders.run_loop(opened, notifier, zone="UTC", at=time(7), stop=event) == 1
    assert event.is_set()
    assert [sent.key for sent in notifier.delivered] == ["k1"]


def test_a_loop_before_seven_sends_the_digest_on_the_next_pass_only(tmp_path, monkeypatch) -> None:
    start = datetime(2026, 11, 20, 6, 59, 30, tzinfo=UTC)
    ticker = Ticker(3, start)
    counter(monkeypatch, ticker)
    notifier = FakeNotifier()
    deadline = Deadline(datetime(2026, 11, 18, 12, tzinfo=UTC), "UTC", True)
    with Store(tmp_path / "docket.sqlite3") as opened:
        core.create_task(opened, title="Synthetic overdue", source="owner", deadline=deadline)
        assert reminders.run_loop(opened, notifier, zone="UTC", at=time(7), stop=ticker) == 3
    assert notifier.delivered == [
        Notice("k1", "t1", "Synthetic overdue", "This is late."),
        Digest(
            "k2",
            "Still open past their deadlines: 1 task.",
            (DigestLine("t1", "Synthetic overdue", "Was due Wed Nov 18 12:00 UTC"),),
        ),
    ]


def test_a_refused_notice_is_delivered_on_the_next_pass_with_the_same_key(
    tmp_path, monkeypatch
) -> None:
    ticker = Ticker(2)
    counter(monkeypatch, ticker)
    notifier = FakeNotifier()
    notifier.fail = 1
    with Store(tmp_path / "docket.sqlite3") as opened:
        core.create_task(
            opened,
            title="Synthetic soon",
            source="owner",
            deadline=Deadline(T0 + timedelta(minutes=1), "UTC", True),
        )
        first = reminders.run_pass(opened, notifier, zone="UTC", at=time(7))
        assert ticker.wait(reminders.LOOP_SECONDS) is False
        second = reminders.run_pass(opened, notifier, zone="UTC", at=time(7))
    assert first == reminders.PassResult(0, False, ())
    assert second == reminders.PassResult(1, False, ())
    assert notifier.delivered == [Notice("k1", "t1", "Synthetic soon", "This is due soon.")]
    assert [sent.key for sent in notifier.attempts] == ["k1", "k1"]
