import re
from dataclasses import dataclass
from datetime import date, time

from docket.core import (
    INVALID_CLIENT,
    INVALID_SOURCE,
    KEY_REUSED,
    UNKNOWN_TASK,
    CoreError,
    add_link,
    create_task_once,
)
from docket.deadlines import Deadline, DeadlineError, make_deadline
from docket.store import Store

MISSING_KEY = "missing_key"
INVALID_BODY = "invalid_body"
INVALID_DEADLINE = "invalid_deadline"

_TASK_FIELDS = {"source", "title", "deadline", "provider", "message_id", "link"}
_TASK_TEXT = ("source", "title", "provider", "message_id", "link")
_LINK_FIELDS = {"source", "provider", "message_id", "link"}
_DEADLINE_FIELDS = {"date", "time", "time_zone"}
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_TIME = re.compile(r"[0-9]{2}:[0-9]{2}")
_TASK_STATUS = {KEY_REUSED: 409}
_LINK_STATUS = {KEY_REUSED: 409, UNKNOWN_TASK: 404}


class _BadDeadline(Exception):
    pass


@dataclass(frozen=True)
class Answer:
    status: int
    body: dict[str, object]


def accept_task(store: Store, *, client: object, key: str | None, body: object) -> Answer:
    if not _valid_key(key):
        return Answer(400, {"error": MISSING_KEY})
    if not isinstance(client, str) or client != "email":
        return Answer(422, {"error": INVALID_CLIENT})
    parsed = _object(body, _TASK_FIELDS, _TASK_TEXT)
    if parsed is None:
        return Answer(422, {"error": INVALID_BODY})
    try:
        deadline = _deadline(parsed["deadline"])
    except _BadDeadline:
        return Answer(422, {"error": INVALID_DEADLINE})
    try:
        outcome = create_task_once(
            store,
            client=client,
            key=key,
            request=parsed,
            title=parsed["title"],
            source=_text(parsed["source"]),
            deadline=deadline,
            provider=_text(parsed["provider"]),
            message_id=_text(parsed["message_id"]),
            link=_text(parsed["link"]),
        )
    except CoreError as error:
        return Answer(_TASK_STATUS.get(error.code, 422), {"error": error.code})
    status = 201 if outcome.changed else 200
    return Answer(status, {"id": outcome.task.id})


def accept_link(
    store: Store, task_id: str, *, client: object, key: str | None, body: object
) -> Answer:
    if not _valid_key(key):
        return Answer(400, {"error": MISSING_KEY})
    if not isinstance(client, str) or client != "email":
        return Answer(422, {"error": INVALID_CLIENT})
    if store.task(task_id) is None:
        return Answer(404, {"error": UNKNOWN_TASK})
    parsed = _object(body, _LINK_FIELDS, _LINK_FIELDS)
    if parsed is None:
        return Answer(422, {"error": INVALID_BODY})
    if parsed["source"] != "email":
        return Answer(422, {"error": INVALID_SOURCE})
    try:
        outcome = add_link(
            store,
            task_id,
            client=client,
            key=key,
            request=parsed,
            provider=parsed["provider"],
            message_id=parsed["message_id"],
            link=parsed["link"],
        )
    except CoreError as error:
        return Answer(_LINK_STATUS.get(error.code, 422), {"error": error.code})
    status = 201 if outcome.changed else 200
    return Answer(status, {"id": outcome.link.id})


def _valid_key(key: object) -> bool:
    return isinstance(key, str) and 1 <= len(key) <= 200


def _object(
    body: object, fields: set[str], text: tuple[str, ...] | set[str]
) -> dict[str, object] | None:
    if not isinstance(body, dict) or set(body) != fields:
        return None
    if any(not isinstance(body[name], str) for name in text):
        return None
    return body


def _text(value: object) -> str:
    if isinstance(value, str):
        return value
    raise _BadDeadline


def _deadline(value: object) -> Deadline | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != _DEADLINE_FIELDS:
        raise _BadDeadline
    try:
        return make_deadline(_day(value["date"]), _clock(value["time"]), _text(value["time_zone"]))
    except DeadlineError:
        raise _BadDeadline from None


def _day(value: object) -> date:
    text = _text(value)
    if _DATE.fullmatch(text) is None:
        raise _BadDeadline
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise _BadDeadline from None


def _clock(value: object) -> time | None:
    if value is None:
        return None
    text = _text(value)
    if _TIME.fullmatch(text) is None:
        raise _BadDeadline
    try:
        return time.fromisoformat(text)
    except ValueError:
        raise _BadDeadline from None
