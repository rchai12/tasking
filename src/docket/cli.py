import re
import sys
from collections.abc import Callable
from datetime import UTC, date, datetime, time
from typing import NoReturn

import typer

from docket import __version__, clock
from docket.config import ConfigError, Settings, get_settings, home_zone
from docket.core import CoreError, change_state, create_task
from docket.deadlines import Deadline, make_deadline
from docket.store import Store, StoreError, Task, open_store
from docket.views import change_text, deadline_text, refusal_text, task_detail, task_line

DUE_MESSAGE = "--due must be a date like 2026-11-20."
AT_MESSAGE = "--at must be a time like 17:00."
AT_WITHOUT_DUE_MESSAGE = "--at needs --due."
NO_TASKS_MESSAGE = "No tasks."

_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_TIME = re.compile(r"[0-9]{2}:[0-9]{2}")

app = typer.Typer()
tasks_app = typer.Typer()
app.add_typer(tasks_app, name="tasks")


@app.callback()
def _callback() -> None:
    """Tasks, reminders and calendar sync."""


@app.command()
def version() -> None:
    print(f"docket {__version__}")


@tasks_app.command()
def add(
    title: str,
    due: str | None = typer.Option(None, "--due"),
    at: str | None = typer.Option(None, "--at"),
) -> None:
    settings, home = _home()
    if at is not None and due is None:
        _fail(AT_WITHOUT_DUE_MESSAGE)
    deadline = _deadline(due, at, home)
    with _store(settings) as store:
        try:
            task = create_task(store, title=title, source="owner", deadline=deadline)
        except CoreError as error:
            _fail(refusal_text(error.code))
    text = f"Added {task.id}: {task.title}"
    if deadline is not None:
        text += f", due {deadline_text(deadline, home, task.created_at)}"
    print(text)


@tasks_app.command("list")
def list_tasks(all_tasks: bool = typer.Option(False, "--all")) -> None:
    settings, home = _home()
    with _store(settings) as store:
        now = clock.now()
        states = None if all_tasks else ("open", "in_progress")
        found = store.tasks(states)
    if not found:
        print(NO_TASKS_MESSAGE)
        return
    for task in sorted(found, key=_list_key):
        print(task_line(task, home, now))


@tasks_app.command()
def show(task_id: str) -> None:
    settings, home = _home()
    with _store(settings) as store:
        now = clock.now()
        found = store.task(task_id)
    if found is None:
        _fail(refusal_text("unknown_task", task_id))
    for line in task_detail(found, home, now):
        print(line)


@tasks_app.command()
def start(task_id: str) -> None:
    _change(task_id, "start")


@tasks_app.command()
def done(task_id: str) -> None:
    _change(task_id, "done")


@tasks_app.command()
def cancel(task_id: str) -> None:
    _change(task_id, "cancel")


@tasks_app.command()
def reopen(task_id: str) -> None:
    _change(task_id, "reopen")


def _change(task_id: str, action: str) -> None:
    settings, _zone = _home()
    with _store(settings) as store:
        try:
            outcome = change_state(store, task_id, action, actor="owner")
        except CoreError as error:
            _fail(refusal_text(error.code, task_id))
    print(change_text(action, outcome))


def _home() -> tuple[Settings, str]:
    try:
        settings = get_settings()
        return settings, home_zone(settings)
    except ConfigError as error:
        _fail(str(error))


def _store(settings: Settings) -> Store:
    try:
        return open_store(settings)
    except StoreError as error:
        _fail(str(error))


def _deadline(due: str | None, at: str | None, home: str) -> Deadline | None:
    if due is None:
        return None
    day = _parse(_DATE, due, date.fromisoformat, DUE_MESSAGE)
    clock_time = None if at is None else _parse(_TIME, at, time.fromisoformat, AT_MESSAGE)
    return make_deadline(day, clock_time, home)


def _parse[T](pattern: re.Pattern[str], value: str, read: Callable[[str], T], message: str) -> T:
    if pattern.fullmatch(value) is None:
        _fail(message)
    try:
        return read(value)
    except ValueError:
        _fail(message)


def _list_key(task: Task) -> tuple[bool, datetime, int]:
    if task.deadline is None:
        instant = datetime.min.replace(tzinfo=UTC)
    else:
        instant = task.deadline.at
    return (task.deadline is None, instant, int(task.id.removeprefix("t")))


def _fail(message: str) -> NoReturn:
    print(message, file=sys.stderr)
    raise typer.Exit(1)
