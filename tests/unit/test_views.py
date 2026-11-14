import locale
from datetime import UTC, datetime

import pytest

from docket import clock
from docket.deadlines import Deadline, WorkTime
from docket.store import Task
from docket.views import deadline_text, status_text, when, work_text

NY = "America/New_York"
NOW = datetime(2026, 11, 14, 14, 0, tzinfo=UTC)
FRIDAY_5PM = datetime(2026, 11, 20, 22, 0, tzinfo=UTC)


def task(state: str, deadline: Deadline | None = None) -> Task:
    return Task(
        id="t1",
        title="Pay rent",
        state=state,
        deadline=deadline,
        work=None,
        source="owner",
        provider=None,
        message_id=None,
        link=None,
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.mark.parametrize(
    ("at", "zone", "now", "expected"),
    [
        (FRIDAY_5PM, NY, NOW, "Fri Nov 20 17:00 EST"),
        (datetime(2027, 1, 8, 22, 0, tzinfo=UTC), NY, NOW, "Fri Jan 8 2027 17:00 EST"),
        (FRIDAY_5PM, "Asia/Tokyo", NOW, "Sat Nov 21 07:00 JST"),
        (FRIDAY_5PM, "Asia/Kolkata", NOW, "Sat Nov 21 03:30 IST"),
        (FRIDAY_5PM, "America/Sao_Paulo", NOW, "Fri Nov 20 19:00 -03"),
        (FRIDAY_5PM, "UTC", NOW, "Fri Nov 20 22:00 UTC"),
        (
            datetime(2027, 1, 10, 12, 0, tzinfo=UTC),
            "Australia/Lord_Howe",
            NOW,
            "Sun Jan 10 2027 23:00 +11",
        ),
        (datetime(2026, 11, 1, 5, 30, tzinfo=UTC), NY, NOW, "Sun Nov 1 01:30 EDT"),
        (datetime(2026, 11, 1, 6, 30, tzinfo=UTC), NY, NOW, "Sun Nov 1 01:30 EST"),
        (
            datetime(2027, 1, 1, 15, 0, tzinfo=UTC),
            NY,
            datetime(2027, 1, 1, 4, 0, tzinfo=UTC),
            "Fri Jan 1 2027 10:00 EST",
        ),
        (
            datetime(2026, 12, 31, 23, 30, tzinfo=UTC),
            "Asia/Tokyo",
            datetime(2026, 12, 31, 12, 0, tzinfo=UTC),
            "Fri Jan 1 2027 08:30 JST",
        ),
        (
            datetime(2027, 1, 1, 3, 0, tzinfo=UTC),
            NY,
            datetime(2026, 12, 31, 12, 0, tzinfo=UTC),
            "Thu Dec 31 22:00 EST",
        ),
    ],
    ids=[
        "this-year",
        "next-year",
        "tokyo",
        "half-hour-offset",
        "numeric-abbreviation",
        "utc",
        "half-hour-daylight-time",
        "first-of-a-repeated-hour",
        "second-of-a-repeated-hour",
        "still-last-year-here",
        "year-read-in-the-zone",
        "already-next-year-in-utc",
    ],
)
def test_when_names_the_day_time_and_zone(
    at: datetime, zone: str, now: datetime, expected: str
) -> None:
    assert when(at, zone, now) == expected


def test_when_is_english_whatever_the_locale() -> None:
    saved = locale.setlocale(locale.LC_TIME)
    try:
        locale.setlocale(locale.LC_TIME, "fr_FR.UTF-8")
        assert when(FRIDAY_5PM, NY, NOW) == "Fri Nov 20 17:00 EST"
    finally:
        locale.setlocale(locale.LC_TIME, saved)


@pytest.mark.parametrize(
    ("deadline", "expected"),
    [
        (Deadline(FRIDAY_5PM, NY, True), "Fri Nov 20 17:00 EST"),
        (Deadline(FRIDAY_5PM, NY, False), "Fri Nov 20 17:00 EST, no time given"),
        (
            Deadline(FRIDAY_5PM, "Asia/Tokyo", True),
            "Fri Nov 20 17:00 EST (Sat Nov 21 07:00 JST where set)",
        ),
        (
            Deadline(FRIDAY_5PM, "Asia/Tokyo", False),
            "Fri Nov 20 17:00 EST (Sat Nov 21 07:00 JST where set), no time given",
        ),
    ],
    ids=["home", "no-time-given", "set-elsewhere", "set-elsewhere-no-time"],
)
def test_a_deadline_in_your_zone_and_where_it_was_set(deadline: Deadline, expected: str) -> None:
    assert deadline_text(deadline, NY, NOW) == expected


@pytest.mark.parametrize(
    ("work", "expected"),
    [
        (
            WorkTime(datetime(2026, 11, 20, 19, 0, tzinfo=UTC), 60, NY),
            "Fri Nov 20 14:00 to 15:00 EST",
        ),
        (
            WorkTime(datetime(2026, 11, 1, 4, 30, tzinfo=UTC), 180, NY),
            "Sun Nov 1 00:30 EDT to 02:30 EST",
        ),
        (
            WorkTime(datetime(2026, 11, 21, 4, 0, tzinfo=UTC), 60, NY),
            "Fri Nov 20 23:00 EST to Sat Nov 21 00:00 EST",
        ),
        (
            WorkTime(datetime(2026, 11, 20, 5, 0, tzinfo=UTC), 60, "Asia/Tokyo"),
            "Fri Nov 20 00:00 to 01:00 EST (Fri Nov 20 14:00 to 15:00 JST where set)",
        ),
        (
            WorkTime(datetime(2026, 11, 21, 4, 30, tzinfo=UTC), 60, "Asia/Tokyo"),
            "Fri Nov 20 23:30 EST to Sat Nov 21 00:30 EST"
            " (Sat Nov 21 13:30 to 14:30 JST where set)",
        ),
    ],
    ids=[
        "one-hour",
        "across-the-change",
        "to-midnight",
        "set-elsewhere",
        "set-elsewhere-across-your-midnight",
    ],
)
def test_a_work_time_as_a_span(work: WorkTime, expected: str) -> None:
    assert work_text(work, NY, NOW) == expected


@pytest.mark.parametrize(
    ("state", "deadline", "now", "expected"),
    [
        ("open", None, NOW, "open"),
        ("open", FRIDAY_5PM, NOW, "open"),
        ("open", FRIDAY_5PM, datetime(2026, 11, 20, 22, 10, tzinfo=UTC), "open, due"),
        ("in_progress", None, NOW, "in progress"),
        (
            "in_progress",
            FRIDAY_5PM,
            datetime(2026, 11, 21, 9, 0, tzinfo=UTC),
            "in progress, overdue",
        ),
        ("done", FRIDAY_5PM, datetime(2026, 11, 21, 9, 0, tzinfo=UTC), "done"),
        ("cancelled", FRIDAY_5PM, datetime(2026, 11, 21, 9, 0, tzinfo=UTC), "cancelled"),
    ],
    ids=[
        "open",
        "open-upcoming",
        "open-due",
        "in-progress",
        "in-progress-overdue",
        "done-ignores-the-deadline",
        "cancelled-ignores-the-deadline",
    ],
)
def test_the_status_word(
    state: str, deadline: datetime | None, now: datetime, expected: str
) -> None:
    value = Deadline(deadline, NY, True) if deadline is not None else None
    assert status_text(task(state, value), now) == expected


def test_the_views_never_read_the_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse() -> datetime:
        raise AssertionError("a view read the clock")

    monkeypatch.setattr(clock, "now", refuse)
    work = WorkTime(datetime(2026, 11, 20, 19, 0, tzinfo=UTC), 60, NY)
    assert when(FRIDAY_5PM, NY, NOW) == "Fri Nov 20 17:00 EST"
    assert deadline_text(Deadline(FRIDAY_5PM, NY, True), NY, NOW) == "Fri Nov 20 17:00 EST"
    assert work_text(work, NY, NOW) == "Fri Nov 20 14:00 to 15:00 EST"
    assert status_text(task("open"), NOW) == "open"
