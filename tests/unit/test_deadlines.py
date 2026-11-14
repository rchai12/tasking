import dataclasses
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from docket import clock, deadlines
from docket.deadlines import (
    DEFAULT_TIME,
    DUE_WINDOW,
    INSTANT_MESSAGE,
    TIME_MESSAGE,
    WORK_DAY_MESSAGE,
    WORK_DEADLINE_MESSAGE,
    WORK_LENGTH_MESSAGE,
    WORK_MINUTES_MAX,
    WORK_MINUTES_MIN,
    ZONE_MESSAGE,
    Deadline,
    DeadlineError,
    WorkTime,
    make_deadline,
    make_work_time,
    status,
)

NY = "America/New_York"
FRIDAY_5PM = Deadline(datetime(2026, 11, 20, 22, 0, tzinfo=UTC), NY, True)


def test_the_constants() -> None:
    assert DEFAULT_TIME == time(17, 0)
    assert DUE_WINDOW == timedelta(minutes=30)
    assert (WORK_MINUTES_MIN, WORK_MINUTES_MAX) == (5, 720)
    assert ZONE_MESSAGE == "unknown time zone"
    assert TIME_MESSAGE == "a time is hours and minutes only"
    assert INSTANT_MESSAGE == "an instant must be in UTC"
    assert WORK_LENGTH_MESSAGE == "a work time is 5 to 720 minutes"
    assert WORK_DAY_MESSAGE == "a work time must end by midnight"
    assert WORK_DEADLINE_MESSAGE == "a work time must end by the deadline"
    assert issubclass(DeadlineError, ValueError)


@pytest.mark.parametrize(
    ("day", "at", "zone", "instant", "time_given"),
    [
        (date(2026, 11, 20), time(14, 0), NY, datetime(2026, 11, 20, 19, 0, tzinfo=UTC), True),
        (date(2026, 11, 20), None, NY, datetime(2026, 11, 20, 22, 0, tzinfo=UTC), False),
        (date(2026, 11, 1), None, NY, datetime(2026, 11, 1, 22, 0, tzinfo=UTC), False),
        (date(2027, 3, 14), None, NY, datetime(2027, 3, 14, 21, 0, tzinfo=UTC), False),
        (
            date(2026, 11, 20),
            time(17, 0),
            "Asia/Tokyo",
            datetime(2026, 11, 20, 8, 0, tzinfo=UTC),
            True,
        ),
        (date(2026, 11, 20), time(9, 15), "UTC", datetime(2026, 11, 20, 9, 15, tzinfo=UTC), True),
        (date(2027, 3, 14), time(2, 30), NY, datetime(2027, 3, 14, 7, 30, tzinfo=UTC), True),
        (date(2026, 11, 1), time(1, 30), NY, datetime(2026, 11, 1, 5, 30, tzinfo=UTC), True),
    ],
    ids=[
        "afternoon",
        "date-only",
        "date-only-fall-back-day",
        "date-only-spring-forward-day",
        "tokyo",
        "utc",
        "missing-time-moves-forward",
        "repeated-time-is-the-first",
    ],
)
def test_a_deadline_is_a_utc_instant_in_its_zone(
    day: date, at: time | None, zone: str, instant: datetime, time_given: bool
) -> None:
    found = make_deadline(day, at, zone)
    assert found == Deadline(instant, zone, time_given)
    assert found.at.tzinfo is UTC


@pytest.mark.parametrize(
    "zone",
    ["america/new_york", "", "../etc/passwd", "Local", "America/New_York ", "Mars/Base"],
    ids=["lower-case", "empty", "path", "not-a-zone", "trailing-space", "made-up"],
)
def test_an_unknown_zone_is_refused(zone: str) -> None:
    with pytest.raises(DeadlineError) as raised:
        make_deadline(date(2026, 11, 20), time(14, 0), zone)
    assert str(raised.value) == ZONE_MESSAGE
    with pytest.raises(DeadlineError) as raised:
        make_work_time(date(2026, 11, 20), time(14, 0), 60, zone, None)
    assert str(raised.value) == ZONE_MESSAGE


@pytest.mark.parametrize(
    "at",
    [time(14, 0, 30), time(14, 0, 0, 1), time(14, 0, tzinfo=UTC)],
    ids=["seconds", "microseconds", "with-a-zone"],
)
def test_a_time_is_hours_and_minutes_only(at: time) -> None:
    with pytest.raises(DeadlineError) as raised:
        make_deadline(date(2026, 11, 20), at, NY)
    assert str(raised.value) == TIME_MESSAGE
    with pytest.raises(DeadlineError) as raised:
        make_work_time(date(2026, 11, 20), at, 60, NY, None)
    assert str(raised.value) == TIME_MESSAGE


