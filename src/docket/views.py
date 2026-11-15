from datetime import datetime
from zoneinfo import ZoneInfo

from docket.core import Outcome
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


def task_line(task: Task, home: str, now: datetime) -> str:
    line = f"{task.id.ljust(5)} {status_text(task, now).ljust(21)} {task.title}"
    if task.deadline is not None:
        line += f"  due {deadline_text(task.deadline, home, now)}"
    return line


def task_detail(task: Task, home: str, now: datetime) -> list[str]:
    due = "none" if task.deadline is None else deadline_text(task.deadline, home, now)
    work = "none" if task.work is None else work_text(task.work, home, now)
    if task.source == "email":
        source = f"Source: email, {task.provider} {task.message_id}"
    else:
        source = f"Source: {task.source}"
    lines = [
        f"{task.id}  {task.title}",
        f"State: {status_text(task, now)}",
        f"Due: {due}",
        f"Work: {work}",
        source,
    ]
    if task.link is not None:
        lines.append(f"Link: {task.link}")
    lines.append(f"Created: {when(task.created_at, home, now)}")
    lines.append(f"Updated: {when(task.updated_at, home, now)}")
    return lines


def edited_text(outcome: Outcome, home: str) -> str:
    task = outcome.task
    if not outcome.changed:
        return f"Nothing changed for {task.id}."
    if task.deadline is None:
        return f"Updated {task.id}: {task.title}, no deadline"
    due = deadline_text(task.deadline, home, task.updated_at)
    return f"Updated {task.id}: {task.title}, due {due}"


def planned_text(outcome: Outcome, home: str) -> str:
    task = outcome.task
    if not outcome.changed:
        return f"Nothing changed for {task.id}."
    if task.work is None:
        return f"Cleared the work time of {task.id}."
    return f"Planned {task.id}: {work_text(task.work, home, task.updated_at)}"


def change_text(action: str, outcome: Outcome) -> str:
    task = outcome.task
    if outcome.changed:
        return f"{_VERBS[action]} {task.id}: {task.title}"
    return f"{task.id} is already {_LABELS[task.state]}."


def refusal_text(code: str, task_id: str | None = None) -> str:
    if code == "unknown_task":
        if task_id is None:
            return "There is no such task."
        return f"There is no task {task_id}."
    if code == "task_ended":
        if task_id is None:
            return "That task has ended; reopen it first."
        return f"Task {task_id} has ended; reopen it first."
    return _REFUSALS[code]


def status_text(task: Task, now: datetime) -> str:
    label = _LABELS[task.state]
    if task.state in {"open", "in_progress"} and task.deadline is not None:
        word = status(task.deadline, now)
        if word in {"due", "overdue"}:
            return f"{label}, {word}"
    return label


_REFUSALS = {
    "invalid_title": "A title is 1 to 100 characters on one line, with no space at either end.",
    "invalid_source": "That source is not allowed.",
    "invalid_reference": "That email reference is not complete.",
    "invalid_actor": "That actor is not allowed.",
    "invalid_action": "That is not a state change.",
    "work_after_deadline": "The work time must end by the deadline.",
}

_VERBS = {"start": "Started", "done": "Done", "cancel": "Cancelled", "reopen": "Reopened"}

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
