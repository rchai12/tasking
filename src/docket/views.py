from datetime import datetime
from zoneinfo import ZoneInfo

from docket.deadlines import Deadline, WorkTime, status
from docket.store import Task

_DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_MONTHS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


def when(at: datetime, zone: str, now: datetime) -> str:
    local = _local(at, zone)
    year = f" {local.year}" if local.year != _local(now, zone).year else ""
    return (
        f"{_DAYS[local.weekday()]} {_MONTHS[local.month - 1]} {local.day}{year} "
        f"{_clock(local)} {local.tzname()}"
    )


def deadline_text(deadline: Deadline, home: str, now: datetime) -> str:
    text = when(deadline.at, home, now)
    if deadline.zone != home:
        text += f" ({when(deadline.at, deadline.zone, now)} where set)"
    if not deadline.time_given:
        text += ", no time given"
    return text


def work_text(work: WorkTime, home: str, now: datetime) -> str:
    text = _span(work.start, work.end, home, now)
    if work.zone != home:
        text += f" ({_span(work.start, work.end, work.zone, now)} where set)"
    return text


def status_text(task: Task, now: datetime) -> str:
    label = _LABELS[task.state]
    if task.state in {"open", "in_progress"} and task.deadline is not None:
        word = status(task.deadline, now)
        if word in {"due", "overdue"}:
            return f"{label}, {word}"
    return label


_LABELS = {
    "open": "open",
    "in_progress": "in progress",
    "done": "done",
    "cancelled": "cancelled",
}


def _local(at: datetime, zone: str) -> datetime:
    return at.astimezone(ZoneInfo(zone))


def _clock(local: datetime) -> str:
    return f"{local.hour:02d}:{local.minute:02d}"


def _span(start: datetime, end: datetime, zone: str, now: datetime) -> str:
    start_local = _local(start, zone)
    end_local = _local(end, zone)
    if start_local.date() != end_local.date():
        return f"{when(start, zone, now)} to {when(end, zone, now)}"
    ending = f"{_clock(end_local)} {end_local.tzname()}"
    if start_local.tzname() != end_local.tzname():
        return f"{when(start, zone, now)} to {ending}"
    shown = when(start, zone, now).removesuffix(f" {start_local.tzname()}")
    return f"{shown} to {ending}"
