import dataclasses
import inspect
from datetime import UTC, date, datetime, time, timedelta

import pytest

from docket import config
from docket.deadlines import Deadline
from docket.notifier import Digest, DigestLine, Notifier
from docket.store import Store
from tests.digest_cases import AT, DAY, SLOT, TASKS, ZONE, later, seed
from tests.notifier_cases import FakeNotifier, Killed, SyntheticBug, rows
from tests.support import fixed_ids, fixed_times

FOUR = (
    DigestLine("t2", "Synthetic report", "Was due Tue Nov 17 17:00 EST"),
    DigestLine("t7", "Synthetic tie", "Was due Tue Nov 17 17:00 EST"),
    DigestLine(
        "t1",
        "Synthetic invoice",
        "Was due Wed Nov 18 09:00 EST (Wed Nov 18 23:00 JST where set)",
    ),
    DigestLine("t3", "Synthetic boundary", "Was due Thu Nov 19 19:00 EST"),
)
FIRST = Digest("k1", "Still open past their deadlines: 4 tasks.", FOUR)


def moment(minutes: float) -> datetime:
    return SLOT + timedelta(minutes=minutes)


def send(opened: Store, notifier: FakeNotifier) -> bool:
    from docket import reminders

    return reminders.send_digest(opened, notifier, zone=ZONE, at=AT)


def no_settings() -> None:
    raise AssertionError("the digest read the settings")


def test_the_digest_names_and_notifier_contract() -> None:
    from docket import reminders

    assert list(inspect.signature(reminders.send_digest).parameters) == [
        "store",
        "notifier",
        "zone",
        "at",
    ]
    assert list(inspect.signature(reminders.digest_slot).parameters) == ["now", "zone", "at"]
    assert list(inspect.signature(reminders.digest_heading).parameters) == ["count"]
    assert [field.name for field in dataclasses.fields(Digest)] == ["key", "heading", "lines"]
    assert [field.name for field in dataclasses.fields(DigestLine)] == [
        "task_id",
        "title",
        "text",
    ]
    assert list(inspect.signature(Notifier.send_digest).parameters) == ["self", "digest"]


@pytest.mark.parametrize(
    "count,heading",
    [
        (1, "Still open past their deadlines: 1 task."),
        (2, "Still open past their deadlines: 2 tasks."),
        (25, "Still open past their deadlines: 25 tasks."),
    ],
    ids=["one", "two", "many"],
)
def test_the_heading_counts_the_tasks_it_lists(count, heading) -> None:
    from docket import reminders

    assert reminders.digest_heading(count) == heading


@pytest.mark.parametrize(
    "now,zone,at,day,slot",
    [
        ("2026-10-31T11:00:00+00:00", ZONE, time(7), date(2026, 10, 31), "2026-10-31T11:00:00"),
        ("2026-11-01T12:00:00+00:00", ZONE, time(7), date(2026, 11, 1), "2026-11-01T12:00:00"),
        ("2026-11-01T11:59:00+00:00", ZONE, time(7), date(2026, 11, 1), "2026-11-01T12:00:00"),
        ("2027-03-14T11:00:00+00:00", ZONE, time(7), date(2027, 3, 14), "2027-03-14T11:00:00"),
        ("2027-03-14T12:00:00+00:00", ZONE, time(2, 30), date(2027, 3, 14), "2027-03-14T07:30:00"),
        ("2026-11-01T12:00:00+00:00", ZONE, time(1, 30), date(2026, 11, 1), "2026-11-01T05:30:00"),
        ("2026-11-21T04:00:00+00:00", ZONE, time(7), date(2026, 11, 20), "2026-11-20T12:00:00"),
        ("2026-11-20T06:59:00+00:00", "UTC", time(7), date(2026, 11, 20), "2026-11-20T07:00:00"),
    ],
    ids=[
        "daylight-time",
        "fall-back-day",
        "before-the-slot",
        "spring-forward-day",
        "skipped-hour-moves-forward",
        "repeated-hour-is-the-first",
        "home-day-behind-utc",
        "utc-zone",
    ],
)
def test_the_slot_is_that_home_day_at_the_digest_time(now, zone, at, day, slot) -> None:
    from docket import reminders

    expected = (day, datetime.fromisoformat(slot).replace(tzinfo=UTC))
    assert reminders.digest_slot(datetime.fromisoformat(now), zone, at) == expected


