from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from docket import domain
from docket.core import Outcome
from docket.deadlines import Deadline, WorkTime, status
from docket.store import LoopStatus, Task

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
    return f"{task.id} is already {domain.STATE_LABELS[task.state]}."


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
    label = domain.STATE_LABELS[task.state]
    if task.state in domain.OPEN_STATES and task.deadline is not None:
        word = status(task.deadline, now)
        if word in {"due", "overdue"}:
            return f"{label}, {word}"
    return label


_REFUSALS = {
    "invalid_reminder_plan": "That time cannot be scheduled for reminders.",
    "invalid_title": "A title is 1 to 100 characters on one line, with no space at either end.",
    "invalid_source": "That source is not allowed.",
    "invalid_reference": "That email reference is not complete.",
    "invalid_actor": "That actor is not allowed.",
    "invalid_action": "That is not a state change.",
    "work_after_deadline": "The work time must end by the deadline.",
    "invalid_client": "That client is not allowed.",
    "invalid_key": "A request key is 1 to 200 characters.",
    "key_reused": "That request key was already used for a different request.",
    "invalid_deadline": "That is not a valid deadline.",
    "invalid_work": "That is not a valid work time.",
}

_VERBS = {"start": "Started", "done": "Done", "cancel": "Cancelled", "reopen": "Reopened"}


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


_NOTICE = {
    "start": "Time to start.",
    "before": "Are you working on this?",
    "due_soon": "This is due soon.",
    "due": "This is now due.",
    "late": "This is late.",
}


def notice_text(kind: str, missed: int) -> str:
    line = _NOTICE[kind]
    if missed >= 2:
        return f"Missed while docket was offline: {missed} reminders.\n{line}"
    return line


def digest_heading(count: int) -> str:
    noun = "task" if count == 1 else "tasks"
    return f"Still open past their deadlines: {count} {noun}."


def _health(failures: int) -> str:
    if failures == 0:
        return "ok"
    return f"failing for {failures} pass" + ("" if failures == 1 else "es")


def loop_status_lines(status: LoopStatus | None, home: str, now: datetime) -> list[str]:
    if status is None:
        return ["Reminder loop: no pass recorded yet"]
    stale = now - status.pass_at > timedelta(minutes=domain.LOOP_STALE_MINUTES)
    state = "not running" if stale else "running"
    digest = f"Digest: {_health(status.digest_failures)}" + (", sent" if status.digest else "")
    lines = [
        f"Reminder loop: {state}, last pass {when(status.pass_at, home, now)}",
        f"Reminders: {_health(status.reminders_failures)}, {status.sent} sent",
        digest,
    ]
    if status.skipped:
        lines.append("Skipped tasks: " + ", ".join(status.skipped))
    return lines
