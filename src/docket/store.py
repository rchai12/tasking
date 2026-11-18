import fcntl
import json
import os
import re
import sqlite3
from collections.abc import Collection, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, cast

from docket import (
    _store_audit,
    _store_keys,
    _store_links,
    _store_reminders,
    _store_tasks,
    domain,
    serialization,
)
from docket.config import Settings, prepare_data_dir
from docket.deadlines import INSTANT_MESSAGE, Deadline, DeadlineError, WorkTime
from docket.references import LINK_MAX, MESSAGE_ID_MAX, valid_reference
from docket.schema import MIGRATIONS, SCHEMA_VERSION

if TYPE_CHECKING:
    from docket.reminders import PlannedReminder

DB_FILENAME = "docket.sqlite3"
SCHEMA_MESSAGE = "unsupported schema version"
TRANSACTION_MESSAGE = "a write needs a transaction"
NESTED_MESSAGE = "a transaction is already open"
UNKNOWN_TASK_MESSAGE = "unknown task"
UNKNOWN_LINK_MESSAGE = "unknown link"

_TASK_ID = re.compile(r"t[1-9][0-9]*")
_LINK_ID = re.compile(r"l[1-9][0-9]*")


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


def _number(task_id: str) -> int | None:
    if _TASK_ID.fullmatch(task_id) is None:
        return None
    return int(task_id[1:])


def _link_number(link_id: str) -> int | None:
    if _LINK_ID.fullmatch(link_id) is None:
        return None
    return int(link_id[1:])


