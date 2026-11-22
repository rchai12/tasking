import fcntl
import json
import os
import re
import sqlite3
from collections.abc import Collection, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import cast

from docket import (
    _store_audit,
    _store_digests,
    _store_keys,
    _store_links,
    _store_migrate,
    _store_posts,
    _store_reminders,
    _store_tasks,
    domain,
    serialization,
)
from docket.config import Settings, prepare_data_dir
from docket.deadlines import INSTANT_MESSAGE, Deadline, DeadlineError, WorkTime
from docket.reminder_plan import PlannedReminder
from docket.schema import MIGRATIONS as MIGRATIONS
from docket.schema import SCHEMA_VERSION as SCHEMA_VERSION

DB_FILENAME = "docket.sqlite3"
SCHEMA_MESSAGE = "unsupported schema version"
TRANSACTION_MESSAGE = "a write needs a transaction"
NESTED_MESSAGE = "a transaction is already open"
UNKNOWN_TASK_MESSAGE = "unknown task"
UNKNOWN_LINK_MESSAGE = "unknown link"

_ROW_ID = re.compile(r"[tlrpd]([1-9][0-9]*)")


class _Unchanged:
    pass


UNCHANGED = _Unchanged()


class StoreError(Exception):
    pass


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    state: str
    deadline: Deadline | None
    work: WorkTime | None
    source: str
    provider: str | None
    message_id: str | None
    link: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class AuditEntry:
    task_id: str
    at: datetime
    action: str
    actor: str
    before: dict[str, object]
    after: dict[str, object]


@dataclass(frozen=True)
class Link:
    id: str
    task_id: str
    provider: str
    message_id: str
    link: str
    created_at: datetime


@dataclass(frozen=True)
class Reminder:
    id: str
    task_id: str
    kind: str
    fire_at: datetime
    planned_at: datetime
    claimed_at: datetime | None
    sent_at: datetime | None
    voided_at: datetime | None


@dataclass(frozen=True)
class Post:
    id: str
    task_id: str
    key: str
    kind: str
    missed: int
    reminder_ids: tuple[str, ...]
    queued_at: datetime
    claimed_at: datetime | None
    sent_at: datetime | None


@dataclass(frozen=True)
class DailyDigest:
    id: str
    day: date
    key: str
    task_ids: tuple[str, ...]
    queued_at: datetime
    claimed_at: datetime | None
    sent_at: datetime | None


@dataclass(frozen=True)
class RequestKey:
    client: str
    key: str
    request: dict[str, object]
    task_id: str
    link_id: str | None
    created_at: datetime


def _statements(script: str) -> list[str]:
    statements: list[str] = []
    pending = ""
    for line in script.splitlines(keepends=True):
        pending += line
        if sqlite3.complete_statement(pending):
            statements.append(pending.strip())
            pending = ""
    return statements


def _instant(at: datetime) -> str:
    return at.isoformat(timespec="microseconds")


def _json(value: dict[str, object]) -> str:
    return serialization.canonical_json(value)


def _deadline_values(deadline: Deadline | None) -> tuple[str | None, str | None, int | None]:
    if deadline is None:
        return None, None, None
    return _instant(deadline.at), deadline.zone, int(deadline.time_given)


def _work_values(work: WorkTime | None) -> tuple[str | None, int | None, str | None]:
    if work is None:
        return None, None, None
    return _instant(work.start), work.minutes, work.zone


def _row_number(prefix: str, value: str) -> int | None:
    found = _ROW_ID.fullmatch(value)
    if found is None or value[0] != prefix:
        return None
    return int(found.group(1))


def _utc(value: str | None, label: str, identifier: str) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise StoreError(f"invalid stored {label}: {identifier}") from None
    if parsed.tzinfo is not UTC:
        raise StoreError(f"invalid stored {label}: {identifier}") from None
    return parsed


def _stored_object(text: str, label: str, identifier: str) -> dict[str, object]:
    try:
        found = json.loads(text)
    except ValueError:
        raise StoreError(f"invalid stored {label}: {identifier}") from None
    if not isinstance(found, dict):
        raise StoreError(f"invalid stored {label}: {identifier}") from None
    return found


