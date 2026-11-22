import dataclasses
import inspect
import threading
from datetime import UTC, datetime, timedelta

import pytest

from docket import clock, config, core, ids, reminders
from docket.deadlines import Deadline
from docket.store import Store
from tests.loop_cases import AT, T0, ZONE, Ticker, text
from tests.notifier_cases import FakeNotifier, Killed, SyntheticBug


def due(minutes: float) -> Deadline:
    return Deadline(T0 + timedelta(minutes=minutes), "UTC", True)


def no_settings() -> None:
    raise AssertionError("the loop read the settings")


def counter(monkeypatch, ticker: Ticker) -> None:
    keys = iter(f"k{n}" for n in range(1, 100))
    monkeypatch.setattr(clock, "now", ticker.now)
    monkeypatch.setattr(ids, "new_id", lambda: next(keys))


def loop(opened: Store, notifier, ticker) -> int:
    return reminders.run_loop(opened, notifier, zone=ZONE, at=AT, stop=ticker)


def one_pass(opened: Store, notifier):
    return reminders.run_pass(opened, notifier, zone=ZONE, at=AT)


class DigestBug(FakeNotifier):
    """Delivers notices; every digest raises an unexpected error."""

    def send_digest(self, digest) -> None:
        self.attempts.append(digest)
        raise SyntheticBug()


def test_the_loop_names_and_result_contract() -> None:
    assert reminders.LOOP_SECONDS == 30
    assert list(inspect.signature(reminders.run_loop).parameters) == [
        "store",
        "notifier",
        "zone",
        "at",
        "stop",
    ]
    assert list(inspect.signature(reminders.run_pass).parameters) == [
        "store",
        "notifier",
        "zone",
        "at",
    ]
    # Phase 5e adds `skipped` after these; `test_isolated_passes.py` pins the whole list.
    assert [field.name for field in dataclasses.fields(reminders.PassResult)][:3] == [
        "sent",
        "digest",
        "failed",
    ]
    assert reminders.PassResult(1, False, ()) == reminders.PassResult(1, False, ())


def test_the_loop_waits_thirty_seconds_after_each_pass_until_stopped(tmp_path, monkeypatch) -> None:
    ticker = Ticker(3)
    counter(monkeypatch, ticker)
    monkeypatch.setattr(config, "get_settings", no_settings)
    notifier = FakeNotifier()
    with Store(tmp_path / "docket.sqlite3") as opened:
        assert loop(opened, notifier, ticker) == 3
    assert ticker.waits == [30, 30, 30]
    assert ticker.reads == 6
    assert ticker.moment == datetime(2026, 11, 20, 16, 1, 30, tzinfo=UTC)
    assert notifier.attempts == []


@pytest.mark.parametrize(
    "make_stop",
    [lambda: Ticker(0), lambda: _set_event()],
    ids=["ticker-already-set", "threading-event-already-set"],
)
def test_a_loop_already_stopped_runs_no_pass(tmp_path, monkeypatch, make_stop) -> None:
    ticker = Ticker(0)
    counter(monkeypatch, ticker)
    notifier = FakeNotifier()
    with Store(tmp_path / "docket.sqlite3") as opened:
        core.create_task(opened, title="Synthetic soon", source="owner", deadline=due(1))
        assert loop(opened, notifier, make_stop()) == 0
    assert ticker.reads == 1
    assert notifier.attempts == []


def _set_event() -> threading.Event:
    event = threading.Event()
    event.set()
    return event


def test_a_pass_sends_due_reminders_then_the_digest_and_says_what_it_sent(
    tmp_path, monkeypatch
) -> None:
    ticker = Ticker(0)
    counter(monkeypatch, ticker)
    notifier = FakeNotifier()
    with Store(tmp_path / "docket.sqlite3") as opened:
        core.create_task(opened, title="Synthetic soon", source="owner", deadline=due(1))
        core.create_task(opened, title="Synthetic overdue", source="owner", deadline=due(-1440))
        assert one_pass(opened, notifier) == reminders.PassResult(2, True, ())
        assert one_pass(opened, notifier) == reminders.PassResult(0, False, ())
    assert [text(sent) for sent in notifier.delivered] == [
        ("k1", "t1", "This is due soon."),
        ("k2", "t2", "This is late."),
        ("k3", "Still open past their deadlines: 1 task."),
    ]
    assert ticker.reads == 6


def bug_first() -> FakeNotifier:
    notifier = FakeNotifier()
    notifier.before = SyntheticBug()
    return notifier


def bug_first_and_after() -> FakeNotifier:
    notifier = bug_first()
    notifier.after = SyntheticBug()
    return notifier


def refuse_three() -> FakeNotifier:
    notifier = FakeNotifier()
    notifier.fail = 3
    return notifier


@pytest.mark.parametrize(
    "make,result,delivered",
    [
        (bug_first, (0, True, ("reminders",)), ["k3"]),
        (DigestBug, (2, False, ("digest",)), ["k1", "k2"]),
        (bug_first_and_after, (0, False, ("reminders", "digest")), ["k3"]),
        (refuse_three, (0, False, ()), []),
    ],
    ids=["reminders-bug", "digest-bug", "both-halves", "refusals-are-not-failures"],
)
def test_each_half_of_a_pass_fails_alone(tmp_path, monkeypatch, make, result, delivered) -> None:
    ticker = Ticker(0)
    counter(monkeypatch, ticker)
    notifier = make()
    with Store(tmp_path / "docket.sqlite3") as opened:
        core.create_task(opened, title="Synthetic soon", source="owner", deadline=due(1))
        core.create_task(opened, title="Synthetic overdue", source="owner", deadline=due(-1440))
        assert one_pass(opened, notifier) == reminders.PassResult(*result)
    assert [sent.key for sent in notifier.delivered] == delivered
    assert ticker.reads == 4


def test_the_loop_keeps_going_after_a_failed_pass_and_resends_after_five_minutes(
    tmp_path, monkeypatch
) -> None:
    ticker = Ticker(12)
    counter(monkeypatch, ticker)
    notifier = FakeNotifier()
    notifier.before = SyntheticBug()
    with Store(tmp_path / "docket.sqlite3") as opened:
        core.create_task(opened, title="Synthetic report", source="owner", deadline=due(1))
        assert loop(opened, notifier, ticker) == 12
    assert [text(sent) for sent in notifier.delivered] == [
        ("k2", "t1", "This is now due."),
        ("k1", "t1", "This is due soon."),
    ]
    assert [sent.key for sent in notifier.attempts] == ["k1", "k2", "k1"]
    assert ticker.waits == [30] * 12


def test_a_crash_is_not_caught_by_the_loop(tmp_path, monkeypatch) -> None:
    ticker = Ticker(3)
    counter(monkeypatch, ticker)
    notifier = FakeNotifier()
    notifier.before = Killed()
    with Store(tmp_path / "docket.sqlite3") as opened:
        core.create_task(opened, title="Synthetic report", source="owner", deadline=due(1))
        with pytest.raises(Killed):
            loop(opened, notifier, ticker)
    assert ticker.waits == []
    assert ticker.reads == 2
    assert [sent.key for sent in notifier.attempts] == ["k1"]