@pytest.mark.parametrize(
    "at",
    [
        datetime(2026, 11, 20, 22, 0),
        datetime(2026, 11, 20, 17, 0, tzinfo=ZoneInfo(NY)),
        datetime(2026, 11, 20, 22, 0, tzinfo=ZoneInfo("UTC")),
    ],
    ids=["naive", "new-york", "zoneinfo-utc"],
)
def test_a_stored_instant_must_be_utc(at: datetime) -> None:
    with pytest.raises(DeadlineError) as raised:
        Deadline(at, NY, True)
    assert str(raised.value) == INSTANT_MESSAGE
    with pytest.raises(DeadlineError) as raised:
        WorkTime(at, 60, NY)
    assert str(raised.value) == INSTANT_MESSAGE


def test_a_stored_value_with_an_unknown_zone_is_refused() -> None:
    at = datetime(2026, 11, 20, 22, 0, tzinfo=UTC)
    with pytest.raises(DeadlineError) as raised:
        Deadline(at, "america/new_york", True)
    assert str(raised.value) == ZONE_MESSAGE
    with pytest.raises(DeadlineError) as raised:
        WorkTime(at, 60, "america/new_york")
    assert str(raised.value) == ZONE_MESSAGE


@pytest.mark.parametrize("minutes", [4, 721], ids=["too-short", "too-long"])
def test_a_stored_work_time_keeps_the_length_rule(minutes: int) -> None:
    with pytest.raises(DeadlineError) as raised:
        WorkTime(datetime(2026, 11, 20, 19, 0, tzinfo=UTC), minutes, NY)
    assert str(raised.value) == WORK_LENGTH_MESSAGE


def test_the_values_are_frozen() -> None:
    work = WorkTime(datetime(2026, 11, 20, 19, 0, tzinfo=UTC), 60, NY)
    with pytest.raises(dataclasses.FrozenInstanceError):
        FRIDAY_5PM.zone = "UTC"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        work.minutes = 30  # type: ignore[misc]


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (datetime(2026, 11, 20, 21, 59, 59, tzinfo=UTC), "upcoming"),
        (datetime(2026, 11, 20, 22, 0, tzinfo=UTC), "due"),
        (datetime(2026, 11, 20, 22, 29, 59, tzinfo=UTC), "due"),
        (datetime(2026, 11, 20, 22, 30, tzinfo=UTC), "overdue"),
        (datetime(2026, 11, 21, 9, 0, tzinfo=UTC), "overdue"),
        (datetime(2026, 11, 20, 16, 59, tzinfo=ZoneInfo(NY)), "upcoming"),
        (datetime(2026, 11, 20, 17, 0, tzinfo=ZoneInfo(NY)), "due"),
    ],
    ids=[
        "a-second-before",
        "at-the-deadline",
        "last-second-due",
        "thirty-minutes-after",
        "next-day",
        "now-in-new-york-before",
        "now-in-new-york-at",
    ],
)
def test_status_comes_from_the_deadline_and_now(now: datetime, expected: str) -> None:
    assert status(FRIDAY_5PM, now) == expected


@pytest.mark.parametrize(
    ("day", "start", "minutes", "zone", "deadline", "begins", "ends"),
    [
        (
            date(2026, 11, 20),
            time(14, 0),
            60,
            NY,
            FRIDAY_5PM,
            datetime(2026, 11, 20, 19, 0, tzinfo=UTC),
            datetime(2026, 11, 20, 20, 0, tzinfo=UTC),
        ),
        (
            date(2026, 11, 20),
            time(14, 0),
            180,
            NY,
            FRIDAY_5PM,
            datetime(2026, 11, 20, 19, 0, tzinfo=UTC),
            datetime(2026, 11, 20, 22, 0, tzinfo=UTC),
        ),
        (
            date(2026, 11, 20),
            time(8, 0),
            5,
            NY,
            None,
            datetime(2026, 11, 20, 13, 0, tzinfo=UTC),
            datetime(2026, 11, 20, 13, 5, tzinfo=UTC),
        ),
        (
            date(2026, 11, 20),
            time(8, 0),
            720,
            NY,
            None,
            datetime(2026, 11, 20, 13, 0, tzinfo=UTC),
            datetime(2026, 11, 21, 1, 0, tzinfo=UTC),
        ),
        (
            date(2026, 11, 20),
            time(23, 0),
            60,
            NY,
            None,
            datetime(2026, 11, 21, 4, 0, tzinfo=UTC),
            datetime(2026, 11, 21, 5, 0, tzinfo=UTC),
        ),
        (
            date(2026, 11, 1),
            time(0, 30),
            180,
            NY,
            None,
            datetime(2026, 11, 1, 4, 30, tzinfo=UTC),
            datetime(2026, 11, 1, 7, 30, tzinfo=UTC),
        ),
        (
            date(2026, 11, 1),
            time(12, 0),
            720,
            NY,
            None,
            datetime(2026, 11, 1, 17, 0, tzinfo=UTC),
            datetime(2026, 11, 2, 5, 0, tzinfo=UTC),
        ),
        (
            date(2027, 3, 14),
            time(12, 30),
            690,
            NY,
            None,
            datetime(2027, 3, 14, 16, 30, tzinfo=UTC),
            datetime(2027, 3, 15, 4, 0, tzinfo=UTC),
        ),
        (
            date(2027, 3, 14),
            time(2, 30),
            60,
            NY,
            None,
            datetime(2027, 3, 14, 7, 30, tzinfo=UTC),
            datetime(2027, 3, 14, 8, 30, tzinfo=UTC),
        ),
        (
            date(2026, 11, 20),
            time(14, 0),
            60,
            NY,
            Deadline(datetime(2026, 11, 20, 21, 0, tzinfo=UTC), "Asia/Tokyo", True),
            datetime(2026, 11, 20, 19, 0, tzinfo=UTC),
            datetime(2026, 11, 20, 20, 0, tzinfo=UTC),
        ),
    ],
    ids=[
        "one-hour",
        "ends-at-the-deadline",
        "shortest",
        "longest",
        "ends-at-midnight",
        "fall-back-day-real-minutes",
        "fall-back-day-to-midnight",
        "spring-forward-day-to-midnight",
        "missing-start-moves-forward",
        "deadline-in-another-zone",
    ],
)
def test_a_work_time_is_a_start_and_a_length(
    day: date,
    start: time,
    minutes: int,
    zone: str,
    deadline: Deadline | None,
    begins: datetime,
    ends: datetime,
) -> None:
    found = make_work_time(day, start, minutes, zone, deadline)
    assert found == WorkTime(begins, minutes, zone)
    assert (found.start.tzinfo, found.end) == (UTC, ends)