def test_one_digest_a_day_lists_tasks_past_their_last_late_reminder_in_deadline_order(
    tmp_path, monkeypatch
) -> None:
    from docket.store import DailyDigest

    monkeypatch.setattr(config, "get_settings", no_settings)
    fixed_times(monkeypatch, later(-0.0001), later(0), later(0.5), later(24 * 60))
    fixed_ids(monkeypatch, "k1", "k2")
    notifier = FakeNotifier()
    with Store(tmp_path / "docket.sqlite3") as opened:
        seed(opened)
        assert [send(opened, notifier) for _ in range(4)] == [False, True, False, True]
        assert opened.digest(DAY) == DailyDigest(
            "d1", DAY, "k1", ("t1", "t2", "t3", "t7"), SLOT, SLOT, SLOT
        )
        tomorrow = moment(24 * 60)
        assert opened.digest(date(2026, 11, 21)) == DailyDigest(
            "d2", date(2026, 11, 21), "k2", ("t1", "t2", "t3", "t4", "t7"), *[tomorrow] * 3
        )
    late = DigestLine(
        "t4",
        "Synthetic not yet",
        "Was due Thu Nov 19 19:00 EST (Fri Nov 20 00:00 UTC where set)",
    )
    second = Digest("k2", "Still open past their deadlines: 5 tasks.", (*FOUR, late))
    assert notifier.delivered == notifier.attempts == [FIRST, second]


def test_a_morning_with_nothing_overdue_sends_and_stores_nothing(tmp_path, monkeypatch) -> None:
    fixed_times(monkeypatch, later(0), later(8 * 60))
    fixed_ids(monkeypatch)
    notifier = FakeNotifier()
    path = tmp_path / "docket.sqlite3"
    with Store(path) as opened:
        seed(
            opened,
            [task for task in TASKS if task[0] in {"Synthetic finished", "Synthetic future"}],
        )
        assert [send(opened, notifier) for _ in range(2)] == [False, False]
    assert notifier.attempts == []
    assert rows(path, "digests") == rows(path, "digest_tasks") == []


@pytest.mark.parametrize(
    "first,day,listed",
    [
        ("2026-11-20T20:00:00+00:00", date(2026, 11, 20), ["t2", "t7", "t1", "t3"]),
        ("2026-11-21T04:30:00+00:00", date(2026, 11, 20), ["t2", "t7", "t1", "t3"]),
        ("2026-11-23T13:00:00+00:00", date(2026, 11, 23), ["t2", "t7", "t1", "t3", "t4"]),
    ],
    ids=["back-that-afternoon", "back-that-night", "back-days-later"],
)
def test_a_missed_seven_o_clock_goes_out_on_the_first_pass_that_home_day_only(
    tmp_path, monkeypatch, first, day, listed
) -> None:
    fixed_times(monkeypatch, first, first)
    fixed_ids(monkeypatch, "k1")
    notifier = FakeNotifier()
    path = tmp_path / "docket.sqlite3"
    with Store(path) as opened:
        seed(opened)
        assert [send(opened, notifier) for _ in range(2)] == [True, False]
        assert opened.digest(day).sent_at == datetime.fromisoformat(first)
    assert [row[1] for row in rows(path, "digests")] == [day.isoformat()]
    found = [(digest.key, [line.task_id for line in digest.lines]) for digest in notifier.delivered]
    assert found == [("k1", listed)]


