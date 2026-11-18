"""Ordinary tasks SQL. The caller owns the connection and the transaction."""

import sqlite3
from collections.abc import Mapping, Sequence

_COLUMNS = (
    "title, state, deadline_at, deadline_zone, deadline_time_given, "
    "work_start, work_minutes, work_zone, source, provider, message_id, link, "
    "created_at, updated_at"
)
_SELECT = "number, " + _COLUMNS


def insert_task(connection: sqlite3.Connection, values: tuple[object, ...]) -> sqlite3.Cursor:
    return connection.execute(
        f"INSERT INTO tasks ({_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        values,
    )


def update_task(
    connection: sqlite3.Connection,
    number: int,
    updated_at: str,
    fields: Mapping[str, object],
) -> sqlite3.Cursor:
    assignments = ["updated_at = ?"]
    parameters: list[object] = [updated_at]
    if "title" in fields:
        assignments.append("title = ?")
        parameters.append(fields["title"])
    if "state" in fields:
        assignments.append("state = ?")
        parameters.append(fields["state"])
    if "deadline_at" in fields:
        assignments.append("deadline_at = ?")
        parameters.append(fields["deadline_at"])
    if "deadline_zone" in fields:
        assignments.append("deadline_zone = ?")
        parameters.append(fields["deadline_zone"])
    if "deadline_time_given" in fields:
        assignments.append("deadline_time_given = ?")
        parameters.append(fields["deadline_time_given"])
    if "work_start" in fields:
        assignments.append("work_start = ?")
        parameters.append(fields["work_start"])
    if "work_minutes" in fields:
        assignments.append("work_minutes = ?")
        parameters.append(fields["work_minutes"])
    if "work_zone" in fields:
        assignments.append("work_zone = ?")
        parameters.append(fields["work_zone"])
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