@pytest.mark.parametrize("minutes", [4, 721, 0, -60], ids=["four", "721", "zero", "negative"])
def test_a_work_time_is_5_to_720_minutes(minutes: int) -> None:
    with pytest.raises(DeadlineError) as raised:
        make_work_time(date(2026, 11, 20), time(8, 0), minutes, NY, None)
    assert str(raised.value) == WORK_LENGTH_MESSAGE


@pytest.mark.parametrize(
    ("day", "start", "minutes"),
    [
        (date(2026, 11, 20), time(23, 0), 61),
        (date(2027, 3, 14), time(12, 30), 720),
    ],
    ids=["a-minute-past-midnight", "spring-forward-day-is-shorter"],
)
def test_a_work_time_ends_by_midnight(day: date, start: time, minutes: int) -> None:
    with pytest.raises(DeadlineError) as raised:
        make_work_time(day, start, minutes, NY, None)
    assert str(raised.value) == WORK_DAY_MESSAGE


@pytest.mark.parametrize(
    ("start", "minutes", "deadline"),
    [
        (time(14, 0), 181, FRIDAY_5PM),
        (time(18, 0), 60, FRIDAY_5PM),
        (
            time(14, 0),
            121,
            Deadline(datetime(2026, 11, 20, 21, 0, tzinfo=UTC), "Asia/Tokyo", True),
        ),
    ],
    ids=["a-minute-late", "after-the-deadline", "deadline-in-another-zone"],
)
def test_a_work_time_ends_by_the_deadline(start: time, minutes: int, deadline: Deadline) -> None:
    with pytest.raises(DeadlineError) as raised:
        make_work_time(date(2026, 11, 20), start, minutes, NY, deadline)
    assert str(raised.value) == WORK_DEADLINE_MESSAGE


@pytest.mark.parametrize(
    ("start", "minutes", "zone", "expected"),
    [
        (time(14, 0, 30), 60, "Mars/Base", TIME_MESSAGE),
        (time(14, 0), 721, "Mars/Base", ZONE_MESSAGE),
        (time(23, 0), 721, NY, WORK_LENGTH_MESSAGE),
        (time(23, 0), 61, NY, WORK_DAY_MESSAGE),
    ],
    ids=["time-before-zone", "zone-before-length", "length-before-midnight", "midnight-first"],
)
def test_the_first_broken_rule_is_reported(
    start: time, minutes: int, zone: str, expected: str
) -> None:
    with pytest.raises(DeadlineError) as raised:
        make_work_time(date(2026, 11, 20), start, minutes, zone, FRIDAY_5PM)
    assert str(raised.value) == expected


def test_the_time_rules_never_read_the_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse() -> datetime:
        raise AssertionError("the time rules read the clock")

    monkeypatch.setattr(clock, "now", refuse)
    found = make_deadline(date(2026, 11, 20), None, NY)
    make_work_time(date(2026, 11, 20), time(14, 0), 60, NY, found)
    assert status(found, datetime(2026, 11, 20, 22, 0, tzinfo=UTC)) == "due"
    assert deadlines.DEFAULT_TIME == time(17, 0)
