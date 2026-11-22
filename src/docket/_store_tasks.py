"""Ordinary tasks SQL. The caller owns the connection and the transaction."""

import sqlite3
from collections.abc import Mapping, Sequence

_COLUMNS = (
    "title, state, deadline_at, deadline_zone, deadline_time_given, "
    "work_start, work_minutes, work_zone, source, provider, message_id, link, "
    "created_at, updated_at"
)
_SELECT = "number, " + _COLUMNS


def insert_task(
    connection: sqlite3.Connection,
    *,
    title: str,
    state: str,
    deadline_at: str | None,
    deadline_zone: str | None,
    deadline_time_given: int | None,
    work_start: str | None,
    work_minutes: int | None,
    work_zone: str | None,
    source: str,
    provider: str | None,
    message_id: str | None,
    link: str | None,
    created_at: str,
    updated_at: str,
) -> sqlite3.Cursor:
    return connection.execute(
        "INSERT INTO tasks (title, state, deadline_at, deadline_zone, deadline_time_given, "
        "work_start, work_minutes, work_zone, source, provider, message_id, link, "
        "created_at, updated_at) VALUES (:title, :state, :deadline_at, :deadline_zone, "
        ":deadline_time_given, :work_start, :work_minutes, :work_zone, :source, :provider, "
        ":message_id, :link, :created_at, :updated_at)",
        {
            "title": title,
            "state": state,
            "deadline_at": deadline_at,
            "deadline_zone": deadline_zone,
            "deadline_time_given": deadline_time_given,
            "work_start": work_start,
            "work_minutes": work_minutes,
            "work_zone": work_zone,
            "source": source,
            "provider": provider,
            "message_id": message_id,
            "link": link,
            "created_at": created_at,
            "updated_at": updated_at,
        },
    )


_UPDATABLE = (
    "title",
    "state",
    "deadline_at",
    "deadline_zone",
    "deadline_time_given",
    "work_start",
    "work_minutes",
    "work_zone",
)


def update_task(
    connection: sqlite3.Connection,
    number: int,
    updated_at: str,
    fields: Mapping[str, object],
) -> sqlite3.Cursor:
    if any(key not in _UPDATABLE for key in fields):
        raise ValueError("unknown task column")
    assignments = ["updated_at = ?"]
    parameters: list[object] = [updated_at]
    for column in _UPDATABLE:
        if column in fields:
            assignments.append(f"{column} = ?")
            parameters.append(fields[column])
    parameters.append(number)
    return connection.execute(
        "UPDATE tasks SET " + ", ".join(assignments) + " WHERE number = ?",
        parameters,
    )


def select_task(connection: sqlite3.Connection, number: int) -> list[sqlite3.Row]:
    return connection.execute(
        f"SELECT {_SELECT} FROM tasks WHERE number = ?",
        (number,),
    ).fetchall()


def select_tasks(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(f"SELECT {_SELECT} FROM tasks ORDER BY number").fetchall()


def select_tasks_in_states(
    connection: sqlite3.Connection, states: Sequence[str]
) -> list[sqlite3.Row]:
    marks = ", ".join("?" for _ in states)
    return connection.execute(
        f"SELECT {_SELECT} FROM tasks WHERE state IN ({marks}) ORDER BY number",
        tuple(states),
    ).fetchall()


def select_existence(connection: sqlite3.Connection, number: int) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT 1 FROM tasks WHERE number = ?",
        (number,),
    ).fetchone()
