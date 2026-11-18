"""Ordinary reminders SQL. The caller owns the connection and the transaction."""

import sqlite3


def insert_reminder(
    connection: sqlite3.Connection,
    task: int,
    kind: str,
    fire_at: str,
    planned_at: str,
) -> sqlite3.Cursor:
    return connection.execute(
        "INSERT INTO reminders (task, kind, fire_at, planned_at) VALUES (?, ?, ?, ?)",
        (task, kind, fire_at, planned_at),
    )


def select_reminders(connection: sqlite3.Connection, task: int) -> list[sqlite3.Row]:
    return connection.execute(
        "SELECT number, task, kind, fire_at, planned_at, claimed_at, sent_at, voided_at "
        "FROM reminders WHERE task = ? ORDER BY number",
        (task,),
    ).fetchall()


def void_reminders(
    connection: sqlite3.Connection,
    task: int,
    at: str,
    kinds: tuple[str, ...],
) -> None:
    marks = ", ".join("?" for _ in kinds)
    connection.execute(
        "UPDATE reminders SET voided_at = ? "
        "WHERE task = ? AND sent_at IS NULL AND voided_at IS NULL "
        f"AND kind IN ({marks})",
        (at, task, *kinds),
    )