def test_a_refused_digest_is_retried_each_pass_with_the_same_key_without_ended_tasks(
    tmp_path, monkeypatch
) -> None:
    fixed_times(monkeypatch, later(0), later(0.5), later(1))
    fixed_ids(monkeypatch, "k1")
    notifier = FakeNotifier()
    notifier.fail = 1
    with Store(tmp_path / "docket.sqlite3") as opened:
        seed(opened)
        assert send(opened, notifier) is False
        assert opened.digest(DAY).claimed_at is None
        with opened.transaction():
            opened.update_task("t2", at=moment(0.2), state="done")
        assert [send(opened, notifier) for _ in range(2)] == [True, False]
        assert opened.digest(DAY).task_ids == ("t1", "t2", "t3", "t7")
    retried = Digest("k1", "Still open past their deadlines: 3 tasks.", FOUR[1:])
    assert notifier.attempts == [FIRST, retried]
    assert notifier.delivered == [retried]


@pytest.mark.parametrize(
    "change",
    [
        {"state": "done"},
        {"state": "cancelled"},
        {"deadline": Deadline(datetime(2026, 11, 30, 22, tzinfo=UTC), ZONE, True)},
        {"deadline": None},
    ],
    ids=["done", "cancelled", "new-deadline", "deadline-removed"],
)
def test_a_digest_with_no_task_still_overdue_is_never_sent(tmp_path, monkeypatch, change) -> None:
    fixed_times(monkeypatch, later(0), later(10), later(20))
    fixed_ids(monkeypatch, "k1")
    notifier = FakeNotifier()
    notifier.fail = 1
    with Store(tmp_path / "docket.sqlite3") as opened:
        seed(opened, TASKS[1:2])
        assert send(opened, notifier) is False
        with opened.transaction():
            opened.update_task("t1", at=moment(1), **change)
        assert [send(opened, notifier) for _ in range(2)] == [False, False]
        stored = opened.digest(DAY)
        assert (stored.key, stored.task_ids, stored.claimed_at, stored.sent_at) == (
            "k1",
            ("t1",),
            None,
            None,
        )
    assert len(notifier.attempts) == 1
    assert notifier.delivered == []


@pytest.mark.parametrize(
    "hook,error,delivered",
    [
        ("before", Killed, []),
        ("after", Killed, ["k1"]),
        ("before", SyntheticBug, []),
    ],
    ids=["before-send", "after-send", "unexpected-error"],
)
def test_a_crash_mid_digest_resends_once_with_the_same_key_after_five_minutes(
    tmp_path, monkeypatch, hook, error, delivered
) -> None:
    fixed_times(monkeypatch, later(0), later(5), later(5.5), later(6))
    fixed_ids(monkeypatch, "k1")
    notifier = FakeNotifier()
    setattr(notifier, hook, error())
    with Store(tmp_path / "docket.sqlite3") as opened:
        seed(opened)
        with pytest.raises(error):
            send(opened, notifier)
        assert [digest.key for digest in notifier.delivered] == delivered
        assert opened.digest(DAY).claimed_at == SLOT
        assert [send(opened, notifier) for _ in range(3)] == [False, True, False]
        assert opened.digest(DAY).sent_at == moment(5.5)
    assert [digest.key for digest in notifier.attempts] == ["k1", "k1"]
    assert notifier.delivered == [FIRST]


def test_a_second_pass_during_a_digest_send_sends_nothing(tmp_path, monkeypatch) -> None:
    path = tmp_path / "docket.sqlite3"
    fixed_times(monkeypatch, later(0), later(0.1))
    fixed_ids(monkeypatch, "k1")
    notifier = FakeNotifier()
    inner: list[bool] = []
    with Store(path) as opened, Store(path) as other:
        seed(opened)
        notifier.during = lambda: inner.append(send(other, notifier))
        assert send(opened, notifier) is True
    assert inner == [False]
    assert notifier.attempts == notifier.delivered == [FIRST]
