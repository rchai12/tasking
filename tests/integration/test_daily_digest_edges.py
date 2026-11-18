from datetime import UTC, date, datetime, time

import pytest

from docket.deadlines import make_deadline
from docket.notifier import Digest, DigestLine
from docket.store import Store, StoreError
from tests.digest_cases import AT, DAY, SLOT, TASKS, ZONE, later, seed
from tests.notifier_cases import FakeNotifier
from tests.support import fixed_ids, fixed_times

FIRST_LINES = (
    DigestLine("t2", "Synthetic report", "Was due Tue Nov 17 17:00 EST"),
    DigestLine("t7", "Synthetic tie", "Was due Tue Nov 17 17:00 EST"),
    DigestLine(
        "t1",
        "Synthetic invoice",
        "Was due Wed Nov 18 09:00 EST (Wed Nov 18 23:00 JST where set)",
    ),
    DigestLine("t3", "Synthetic boundary", "Was due Thu Nov 19 19:00 EST"),
)


def test_a_task_overdue_only_after_the_slot_is_left_out_of_the_heading(
    tmp_path, monkeypatch
) -> None:
    from docket import reminders

    fixed_times(monkeypatch, later(120))
    fixed_ids(monkeypatch, "k1")
    notifier = FakeNotifier()
    evening = ("Synthetic evening", "open", make_deadline(date(2026, 11, 19), time(20), ZONE))
    with Store(tmp_path / "docket.sqlite3") as opened:
        seed(opened, (*TASKS, evening))
        assert reminders.send_digest(opened, notifier, zone=ZONE, at=AT) is True
        assert opened.digest(DAY).task_ids == ("t1", "t2", "t3", "t7")
    assert notifier.delivered == [
        Digest("k1", "Still open past their deadlines: 4 tasks.", FIRST_LINES)
    ]


def test_a_task_added_after_the_slot_is_in_the_first_digest_that_day(tmp_path, monkeypatch) -> None:
    from docket import reminders

    nine = datetime(2026, 11, 20, 14, tzinfo=UTC)
    ten = datetime(2026, 11, 20, 15, tzinfo=UTC)
    fixed_times(monkeypatch, ten.isoformat())
    fixed_ids(monkeypatch, "k1")
    notifier = FakeNotifier()
    with Store(tmp_path / "docket.sqlite3") as opened:
        with opened.transaction():
            opened.insert_task(
                title="Synthetic added",
                state="open",
                deadline=make_deadline(date(2026, 11, 18), time(9), ZONE),
                work=None,
                source="owner",
                provider=None,
                message_id=None,
                link=None,
                at=nine,
            )
        assert reminders.send_digest(opened, notifier, zone=ZONE, at=AT) is True
        assert opened.digest(DAY).queued_at == ten
    assert notifier.delivered == [
        Digest(
            "k1",
            "Still open past their deadlines: 1 task.",
            (DigestLine("t1", "Synthetic added", "Was due Wed Nov 18 09:00 EST"),),
        )
    ]


def test_a_retry_shows_the_title_at_resend(tmp_path, monkeypatch) -> None:
    from docket import reminders

    fixed_times(monkeypatch, later(0), later(1))
    fixed_ids(monkeypatch, "k1")
    notifier = FakeNotifier()
    notifier.fail = 1
    with Store(tmp_path / "docket.sqlite3") as opened:
        seed(opened, TASKS[1:2])
        assert reminders.send_digest(opened, notifier, zone=ZONE, at=AT) is False
        with opened.transaction():
            opened.update_task("t1", at=SLOT, title="Synthetic renamed")
        assert reminders.send_digest(opened, notifier, zone=ZONE, at=AT) is True
    assert notifier.delivered == [
        Digest(
            "k1",
            "Still open past their deadlines: 1 task.",
            (DigestLine("t1", "Synthetic renamed", "Was due Tue Nov 17 17:00 EST"),),
        )
    ]


def test_tokyo_home_day_is_ahead_of_utc() -> None:
    from docket import reminders

    now = datetime.fromisoformat("2026-11-19T22:00:00+00:00")
    assert reminders.digest_slot(now, "Asia/Tokyo", AT) == (
        date(2026, 11, 20),
        datetime(2026, 11, 19, 22, tzinfo=UTC),
    )


def test_a_missing_queued_time_is_an_invalid_stored_digest_time(tmp_path) -> None:
    with Store(tmp_path / "docket.sqlite3") as opened:
        opened._connection.execute(
            "CREATE TEMP TABLE digest_times (number, day, key, queued_at, claimed_at, sent_at)"
        )
        opened._connection.execute(
            "INSERT INTO digest_times VALUES (1, '2026-11-20', 'k1', NULL, NULL, NULL)"
        )
        row = opened._connection.execute("SELECT * FROM digest_times").fetchone()
        with pytest.raises(StoreError, match="invalid stored digest time: d1"):
            opened._digest_from(row)
