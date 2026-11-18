import unicodedata
from dataclasses import dataclass, replace
from datetime import datetime
from typing import cast

from docket import clock, domain, serialization
from docket.deadlines import Deadline, WorkTime
from docket.references import LINK_MAX, MESSAGE_ID_MAX, valid_reference
from docket.reminders import plan_reminders
from docket.store import UNCHANGED, Link, Store, Task

UNKNOWN_TASK = "unknown_task"
INVALID_TITLE = "invalid_title"
INVALID_SOURCE = "invalid_source"
INVALID_REFERENCE = "invalid_reference"
INVALID_ACTOR = "invalid_actor"
INVALID_ACTION = "invalid_action"
TASK_ENDED = "task_ended"
WORK_AFTER_DEADLINE = "work_after_deadline"
INVALID_CLIENT = "invalid_client"
INVALID_KEY = "invalid_key"
KEY_REUSED = "key_reused"
INVALID_REMINDER_PLAN = "invalid_reminder_plan"

_SOURCES = domain.SOURCES
_CLIENTS = domain.CORE_CLIENTS
_ACTORS = domain.ACTORS
_ACTIONS = domain.STATE_ACTIONS
_PROVIDERS = domain.PROVIDERS
_ACTOR_FOR_SOURCE = domain.SOURCE_ACTORS
_BAD_CATEGORIES = domain.FORBIDDEN_TEXT_CATEGORIES
_OPEN = domain.OPEN_STATES


class CoreError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Outcome:
    task: Task
    changed: bool


@dataclass(frozen=True)
class LinkOutcome:
    link: Link
    changed: bool


def check_title(title: object) -> None:
    if (
        not isinstance(title, str)
        or not 1 <= len(title) <= domain.TITLE_MAX
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
        return _insert_open_task(
            store,
            title=title,
            source=source,
            deadline=deadline,
            work=work,
            provider=provider,
            message_id=message_id,
            link=link,
            at=at,
        )


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
        if action in ("done", "cancel"):
            store.void_reminders(task_id, at=at)
        elif action == "reopen":
            _persist_plan(store, updated, at)
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
        _replace_reminders(
            store,
            updated,
            at,
            deadline="deadline" in fields,
            work="work" in fields,
        )
        return Outcome(updated, True)


def create_task_once(
    store: Store,
    *,
    client: object,
    key: object,
    request: dict[str, object],
    title: object,
    source: str,
    deadline: Deadline | None = None,
    work: WorkTime | None = None,
    provider: str | None = None,
    message_id: str | None = None,
    link: str | None = None,
) -> Outcome:
    if not isinstance(client, str) or client not in _CLIENTS:
        raise CoreError(INVALID_CLIENT)
    _check_key(key)
    check_title(title)
    if not isinstance(source, str) or source != client:
        raise CoreError(INVALID_SOURCE)
    _check_reference(source, provider, message_id, link)
    if _work_after_deadline(deadline, work):
        raise CoreError(WORK_AFTER_DEADLINE)
    at = clock.now()
    with store.transaction():
        found = store.request_key(cast(str, client), cast(str, key))
        if found is not None:
            if found.link_id is None and _same_request(found.request, request):
                return Outcome(cast(Task, store.task(found.task_id)), False)
            raise CoreError(KEY_REUSED)
        task = _insert_open_task(
            store,
            title=title,
            source=source,
            deadline=deadline,
            work=work,
            provider=provider,
            message_id=message_id,
            link=link,
            at=at,
        )
        store.insert_request_key(
            client=cast(str, client),
            key=cast(str, key),
            request=request,
            task_id=task.id,
            link_id=None,
            at=at,
        )
        return Outcome(task, True)


def add_link(
    store: Store,
    task_id: str,
    *,
    client: object,
    key: object,
    request: dict[str, object],
    provider: object,
    message_id: object,
    link: object,
) -> LinkOutcome:
    if not isinstance(client, str) or client != "email":
        raise CoreError(INVALID_CLIENT)
    _check_key(key)
    _check_reference("email", provider, message_id, link)
    at = clock.now()
    with store.transaction():
        found = store.request_key("email", cast(str, key))
        if found is not None:
            if (
                found.link_id is not None
                and found.task_id == task_id
                and _same_request(found.request, request)
            ):
                made = {item.id: item for item in store.links(task_id)}
                return LinkOutcome(made[found.link_id], False)
            raise CoreError(KEY_REUSED)
        if store.task(task_id) is None:
            raise CoreError(UNKNOWN_TASK)
        created = store.insert_link(
            task_id,
            provider=cast(str, provider),
            message_id=cast(str, message_id),
            link=cast(str, link),
            at=at,
        )
        store.insert_request_key(
            client="email",
            key=cast(str, key),
            request=request,
            task_id=task_id,
            link_id=created.id,
            at=at,
        )
        return LinkOutcome(created, True)


def _insert_open_task(
    store: Store,
    *,
    title: object,
    source: str,
    deadline: Deadline | None,
    work: WorkTime | None,
    provider: str | None,
    message_id: str | None,
    link: str | None,
    at: datetime,
) -> Task:
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
    _persist_plan(store, task, at)
    return task


def _persist_plan(store: Store, task: Task, at: datetime) -> None:
    try:
        plans = plan_reminders(task, at)
    except OverflowError:
        raise CoreError(INVALID_REMINDER_PLAN) from None
    store.insert_reminders(task.id, plans, at=at)


def _replace_reminders(
    store: Store,
    task: Task,
    at: datetime,
    *,
    deadline: bool,
    work: bool,
) -> None:
    if deadline:
        store.void_reminders(task.id, at=at, kinds=("before", "due_soon", "due", "late"))
        if task.deadline is not None:
            _persist_plan(store, replace(task, work=None), at)
    if work:
        store.void_reminders(task.id, at=at, kinds=("start",))
        if task.work is not None:
            _persist_plan(store, replace(task, deadline=None), at)


def _check_key(key: object) -> None:
    if not isinstance(key, str) or not 1 <= len(key) <= domain.REQUEST_KEY_MAX:
        raise CoreError(INVALID_KEY)


def _same_request(stored: dict[str, object], request: dict[str, object]) -> bool:
    return serialization.canonical_json(stored) == serialization.canonical_json(request)


def _check_reference(source: str, provider: object, message_id: object, link: object) -> None:
    if source == "email":
        if not (
            isinstance(provider, str)
            and provider in _PROVIDERS
            and valid_reference(message_id, MESSAGE_ID_MAX)
            and valid_reference(link, LINK_MAX)
        ):
            raise CoreError(INVALID_REFERENCE)
        return
    if (provider, message_id, link) != (None, None, None):
        raise CoreError(INVALID_REFERENCE)


def _work_after_deadline(deadline: object, work: object) -> bool:
    return isinstance(deadline, Deadline) and isinstance(work, WorkTime) and work.end > deadline.at


def _next_state(state: str, action: str) -> str | None:
    if action == "reopen":
        if state in domain.ENDED_STATES:
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
