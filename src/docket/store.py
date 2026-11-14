import json
import re
import sqlite3
from collections.abc import Collection, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from docket.config import Settings, prepare_data_dir
from docket.deadlines import INSTANT_MESSAGE, Deadline, WorkTime
from docket.schema import MIGRATIONS, SCHEMA_VERSION

DB_FILENAME = "docket.sqlite3"
SCHEMA_MESSAGE = "unsupported schema version"
TRANSACTION_MESSAGE = "a write needs a transaction"
NESTED_MESSAGE = "a transaction is already open"
UNKNOWN_TASK_MESSAGE = "unknown task"

_TASK_ID = re.compile(r"t[1-9][0-9]*")
_COLUMNS = (
    "number, title, state, deadline_at, deadline_zone, deadline_time_given, "
    "work_start, work_minutes, work_zone, source, provider, message_id, link, "
    "created_at, updated_at"
)


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
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


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


class Store:
    def __init__(self, path: Path) -> None:
        self._in_transaction = False
        self._connection = sqlite3.connect(path, isolation_level=None)
        self._connection.row_factory = sqlite3.Row
        path.chmod(0o600)
        self._connection.execute("PRAGMA busy_timeout = 5000")
        self._connection.execute("PRAGMA foreign_keys = ON")
        found = cast(sqlite3.Row, self._connection.execute("PRAGMA user_version").fetchone())
        version = int(found[0])
        if version > SCHEMA_VERSION:
            self.close()
            raise StoreError(f"{SCHEMA_MESSAGE}: {version}")
        self._connection.execute("PRAGMA journal_mode = WAL")
        self._migrate(version)

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
        cursor = self._connection.execute(
            "INSERT INTO tasks ("
            "title, state, deadline_at, deadline_zone, deadline_time_given, "
            "work_start, work_minutes, work_zone, source, provider, message_id, link, "
            "created_at, updated_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
        assignments = ["updated_at = ?"]
        parameters: list[object] = [_instant(at)]
        if title is not UNCHANGED:
            assignments.append("title = ?")
            parameters.append(title)
        if state is not UNCHANGED:
            assignments.append("state = ?")
            parameters.append(state)
        if deadline is not UNCHANGED:
            deadline_at, deadline_zone, deadline_time_given = _deadline_values(deadline)
            assignments.extend(["deadline_at = ?", "deadline_zone = ?", "deadline_time_given = ?"])
            parameters.extend([deadline_at, deadline_zone, deadline_time_given])
        if work is not UNCHANGED:
            work_start, work_minutes, work_zone = _work_values(work)
            assignments.extend(["work_start = ?", "work_minutes = ?", "work_zone = ?"])
            parameters.extend([work_start, work_minutes, work_zone])
        parameters.append(number)
        self._connection.execute(
            "UPDATE tasks SET " + ", ".join(assignments) + " WHERE number = ?",
            parameters,
        )
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
        self._connection.execute(
            "INSERT INTO audit_log (task, at, action, actor, before, after) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (number, _instant(at), action, actor, _json(before), _json(after)),
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
        rows = self._connection.execute(
            f"SELECT {_COLUMNS} FROM tasks WHERE number = ?",
            (number,),
        ).fetchall()
        if not rows:
            return None
        return self._task_from(rows[0])

    def tasks(self, states: Collection[str] | None = None) -> list[Task]:
        if states is None:
            rows = self._connection.execute(
                f"SELECT {_COLUMNS} FROM tasks ORDER BY number"
            ).fetchall()
        elif len(states) == 0:
            return []
        else:
            marks = ", ".join("?" for _ in states)
            rows = self._connection.execute(
                f"SELECT {_COLUMNS} FROM tasks WHERE state IN ({marks}) ORDER BY number",
                tuple(states),
            ).fetchall()
        return [self._task_from(row) for row in rows]

    def audit(self, task_id: str) -> list[AuditEntry]:
        number = _number(task_id)
        if number is None:
            return []
        rows = self._connection.execute(
            "SELECT at, action, actor, before, after FROM audit_log WHERE task = ? ORDER BY number",
            (number,),
        ).fetchall()
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

    def _migrate(self, version: int) -> None:
        while version < SCHEMA_VERSION:
            with self.transaction():
                for statement in _statements(MIGRATIONS[version]):
                    self._connection.execute(statement)
                self._connection.execute(f"PRAGMA user_version = {version + 1}")
            version += 1

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
        row = self._connection.execute(
            "SELECT 1 FROM tasks WHERE number = ?",
            (number,),
        ).fetchone()
        return row is not None

    def _read_task(self, number: int) -> Task:
        rows = self._connection.execute(
            f"SELECT {_COLUMNS} FROM tasks WHERE number = ?",
            (number,),
        ).fetchall()
        return self._task_from(rows[0])

    def _task_from(self, row: sqlite3.Row) -> Task:
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
        return Task(
            id=f"t{row['number']}",
            title=row["title"],
            state=row["state"],
            deadline=deadline,
            work=work,
            source=row["source"],
            provider=row["provider"],
            message_id=row["message_id"],
            link=row["link"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


def open_store(settings: Settings) -> Store:
    return Store(prepare_data_dir(settings) / DB_FILENAME)
