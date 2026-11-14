import unicodedata
from dataclasses import dataclass

from docket import clock
from docket.deadlines import Deadline, WorkTime
from docket.store import UNCHANGED, Store, Task

UNKNOWN_TASK = "unknown_task"
INVALID_TITLE = "invalid_title"
INVALID_SOURCE = "invalid_source"
INVALID_REFERENCE = "invalid_reference"
INVALID_ACTOR = "invalid_actor"
INVALID_ACTION = "invalid_action"
TASK_ENDED = "task_ended"
WORK_AFTER_DEADLINE = "work_after_deadline"

_SOURCES = {"email", "agent", "proposal", "owner"}
_ACTORS = {"owner", "agent", "email"}
_ACTIONS = {"start", "done", "cancel", "reopen"}
_PROVIDERS = {"gmail", "outlook", "yahoo"}
_ACTOR_FOR_SOURCE = {"email": "email", "agent": "agent", "proposal": "owner", "owner": "owner"}
_BAD_CATEGORIES = {"Cc", "Cf", "Zl", "Zp"}
_OPEN = {"open", "in_progress"}


class CoreError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Outcome:
    task: Task
    changed: bool


def check_title(title: object) -> None:
    if (
        not isinstance(title, str)
        or not 1 <= len(title) <= 100
        or title != title.strip()
        or any(unicodedata.category(character) in _BAD_CATEGORIES for character in title)
    ):
        raise CoreError(INVALID_TITLE)


def create_task(
    store: Store,
    *,
    title: object,
    source: str,
    deadline: Deadline | None = None,
    work: WorkTime | None = None,
    provider: str | None = None,
    message_id: str | None = None,
    link: str | None = None,
) -> Task:
    check_title(title)
    if source not in _SOURCES:
        raise CoreError(INVALID_SOURCE)
    _check_reference(source, provider, message_id, link)
    if _work_after_deadline(deadline, work):
        raise CoreError(WORK_AFTER_DEADLINE)
    at = clock.now()
    with store.transaction():
        task = store.insert_task(
            title=str(title),
            state="open",
            deadline=deadline,
            work=work,
            source=source,
            provider=provider,
            message_id=message_id,
            link=link,
            at=at,
        )
        store.append_audit(
            task.id,
            at=at,
            action="create",
            actor=_ACTOR_FOR_SOURCE[source],
            before={},
            after={
                "title": title,
                "state": "open",
                "deadline": _deadline_snapshot(deadline),
                "work": _work_snapshot(work),
                "source": source,
                "provider": provider,
                "message_id": message_id,
                "link": link,
            },
        )
        return task


def change_state(store: Store, task_id: str, action: str, *, actor: str) -> Outcome:
    if action not in _ACTIONS:
        raise CoreError(INVALID_ACTION)
    if actor not in _ACTORS:
        raise CoreError(INVALID_ACTOR)
    at = clock.now()
    with store.transaction():
        task = store.task(task_id)
        if task is None:
            raise CoreError(UNKNOWN_TASK)
        new_state = _next_state(task.state, action)
        if new_state is None:
            return Outcome(task, False)
        updated = store.update_task(task_id, at=at, state=new_state)
        store.append_audit(
            task_id,
            at=at,
            action=action,
            actor=actor,
            before={"state": task.state},
            after={"state": new_state},
        )
        return Outcome(updated, True)


def edit_task(
    store: Store,
    task_id: str,
    *,
    actor: str,
    title: object = UNCHANGED,
    deadline: object = UNCHANGED,
    work: object = UNCHANGED,
) -> Outcome:
    if actor not in _ACTORS:
        raise CoreError(INVALID_ACTOR)
    if title is not UNCHANGED:
        check_title(title)
    at = clock.now()
    with store.transaction():
        task = store.task(task_id)
        if task is None:
            raise CoreError(UNKNOWN_TASK)
        if task.state not in _OPEN:
            raise CoreError(TASK_ENDED)
        new_deadline = task.deadline if deadline is UNCHANGED else deadline
        new_work = task.work if work is UNCHANGED else work
        if _work_after_deadline(new_deadline, new_work):
            raise CoreError(WORK_AFTER_DEADLINE)
        fields: dict[str, object] = {}
        rows: list[tuple[str, dict[str, object], dict[str, object]]] = []
        if title is not UNCHANGED and title != task.title:
            fields["title"] = title
            rows.append(("retitle", {"title": task.title}, {"title": title}))
        if deadline is not UNCHANGED and new_deadline != task.deadline:
            fields["deadline"] = new_deadline
            rows.append(
                (
                    "deadline",
                    {"deadline": _deadline_snapshot(task.deadline)},
                    {"deadline": _deadline_snapshot(new_deadline)},
                )
            )
        if work is not UNCHANGED and new_work != task.work:
            fields["work"] = new_work
            rows.append(
                (
                    "work_time",
                    {"work": _work_snapshot(task.work)},
                    {"work": _work_snapshot(new_work)},
                )
            )
        if not rows:
            return Outcome(task, False)
        updated = store.update_task(task_id, at=at, **fields)
        for action, before, after in rows:
            store.append_audit(
                task_id, at=at, action=action, actor=actor, before=before, after=after
            )
        return Outcome(updated, True)


def _nonempty(value: object) -> bool:
    return isinstance(value, str) and value != ""


def _check_reference(source: str, provider: object, message_id: object, link: object) -> None:
    if source == "email":
        if not (_nonempty(message_id) and _nonempty(link) and provider in _PROVIDERS):
            raise CoreError(INVALID_REFERENCE)
        return
    if (provider, message_id, link) != (None, None, None):
        raise CoreError(INVALID_REFERENCE)


def _work_after_deadline(deadline: object, work: object) -> bool:
    return isinstance(deadline, Deadline) and isinstance(work, WorkTime) and work.end > deadline.at


def _next_state(state: str, action: str) -> str | None:
    if action == "reopen":
        if state in {"done", "cancelled"}:
            return "open"
        return None
    if action == "start":
        if state == "open":
            return "in_progress"
        if state == "in_progress":
            return None
        raise CoreError(TASK_ENDED)
    if action == "done":
        if state in _OPEN:
            return "done"
        if state == "done":
            return None
        raise CoreError(TASK_ENDED)
    if state in _OPEN:
        return "cancelled"
    if state == "cancelled":
        return None
    raise CoreError(TASK_ENDED)


def _deadline_snapshot(deadline: object) -> dict[str, object] | None:
    if not isinstance(deadline, Deadline):
        return None
    return {
        "at": deadline.at.isoformat(timespec="microseconds"),
        "zone": deadline.zone,
        "time_given": deadline.time_given,
    }


def _work_snapshot(work: object) -> dict[str, object] | None:
    if not isinstance(work, WorkTime):
        return None
    return {
        "start": work.start.isoformat(timespec="microseconds"),
        "minutes": work.minutes,
        "zone": work.zone,
    }
