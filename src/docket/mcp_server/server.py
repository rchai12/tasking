"""The docket MCP server: read tools over stdio."""

from datetime import datetime
from zoneinfo import ZoneInfo

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict

from docket import config, reads, writes
from docket.config import Settings
from docket.deadlines import Deadline, WorkTime
from docket.store import Reminder, Task, open_store

SERVER_NAME = "docket"
INSTRUCTIONS = (
    "The owner's tasks in docket. list_tasks and get_task only read. create_task, complete_task "
    "and cancel_task change tasks once Conductor's step is approved; each takes a request_key, "
    "and the same key with the same arguments changes nothing twice."
)
LIST_TASKS = (
    "List tasks by status: open, in_progress, due (deadline later today), overdue, done or "
    "cancelled. Up to 50 a page; pass next_after back as after for the next page."
)
GET_TASK = "One task by id, with its sent and pending reminders."
CREATE_TASK = (
    "Create an approved task, source agent. deadline is null or {date, time, time_zone}: "
    "date YYYY-MM-DD, time HH:MM or null for 17:00, time_zone an IANA name. "
    "The same request_key with the same arguments returns the same task."
)
COMPLETE_TASK = (
    "Mark a task done, as the Done button does; a task already done is no change. "
    "The same request_key returns the first answer."
)
CANCEL_TASK = (
    "Cancel a task, as the Cancel button does; a task already cancelled is no change. "
    "The same request_key returns the first answer."
)


class DeadlineResult(BaseModel):
    at: str
    date: str
    time: str | None
    time_zone: str


class WorkResult(BaseModel):
    start: str
    minutes: int
    time_zone: str


class TaskResult(BaseModel):
    id: str
    title: str
    state: str
    source: str
    deadline: DeadlineResult | None
    work: WorkResult | None
    created_at: str
    updated_at: str


class TaskPageResult(BaseModel):
    tasks: list[TaskResult]
    next_after: str | None


class ReminderResult(BaseModel):
    kind: str
    fire_at: str
    sent_at: str | None


class DeadlineInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str
    time: str | None
    time_zone: str


class TaskChangeResult(TaskResult):
    changed: bool


class TaskDetailResult(TaskResult):
    reminders: list[ReminderResult]


def _instant(value: datetime) -> str:
    return value.isoformat()


def _deadline(deadline: Deadline | None) -> DeadlineResult | None:
    if deadline is None:
        return None
    local = deadline.at.astimezone(ZoneInfo(deadline.zone))
    return DeadlineResult(
        at=_instant(deadline.at),
        date=local.date().isoformat(),
        time=local.time().isoformat(timespec="minutes") if deadline.time_given else None,
        time_zone=deadline.zone,
    )


def _work(work: WorkTime | None) -> WorkResult | None:
    if work is None:
        return None
    return WorkResult(start=_instant(work.start), minutes=work.minutes, time_zone=work.zone)


def _task(task: Task) -> dict:
    return {
        "id": task.id,
        "title": task.title,
        "state": task.state,
        "source": task.source,
        "deadline": _deadline(task.deadline),
        "work": _work(task.work),
        "created_at": _instant(task.created_at),
        "updated_at": _instant(task.updated_at),
    }


def _reminder(reminder: Reminder) -> ReminderResult:
    return ReminderResult(
        kind=reminder.kind,
        fire_at=_instant(reminder.fire_at),
        sent_at=None if reminder.sent_at is None else _instant(reminder.sent_at),
    )


def build_server(settings: Settings) -> MCPServer:
    zone = config.home_zone(settings)
    open_store(settings).close()

    def list_tasks(status: str, after: str | None = None) -> TaskPageResult:
        store = open_store(settings)
        try:
            page = reads.list_tasks(store, status, after, zone=zone)
        except reads.ReadRefused as error:
            raise ToolError(error.code) from None
        finally:
            store.close()
        return TaskPageResult(
            tasks=[TaskResult(**_task(task)) for task in page.tasks],
            next_after=page.next_after,
        )

    def get_task(id: str) -> TaskDetailResult:
        store = open_store(settings)
        try:
            record = reads.task_record(store, id)
        except reads.ReadRefused as error:
            raise ToolError(error.code) from None
        finally:
            store.close()
        return TaskDetailResult(
            **_task(record.task),
            reminders=[_reminder(r) for r in record.reminders],
        )

    def write(call, *arguments, **keywords) -> TaskChangeResult:
        store = open_store(settings)
        try:
            outcome = call(store, *arguments, **keywords)
        except writes.WriteRefused as error:
            raise ToolError(error.code) from None
        finally:
            store.close()
        return TaskChangeResult(**_task(outcome.task), changed=outcome.changed)

    def create_task(
        title: str, request_key: str, deadline: DeadlineInput | None = None
    ) -> TaskChangeResult:
        given = None if deadline is None else deadline.model_dump()
        return write(writes.create_task, title=title, deadline=given, request_key=request_key)

    def complete_task(id: str, request_key: str) -> TaskChangeResult:
        return write(writes.complete_task, id, request_key=request_key)

    def cancel_task(id: str, request_key: str) -> TaskChangeResult:
        return write(writes.cancel_task, id, request_key=request_key)

    server = MCPServer(name=SERVER_NAME, instructions=INSTRUCTIONS, log_level="CRITICAL")
    hints = ToolAnnotations(
        read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
    )
    server.add_tool(list_tasks, description=LIST_TASKS, annotations=hints, structured_output=True)
    server.add_tool(get_task, description=GET_TASK, annotations=hints, structured_output=True)
    changes = ToolAnnotations(
        read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False
    )
    for function, description in (
        (create_task, CREATE_TASK),
        (complete_task, COMPLETE_TASK),
        (cancel_task, CANCEL_TASK),
    ):
        server.add_tool(
            function, description=description, annotations=changes, structured_output=True
        )
    return server


def serve(server: MCPServer) -> None:
    server.run("stdio")