def _check_retry_key(key: object, message: str) -> None:
    if not domain.valid_request_key(key):
        raise StoreError(message)


def _digest_day(day: object) -> date:
    if isinstance(day, datetime) or not isinstance(day, date):
        raise StoreError("invalid digest day")
    return day


class Store:
    def __init__(self, path: Path) -> None:
        gate = _startup_gate(path)
        try:
            self._in_transaction = False
            opened = False
            try:
                try:
                    os.close(os.open(path, os.O_CREAT | os.O_RDWR, 0o600))
                except OSError:
                    raise StoreError("store startup unavailable") from None
                self._connection = sqlite3.connect(path, isolation_level=None)
                opened = True
                self._connection.row_factory = sqlite3.Row
                path.chmod(0o600)
                for suffix in ("-wal", "-shm"):
                    try:
                        path.with_name(path.name + suffix).chmod(0o600)
                    except FileNotFoundError:
                        pass
                self._connection.execute("PRAGMA busy_timeout = 5000")
                self._connection.execute("PRAGMA foreign_keys = ON")
                self._connection.execute("PRAGMA journal_mode = WAL")
                _store_migrate.migrate(self)
            except BaseException:
                if opened:
                    self.close()
                raise
        finally:
            _release_gate(gate)

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        if self._in_transaction:
            raise StoreError(NESTED_MESSAGE)
        self._connection.execute("BEGIN IMMEDIATE")
        self._in_transaction = True
        try:
            yield
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise
        else:
            self._connection.execute("COMMIT")
        finally:
            self._in_transaction = False

    def insert_task(
        self,
        *,
        title: str,
        state: str,
        deadline: Deadline | None,
        work: WorkTime | None,
        source: str,
        provider: str | None,
        message_id: str | None,
        link: str | None,
        at: datetime,
    ) -> Task:
        self._require_write(at)
        deadline_at, deadline_zone, deadline_time_given = _deadline_values(deadline)
        work_start, work_minutes, work_zone = _work_values(work)
        instant = _instant(at)
        cursor = _store_tasks.insert_task(
            self._connection,
            title=title,
            state=state,
            deadline_at=deadline_at,
            deadline_zone=deadline_zone,
            deadline_time_given=deadline_time_given,
            work_start=work_start,
            work_minutes=work_minutes,
            work_zone=work_zone,
            source=source,
            provider=provider,
            message_id=message_id,
            link=link,
            created_at=instant,
            updated_at=instant,
        )
        return self._read_task(int(cursor.lastrowid))

    def update_task(
        self,
        task_id: str,
        *,
        at: datetime,
        title: str | _Unchanged = UNCHANGED,
        state: str | _Unchanged = UNCHANGED,
        deadline: Deadline | None | _Unchanged = UNCHANGED,
        work: WorkTime | None | _Unchanged = UNCHANGED,
    ) -> Task:
        self._require_write(at)
        number = self._require_task(task_id)
        fields: dict[str, object] = {}
        if title is not UNCHANGED:
            fields["title"] = title
        if state is not UNCHANGED:
            fields["state"] = state
        if deadline is not UNCHANGED:
            deadline_at, deadline_zone, deadline_time_given = _deadline_values(deadline)
            fields["deadline_at"] = deadline_at
            fields["deadline_zone"] = deadline_zone
            fields["deadline_time_given"] = deadline_time_given
        if work is not UNCHANGED:
            work_start, work_minutes, work_zone = _work_values(work)
            fields["work_start"] = work_start
            fields["work_minutes"] = work_minutes
            fields["work_zone"] = work_zone
        _store_tasks.update_task(self._connection, number, _instant(at), fields)
        return self._read_task(number)

    def append_audit(
        self,
        task_id: str,
        *,
        at: datetime,
        action: str,
        actor: str,
        before: dict[str, object],
        after: dict[str, object],
    ) -> AuditEntry:
        self._require_write(at)
        number = self._require_task(task_id)
        _store_audit.insert_audit(
            self._connection,
            number,
            _instant(at),
            action,
            actor,
            _json(before),
            _json(after),
        )
        return AuditEntry(
            task_id=task_id,
            at=at,
            action=action,
            actor=actor,
            before=before,
            after=after,
        )

    def task(self, task_id: str) -> Task | None:
        number = _row_number("t", task_id)
        if number is None:
            return None
        rows = _store_tasks.select_task(self._connection, number)
        if not rows:
            return None
        return self._task_from(rows[0])

    def tasks(self, states: Collection[str] | None = None) -> list[Task]:
        if states is None:
            rows = _store_tasks.select_tasks(self._connection)
        elif len(states) == 0:
            return []
        else:
            rows = _store_tasks.select_tasks_in_states(self._connection, tuple(states))
        return [self._task_from(row) for row in rows]

    def audit(self, task_id: str) -> list[AuditEntry]:
        number = _row_number("t", task_id)
        if number is None:
            return []
        rows = _store_audit.select_audit(self._connection, number)
        return [
            AuditEntry(
                task_id=task_id,
                at=cast(datetime, _utc(row["at"], "audit entry", task_id)),
                action=row["action"],
                actor=row["actor"],
                before=_stored_object(row["before"], "audit entry", task_id),
                after=_stored_object(row["after"], "audit entry", task_id),
            )
            for row in rows
        ]

    def insert_link(
        self,
        task_id: str,
        *,
        provider: str,
        message_id: str,
        link: str,
        at: datetime,
    ) -> Link:
        self._require_write(at)
        number = self._require_task(task_id)
        cursor = _store_links.insert_link(
            self._connection, number, provider, message_id, link, _instant(at)
        )
        return self._read_link(int(cursor.lastrowid))

    def links(self, task_id: str) -> list[Link]:
        number = _row_number("t", task_id)
        if number is None:
            return []
        rows = _store_links.select_links(self._connection, number)
        return [self._link_from(row) for row in rows]

    def insert_request_key(
        self,
        *,
        client: str,
        key: str,
        request: dict[str, object],
        task_id: str,
        link_id: str | None,
        at: datetime,
    ) -> RequestKey:
        self._require_write(at)
        task_number = self._require_task(task_id)
        link_number = None if link_id is None else self._require_link(link_id)
        _store_keys.insert_request_key(
            self._connection,
            client,
            key,
            _json(request),
            task_number,
            link_number,
            _instant(at),
        )
        return RequestKey(
            client=client,
            key=key,
            request=request,
            task_id=task_id,
            link_id=link_id,
            created_at=at,
        )

    def request_key(self, client: str, key: str) -> RequestKey | None:
        row = _store_keys.select_request_key(self._connection, client, key)
        if row is None:
            return None
        task_id = f"t{row['task']}"
        return RequestKey(
            client=row["client"],
            key=row["key"],
            request=_stored_object(row["request"], "request key", task_id),
            task_id=task_id,
            link_id=None if row["link"] is None else f"l{row['link']}",
            created_at=cast(datetime, _utc(row["created_at"], "request key", task_id)),
        )

    def insert_reminders(
        self,
        task_id: str,
        plans: tuple[PlannedReminder, ...],
        *,
        at: datetime,
    ) -> list[Reminder]:
        self._require_write(at)
        number = self._require_task(task_id)
        return self._write_reminders(task_id, number, plans, at)

    def void_reminders(
        self,
        task_id: str,
        *,
        at: datetime,
        kinds: Collection[str] | None = None,
    ) -> None:
        self._require_write(at)
        number = self._require_task(task_id)
        selected = domain.REMINDER_KINDS if kinds is None else tuple(kinds)
        for kind in selected:
            if not isinstance(kind, str) or kind not in domain.REMINDER_KINDS:
                raise StoreError("invalid reminder kind")
        if not selected:
            return
        _store_reminders.void_reminders(self._connection, number, _instant(at), selected)

    def reminders(self, task_id: str) -> list[Reminder]:
        number = _row_number("t", task_id)
        if number is None:
            return []
        return [
            self._reminder_from(row)
            for row in _store_reminders.select_reminders(self._connection, number)
        ]

    def _write_reminders(
        self,
        task_id: str,
        number: int,
        plans: tuple[PlannedReminder, ...],
        at: datetime,
    ) -> list[Reminder]:
        for plan in plans:
            if not isinstance(plan.kind, str) or plan.kind not in domain.REMINDER_KINDS:
                raise StoreError("invalid reminder kind")
            if plan.fire_at.tzinfo is not UTC:
                raise StoreError(INSTANT_MESSAGE)
        written: list[Reminder] = []
        for plan in plans:
            cursor = _store_reminders.insert_reminder(
                self._connection,
                number,
                plan.kind,
                _instant(plan.fire_at),
                _instant(at),
            )
            written.append(
                Reminder(
                    id=f"r{cursor.lastrowid}",
                    task_id=task_id,
                    kind=plan.kind,
                    fire_at=plan.fire_at,
                    planned_at=at,
                    claimed_at=None,
                    sent_at=None,
                    voided_at=None,
                )
            )
        return written

    def _reminder_from(self, row: sqlite3.Row) -> Reminder:
        identifier = f"r{row['number']}"
        return Reminder(
            id=identifier,
            task_id=f"t{row['task']}",
            kind=row["kind"],
            fire_at=_utc(row["fire_at"], "reminder time", identifier),
            planned_at=_utc(row["planned_at"], "reminder time", identifier),
            claimed_at=_utc(row["claimed_at"], "reminder time", identifier),
            sent_at=_utc(row["sent_at"], "reminder time", identifier),
            voided_at=_utc(row["voided_at"], "reminder time", identifier),
        )

    def _require_write(self, at: datetime) -> None:
        if not self._in_transaction:
            raise StoreError(TRANSACTION_MESSAGE)
        if at.tzinfo is not UTC:
            raise StoreError(INSTANT_MESSAGE)

    def _require_task(self, task_id: str) -> int:
        number = _row_number("t", task_id)
        if number is None or not self._exists(number):
            raise StoreError(UNKNOWN_TASK_MESSAGE)
        return number

    def _exists(self, number: int) -> bool:
        return _store_tasks.select_existence(self._connection, number) is not None

    def _require_link(self, link_id: str) -> int:
        number = _row_number("l", link_id)
        if number is None or not self._link_exists(number):
            raise StoreError(UNKNOWN_LINK_MESSAGE)
        return number

    def _link_exists(self, number: int) -> bool:
        return _store_links.select_existence(self._connection, number) is not None

    def _read_link(self, number: int) -> Link:
        row = _store_links.select_link(self._connection, number)
        return self._link_from(cast(sqlite3.Row, row))

    def _link_from(self, row: sqlite3.Row) -> Link:
        identifier = f"l{row['number']}"
        return Link(
            id=identifier,
            task_id=f"t{row['task']}",
            provider=row["provider"],
            message_id=row["message_id"],
            link=row["link"],
            created_at=cast(datetime, _utc(row["created_at"], "link", identifier)),
        )

    def _read_task(self, number: int) -> Task:
        rows = _store_tasks.select_task(self._connection, number)
        return self._task_from(rows[0])

    def _task_from(self, row: sqlite3.Row) -> Task:
        task_id = f"t{row['number']}"
        deadline_at = _utc(row["deadline_at"], "task time", task_id)
        work_start = _utc(row["work_start"], "task time", task_id)
        created_at = cast(datetime, _utc(row["created_at"], "task time", task_id))
        updated_at = cast(datetime, _utc(row["updated_at"], "task time", task_id))
        try:
            deadline = None
            if deadline_at is not None:
                deadline = Deadline(
                    deadline_at, row["deadline_zone"], bool(row["deadline_time_given"])
                )
            work = None
            if work_start is not None:
                work = WorkTime(work_start, row["work_minutes"], row["work_zone"])
        except DeadlineError:
            raise StoreError(f"invalid stored task time: {task_id}") from None
        return Task(
            id=task_id,
            title=row["title"],
            state=row["state"],
            deadline=deadline,
            work=work,
            source=row["source"],
            provider=row["provider"],
            message_id=row["message_id"],
            link=row["link"],
            created_at=created_at,
            updated_at=updated_at,
        )

    def due_reminders(self, at: datetime) -> list[Reminder]:
        self._require_utc(at)
        return [
            self._reminder_from(row)
            for row in _store_reminders.select_due_reminders(self._connection, _instant(at))
        ]

    def queue_post(
        self,
        task_id: str,
        reminder_ids: tuple[str, ...],
        *,
        key: str,
        kind: str,
        missed: int,
        at: datetime,
    ) -> Post:
        self._require_write(at)
        task = self._require_task(task_id)
        _check_retry_key(key, "invalid post key")
        if not isinstance(kind, str) or kind not in domain.REMINDER_KINDS:
            raise StoreError("invalid reminder kind")
        if (
            isinstance(missed, bool)
            or not isinstance(missed, int)
            or not 0 <= missed <= len(reminder_ids)
        ):
            raise StoreError("invalid missed count")
        if not reminder_ids:
            raise StoreError("a post needs a reminder")
        numbers: list[int] = []
        seen: set[int] = set()
        for reminder_id in reminder_ids:
            number = _row_number("r", reminder_id)
            if number is None:
                raise StoreError("invalid reminder id")
            if number in seen or not _store_reminders.pending_reminder(
                self._connection, number, task
            ):
                raise StoreError(f"reminder not pending: {reminder_id}")
            seen.add(number)
            numbers.append(number)
        instant = _instant(at)
        cursor = _store_posts.insert_post(self._connection, task, key, kind, missed, instant)
        post_number = int(cursor.lastrowid)
        for number in numbers:
            _store_posts.insert_post_reminder(self._connection, post_number, number)
        _store_reminders.claim_reminders(self._connection, tuple(numbers), instant)
        return Post(
            id=f"p{post_number}",
            task_id=task_id,
            key=key,
            kind=kind,
            missed=missed,
            reminder_ids=reminder_ids,
            queued_at=at,
            claimed_at=None,
            sent_at=None,
        )

    def claim_posts(self, *, at: datetime, stale_before: datetime) -> list[Post]:
        self._require_write(at)
        self._require_utc(stale_before)
        rows = _store_posts.claim_posts(self._connection, _instant(at), _instant(stale_before))
        return [self._post_from(row) for row in sorted(rows, key=lambda row: int(row["number"]))]

    def release_post(self, post_id: str, *, claimed_at: datetime) -> None:
        self._require_write(claimed_at)
        number = self._require_post(post_id)
        _store_posts.release_post(self._connection, number, _instant(claimed_at))

    def mark_post_sent(self, post_id: str, *, at: datetime) -> None:
        self._require_write(at)
        number = self._require_post(post_id)
        cursor = _store_posts.mark_post_sent(self._connection, number, _instant(at))
        if cursor.rowcount == 0:
            return
        links = _store_posts.select_post_reminders(self._connection, number)
        if not links:
            return
        _store_reminders.mark_reminders_sent(
            self._connection,
            tuple(int(row["reminder"]) for row in links),
            _instant(at),
        )

    def posts(self, task_id: str) -> list[Post]:
        number = _row_number("t", task_id)
        if number is None:
            return []
        return [self._post_from(row) for row in _store_posts.select_posts(self._connection, number)]

    def _require_post(self, post_id: str) -> int:
        number = _row_number("p", post_id)
        if number is None or _store_posts.select_post(self._connection, number) is None:
            raise StoreError("unknown post")
        return number

    def _post_from(self, row: sqlite3.Row) -> Post:
        identifier = f"p{row['number']}"
        queued_at = _utc(row["queued_at"], "post time", identifier)
        if queued_at is None:
            raise StoreError(f"invalid stored post time: {identifier}")
        links = _store_posts.select_post_reminders(self._connection, int(row["number"]))
        return Post(
            id=identifier,
            task_id=f"t{row['task']}",
            key=row["key"],
            kind=row["kind"],
            missed=int(row["missed"]),
            reminder_ids=tuple(f"r{link['reminder']}" for link in links),
            queued_at=queued_at,
            claimed_at=_utc(row["claimed_at"], "post time", identifier),
            sent_at=_utc(row["sent_at"], "post time", identifier),
        )

    def _require_utc(self, at: datetime) -> None:
        if at.tzinfo is not UTC:
            raise StoreError(INSTANT_MESSAGE)

    def digest(self, day: date) -> DailyDigest | None:
        row = _store_digests.select_digest(self._connection, _digest_day(day).isoformat())
        if row is None:
            return None
        return self._digest_from(row)

    def queue_digest(
        self, day: date, task_ids: tuple[str, ...], *, key: str, at: datetime
    ) -> DailyDigest:
        self._require_write(at)
        home = _digest_day(day)
        _check_retry_key(key, "invalid digest key")
        if not task_ids:
            raise StoreError("a digest needs a task")
        seen: set[int] = set()
        numbers: list[int] = []
        for task_id in task_ids:
            number = _row_number("t", task_id)
            if number is None:
                raise StoreError("invalid task id")
            task = self.task(task_id)
            if task is None or task.state not in domain.OPEN_STATES or number in seen:
                raise StoreError(f"task not open: {task_id}")
            seen.add(number)
            numbers.append(number)
        if _store_digests.select_digest(self._connection, home.isoformat()) is not None:
            raise StoreError(f"digest already queued: {home.isoformat()}")
        cursor = _store_digests.insert_digest(self._connection, home.isoformat(), key, _instant(at))
        digest = int(cursor.lastrowid)
        for number in numbers:
            _store_digests.insert_digest_task(self._connection, digest, number)
        row = _store_digests.select_digest_by_number(self._connection, digest)
        return self._digest_from(row)

    def claim_digest(
        self, day: date, *, at: datetime, stale_before: datetime, overdue_before: datetime
    ) -> DailyDigest | None:
        self._require_write(at)
        self._require_utc(stale_before)
        self._require_utc(overdue_before)
        home = _digest_day(day)
        row = _store_digests.claim_digest(
            self._connection,
            home.isoformat(),
            _instant(at),
            _instant(stale_before),
            _instant(overdue_before),
            domain.OPEN_STATES,
        )
        if row is None:
            return None
        return self._digest_from(row)

    def release_digest(self, digest_id: str, *, claimed_at: datetime) -> None:
        self._require_write(claimed_at)
        number = self._require_digest(digest_id)
        _store_digests.release_digest(self._connection, number, _instant(claimed_at))

    def mark_digest_sent(self, digest_id: str, *, at: datetime) -> None:
        self._require_write(at)
        number = self._require_digest(digest_id)
        _store_digests.mark_digest_sent(self._connection, number, _instant(at))

    def _require_digest(self, digest_id: str) -> int:
        number = _row_number("d", digest_id)
        if (
            number is None
            or _store_digests.select_digest_by_number(self._connection, number) is None
        ):
            raise StoreError("unknown digest")
        return number

    def _digest_from(self, row: sqlite3.Row) -> DailyDigest:
        identifier = f"d{row['number']}"
        queued_at = _utc(row["queued_at"], "digest time", identifier)
        if queued_at is None:
            raise StoreError(f"invalid stored digest time: {identifier}")
        members = _store_digests.select_digest_tasks(self._connection, int(row["number"]))
        return DailyDigest(
            id=identifier,
            day=date.fromisoformat(row["day"]),
            key=row["key"],
            task_ids=tuple(f"t{member['task']}" for member in members),
            queued_at=queued_at,
            claimed_at=_utc(row["claimed_at"], "digest time", identifier),
            sent_at=_utc(row["sent_at"], "digest time", identifier),
        )


def _startup_gate(path: Path) -> int:
    lock = path.with_name(path.name + ".startup.lock")
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_RDWR, 0o600)
    except OSError:
        raise StoreError("store startup unavailable") from None
    try:
        os.chmod(lock, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
    except OSError:
        os.close(descriptor)
        raise StoreError("store startup unavailable") from None
    return descriptor


def _release_gate(descriptor: int) -> None:
    fcntl.flock(descriptor, fcntl.LOCK_UN)
    os.close(descriptor)


def open_store(settings: Settings) -> Store:
    return Store(prepare_data_dir(settings) / DB_FILENAME)
