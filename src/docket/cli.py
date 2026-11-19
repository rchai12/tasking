import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import NoReturn

import typer

from docket import __version__, clock, domain, parsing
from docket.clients import ClientError, issue_token
from docket.config import ConfigError, Settings, get_settings, home_zone
from docket.core import CoreError, Outcome, change_state, create_task, edit_task
from docket.deadlines import (
    WORK_DAY_MESSAGE,
    Deadline,
    DeadlineError,
    WorkTime,
    make_deadline,
    make_work_time,
)
from docket.keychain import KeychainUnavailable
from docket.server import ServeError, build_app, run_app
from docket.store import UNCHANGED, Store, StoreError, Task, open_store
from docket.views import (
    change_text,
    deadline_text,
    edited_text,
    planned_text,
    refusal_text,
    task_detail,
    task_line,
)

DUE_MESSAGE = "--due must be a date like 2026-11-20."
AT_MESSAGE = "--at must be a time like 17:00."
AT_WITHOUT_DUE_MESSAGE = "--at needs --due."
NO_TASKS_MESSAGE = "No tasks."
NOTHING_TO_EDIT_MESSAGE = "Give --title, --due or --no-due."
BOTH_DUES_MESSAGE = "--due and --no-due can't be used together."
PLAN_NEEDS_MESSAGE = "Give a date and a start time, or --clear."
CLEAR_ALONE_MESSAGE = "--clear takes no date, start time or --minutes."
PLAN_DATE_MESSAGE = "The date must look like 2026-11-20."
PLAN_TIME_MESSAGE = "The start time must look like 14:00."
MINUTES_MESSAGE = "--minutes must be 5 to 720."
MIDNIGHT_MESSAGE = "A work time must end by midnight."

app = typer.Typer()
tasks_app = typer.Typer()
clients_app = typer.Typer()
mcp_app = typer.Typer()
app.add_typer(tasks_app, name="tasks")
app.add_typer(clients_app, name="clients")
app.add_typer(mcp_app, name="mcp")


@app.callback()
def _callback() -> None:
    """Tasks, reminders and calendar sync."""


@app.command()
def version() -> None:
    print(f"docket {__version__}")


@app.command()
def serve() -> None:
    try:
        settings = get_settings()
        built = build_app(settings)
    except (ConfigError, KeychainUnavailable, ServeError, StoreError) as error:
        _fail(str(error))
    print(f"Serving on http://127.0.0.1:{settings.web_port}")
    run_app(built, settings.web_port)


@mcp_app.command("serve")
def mcp_serve() -> None:
    """Serve the read tools to Conductor over stdio."""
    from docket.mcp_server import server

    try:
        built = server.build_server(get_settings())
    except (ConfigError, StoreError) as error:
        _fail(str(error))
    server.serve(built)


@clients_app.command("add")
def add_client(client: str, replace: bool = typer.Option(False, "--replace")) -> None:
    try:
        token = issue_token(client, replace=replace)
    except (ClientError, KeychainUnavailable) as error:
        _fail(str(error))
    print(token)


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
        states = None if all_tasks else domain.OPEN_STATES
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


@tasks_app.command()
def edit(
    task_id: str,
    title: str | None = typer.Option(None, "--title"),
    due: str | None = typer.Option(None, "--due"),
    at: str | None = typer.Option(None, "--at"),
    no_due: bool = typer.Option(False, "--no-due"),
) -> None:
    settings, home = _home()
    if title is None and due is None and not no_due and at is None:
        _fail(NOTHING_TO_EDIT_MESSAGE)
    if due is not None and no_due:
        _fail(BOTH_DUES_MESSAGE)
    if at is not None and due is None:
        _fail(AT_WITHOUT_DUE_MESSAGE)
    deadline: object = UNCHANGED
    if no_due:
        deadline = None
    elif due is not None:
        deadline = _deadline(due, at, home)
    outcome = _apply(
        settings,
        task_id,
        title=UNCHANGED if title is None else title,
        deadline=deadline,
    )
    print(edited_text(outcome, home))


@tasks_app.command()
def plan(
    task_id: str,
    day: str | None = typer.Argument(None),
    start: str | None = typer.Argument(None),
    minutes: int | None = typer.Option(None, "--minutes"),
    clear: bool = typer.Option(False, "--clear"),
) -> None:
    settings, home = _home()
    if clear:
        if day is not None or start is not None or minutes is not None:
            _fail(CLEAR_ALONE_MESSAGE)
        work = None
    elif day is None or start is None:
        _fail(PLAN_NEEDS_MESSAGE)
    else:
        length = settings.work_minutes if minutes is None else minutes
        work = _planned(day, start, length, home)
    outcome = _apply(settings, task_id, work=work)
    print(planned_text(outcome, home))


def _apply(settings: Settings, task_id: str, **fields: object) -> Outcome:
    with _store(settings) as store:
        try:
            return edit_task(store, task_id, actor="owner", **fields)
        except CoreError as error:
            _fail(refusal_text(error.code, task_id))


def _planned(day: str, start: str, minutes: int, home: str) -> WorkTime:
    parsed_day = _read(parsing.parse_date, day, PLAN_DATE_MESSAGE)
    parsed_start = _read(parsing.parse_time, start, PLAN_TIME_MESSAGE)
    try:
        return make_work_time(parsed_day, parsed_start, minutes, home, None)
    except DeadlineError as error:
        if str(error) == WORK_DAY_MESSAGE:
            _fail(MIDNIGHT_MESSAGE)
        _fail(MINUTES_MESSAGE)


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


@contextmanager
def _store(settings: Settings) -> Iterator[Store]:
    try:
        with open_store(settings) as store:
            yield store
    except StoreError as error:
        _fail(str(error))


def _deadline(due: str | None, at: str | None, home: str) -> Deadline | None:
    if due is None:
        return None
    day = _read(parsing.parse_date, due, DUE_MESSAGE)
    clock_time = None if at is None else _read(parsing.parse_time, at, AT_MESSAGE)
    return make_deadline(day, clock_time, home)


def _read[T](parse: Callable[[object], T], value: str, message: str) -> T:
    try:
        return parse(value)
    except parsing.ParseError:
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
