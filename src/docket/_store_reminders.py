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


def select_due_reminders(
    connection: sqlite3.Connection, at: str, task: int | None = None
) -> list[sqlite3.Row]:
    return connection.execute(
        "SELECT number, task, kind, fire_at, planned_at, claimed_at, sent_at, voided_at "
        "FROM reminders WHERE fire_at <= ? AND claimed_at IS NULL AND sent_at IS NULL "
        "AND voided_at IS NULL AND (? IS NULL OR task = ?) ORDER BY task, fire_at, number",
        (at, task, task),
    ).fetchall()


def pending_reminder(connection: sqlite3.Connection, number: int, task: int) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM reminders WHERE number = ? AND task = ? AND claimed_at IS NULL "
            "AND sent_at IS NULL AND voided_at IS NULL",
            (number, task),
        ).fetchone()
        is not None
    )


def claim_reminders(connection: sqlite3.Connection, numbers: tuple[int, ...], at: str) -> None:
    marks = ", ".join("?" for _ in numbers)
    connection.execute(
        f"UPDATE reminders SET claimed_at = ? WHERE number IN ({marks})",
        (at, *numbers),
    )


def mark_reminders_sent(connection: sqlite3.Connection, numbers: tuple[int, ...], at: str) -> None:
    marks = ", ".join("?" for _ in numbers)
    connection.execute(
        "UPDATE reminders SET sent_at = ? "
        f"WHERE number IN ({marks}) AND voided_at IS NULL AND sent_at IS NULL",
        (at, *numbers),
    )