class Store:
    def __init__(self, path: Path) -> None:
        gate = _startup_gate(path)
        try:
            self._in_transaction = False
            opened = False
            try:
                self._connection = sqlite3.connect(path, isolation_level=None)
                opened = True
                self._connection.row_factory = sqlite3.Row
                path.chmod(0o600)
                self._connection.execute("PRAGMA busy_timeout = 5000")
                self._connection.execute("PRAGMA foreign_keys = ON")
                self._connection.execute("PRAGMA journal_mode = WAL")
                self._migrate()
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
            (
                title,
                state,
                deadline_at,
                deadline_zone,
                deadline_time_given,
                work_start,
                work_minutes,
                work_zone,
                source,
                provider,
                message_id,
                link,
                instant,
                instant,
            ),
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
        number = _number(task_id)
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
        number = _number(task_id)
        if number is None:
            return []
        rows = _store_audit.select_audit(self._connection, number)
        return [
            AuditEntry(
                task_id=task_id,
                at=datetime.fromisoformat(row["at"]),
                action=row["action"],
                actor=row["actor"],
                before=json.loads(row["before"]),
                after=json.loads(row["after"]),
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
        number = _number(task_id)
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
        return RequestKey(
            client=row["client"],
            key=row["key"],
            request=json.loads(row["request"]),
            task_id=f"t{row['task']}",
            link_id=None if row["link"] is None else f"l{row['link']}",
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def _migrate(self) -> None:
        while True:
            rebuild = False
            with self.transaction():
                version = self._user_version()
                if version > SCHEMA_VERSION:
                    raise StoreError(f"{SCHEMA_MESSAGE}: {version}")
                if version == SCHEMA_VERSION:
                    return
                if version == 2:
                    rebuild = True
                else:
                    self._apply_migration(version)
            if rebuild:
                self._migrate_references()

    def insert_reminders(
        self,
        task_id: str,
        plans: tuple["PlannedReminder", ...],
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
        number = _number(task_id)
        if number is None:
            return []
        return [
            self._reminder_from(row)
            for row in _store_reminders.select_reminders(self._connection, number)
        ]

    def _apply_migration(self, version: int) -> None:
        for statement in _statements(MIGRATIONS[version]):
            self._connection.execute(statement)
        if version == 3:
            self._backfill_reminders()
        self._connection.execute(f"PRAGMA user_version = {version + 1}")

    def _user_version(self) -> int:
        found = cast(sqlite3.Row, self._connection.execute("PRAGMA user_version").fetchone())
        return int(found[0])

    def _migrate_references(self) -> None:
        self._connection.execute("PRAGMA foreign_keys = OFF")
        try:
            with self.transaction():
                version = self._user_version()
                if version > SCHEMA_VERSION:
                    raise StoreError(f"{SCHEMA_MESSAGE}: {version}")
                if version == 2:
                    self._refuse_invalid_references()
                    for statement in _statements(MIGRATIONS[2]):
                        self._connection.execute(statement)
                    if self._connection.execute("PRAGMA foreign_key_check").fetchall():
                        raise StoreError("invalid reference migration")
                    self._connection.execute("PRAGMA user_version = 3")
        finally:
            self._connection.execute("PRAGMA foreign_keys = ON")

    def _refuse_invalid_references(self) -> None:
        tasks = self._connection.execute(
            "SELECT number, message_id, link FROM tasks WHERE source = 'email' ORDER BY number"
        )
        for row in tasks:
            self._refuse_reference(f"t{row['number']}", row["message_id"], row["link"])
        links = self._connection.execute(
            "SELECT number, message_id, link FROM links ORDER BY number"
        )
        for row in links:
            self._refuse_reference(f"l{row['number']}", row["message_id"], row["link"])

    def _refuse_reference(self, identifier: str, message_id: object, link: object) -> None:
        if not valid_reference(message_id, MESSAGE_ID_MAX):
            raise StoreError(f"invalid stored reference: {identifier} message_id")
        if not valid_reference(link, LINK_MAX):
            raise StoreError(f"invalid stored reference: {identifier} link")

    def _backfill_reminders(self) -> None:
        from docket import reminders

        rows = self._connection.execute(
            "SELECT number, title, state, deadline_at, deadline_zone, deadline_time_given, "
            "work_start, work_minutes, work_zone, source, provider, message_id, link, "
            "created_at, updated_at FROM tasks WHERE state IN ("
            + ", ".join("?" for _ in domain.OPEN_STATES)
            + ") ORDER BY number",
            domain.OPEN_STATES,
        ).fetchall()
        for row in rows:
            task = self._task_from(row)
            try:
                plans = reminders.plan_reminders(task, task.updated_at)
            except OverflowError:
                raise StoreError(f"invalid reminder plan: {task.id}") from None
            self._write_reminders(task.id, int(row["number"]), plans, task.updated_at)

    def _write_reminders(
        self,
        task_id: str,
        number: int,
        plans: tuple["PlannedReminder", ...],
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
            fire_at=self._reminder_time(row["fire_at"], identifier),
            planned_at=self._reminder_time(row["planned_at"], identifier),
            claimed_at=self._reminder_time(row["claimed_at"], identifier),
            sent_at=self._reminder_time(row["sent_at"], identifier),
            voided_at=self._reminder_time(row["voided_at"], identifier),
        )

    def _reminder_time(self, value: str | None, identifier: str) -> datetime | None:
        if value is None:
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            raise StoreError(f"invalid stored reminder time: {identifier}") from None
        if parsed.tzinfo is not UTC:
            raise StoreError(f"invalid stored reminder time: {identifier}")
        return parsed

    def _require_write(self, at: datetime) -> None:
        if not self._in_transaction:
            raise StoreError(TRANSACTION_MESSAGE)
        if at.tzinfo is not UTC:
            raise StoreError(INSTANT_MESSAGE)

    def _require_task(self, task_id: str) -> int:
        number = _number(task_id)
        if number is None or not self._exists(number):
            raise StoreError(UNKNOWN_TASK_MESSAGE)
        return number

    def _exists(self, number: int) -> bool:
        return _store_tasks.select_existence(self._connection, number) is not None

    def _require_link(self, link_id: str) -> int:
        number = _link_number(link_id)
        if number is None or not self._link_exists(number):
            raise StoreError(UNKNOWN_LINK_MESSAGE)
        return number

    def _link_exists(self, number: int) -> bool:
        return _store_links.select_existence(self._connection, number) is not None

    def _read_link(self, number: int) -> Link:
        row = _store_links.select_link(self._connection, number)
        return self._link_from(cast(sqlite3.Row, row))

    def _link_from(self, row: sqlite3.Row) -> Link:
        return Link(
            id=f"l{row['number']}",
            task_id=f"t{row['task']}",
            provider=row["provider"],
            message_id=row["message_id"],
            link=row["link"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def _read_task(self, number: int) -> Task:
        rows = _store_tasks.select_task(self._connection, number)
        return self._task_from(rows[0])

    def _task_from(self, row: sqlite3.Row) -> Task:
        task_id = f"t{row['number']}"
        try:
            deadline = None
            if row["deadline_at"] is not None:
                deadline = Deadline(
                    datetime.fromisoformat(row["deadline_at"]),
                    row["deadline_zone"],
                    bool(row["deadline_time_given"]),
                )
            work = None
            if row["work_start"] is not None:
                work = WorkTime(
                    datetime.fromisoformat(row["work_start"]),
                    row["work_minutes"],
                    row["work_zone"],
                )
            created_at = datetime.fromisoformat(row["created_at"])
            updated_at = datetime.fromisoformat(row["updated_at"])
            if created_at.tzinfo is not UTC or updated_at.tzinfo is not UTC:
                raise DeadlineError(INSTANT_MESSAGE)
        except (ValueError, DeadlineError):
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
