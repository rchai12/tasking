import functools
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, available_timezones

DEFAULT_TIME = time(17, 0)
DUE_WINDOW = timedelta(minutes=30)
WORK_MINUTES_MIN = 5
WORK_MINUTES_MAX = 720

ZONE_MESSAGE = "unknown time zone"
TIME_MESSAGE = "a time is hours and minutes only"
INSTANT_MESSAGE = "an instant must be in UTC"
WORK_LENGTH_MESSAGE = "a work time is 5 to 720 minutes"
WORK_DAY_MESSAGE = "a work time must end by midnight"
WORK_DEADLINE_MESSAGE = "a work time must end by the deadline"


class DeadlineError(ValueError):
    pass


@functools.cache
def _zone_names() -> frozenset[str]:
    return frozenset(available_timezones())


def _require_zone(zone: str) -> None:
    if zone not in _zone_names():
        raise DeadlineError(ZONE_MESSAGE)


def _require_utc(at: datetime) -> None:
    if at.tzinfo is not UTC:
        raise DeadlineError(INSTANT_MESSAGE)


def _require_hours_and_minutes(at: time) -> None:
    if at.second != 0 or at.microsecond != 0 or at.tzinfo is not None:
        raise DeadlineError(TIME_MESSAGE)


def _instant(day: date, at: time, zone: str) -> datetime:
    wall = datetime(
        day.year,
        day.month,
        day.day,
        at.hour,
        at.minute,
        tzinfo=ZoneInfo(zone),
        fold=0,
    )
    return wall.astimezone(UTC)


@dataclass(frozen=True)
class Deadline:
    at: datetime
    zone: str
    time_given: bool

    def __post_init__(self) -> None:
        _require_utc(self.at)
        _require_zone(self.zone)


@dataclass(frozen=True)
class WorkTime:
    start: datetime
    minutes: int
    zone: str

    def __post_init__(self) -> None:
        _require_utc(self.start)
        _require_zone(self.zone)
        if not WORK_MINUTES_MIN <= self.minutes <= WORK_MINUTES_MAX:
            raise DeadlineError(WORK_LENGTH_MESSAGE)

    @property
    def end(self) -> datetime:
        return self.start + timedelta(minutes=self.minutes)


def make_deadline(day: date, at: time | None, zone: str) -> Deadline:
    if at is None:
        clock_time = DEFAULT_TIME
        time_given = False
    else:
        _require_hours_and_minutes(at)
        clock_time = at
        time_given = True
    _require_zone(zone)
    return Deadline(_instant(day, clock_time, zone), zone, time_given)


def make_work_time(
    day: date, start: time, minutes: int, zone: str, deadline: Deadline | None
) -> WorkTime:
    _require_hours_and_minutes(start)
    _require_zone(zone)
    work = WorkTime(_instant(day, start, zone), minutes, zone)
    midnight = _instant(day + timedelta(days=1), time(0, 0), zone)
    if work.end > midnight:
        raise DeadlineError(WORK_DAY_MESSAGE)
    if deadline is not None and work.end > deadline.at:
        raise DeadlineError(WORK_DEADLINE_MESSAGE)
    return work


def status(deadline: Deadline, now: datetime) -> str:
    if now < deadline.at:
        return "upcoming"
    if now < deadline.at + DUE_WINDOW:
        return "due"
    return "overdue"
