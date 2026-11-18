"""Ordinary digest SQL. The caller owns the connection and the transaction."""

import sqlite3


def insert_digest(
    connection: sqlite3.Connection, day: str, key: str, queued_at: str
) -> sqlite3.Cursor:
    return connection.execute(
        "INSERT INTO digests (day, key, queued_at) VALUES (?, ?, ?)",
        (day, key, queued_at),
    )


def insert_digest_task(connection: sqlite3.Connection, digest: int, task: int) -> None:
    connection.execute(
        "INSERT INTO digest_tasks (digest, task) VALUES (?, ?)",
        (digest, task),
    )


def claim_digest(
    connection: sqlite3.Connection,
    day: str,
    at: str,
    stale_before: str,
    overdue_before: str,
    states: tuple[str, ...],
) -> sqlite3.Row | None:
    marks = ", ".join("?" for _ in states)
    return connection.execute(
        "UPDATE digests SET claimed_at = ? "
        "WHERE day = ? AND sent_at IS NULL AND (claimed_at IS NULL OR claimed_at < ?) "
        "AND EXISTS ("
        "SELECT 1 FROM digest_tasks "
        "JOIN tasks ON tasks.number = digest_tasks.task "
        "WHERE digest_tasks.digest = digests.number "
        f"AND tasks.state IN ({marks}) "
        "AND tasks.deadline_at IS NOT NULL AND tasks.deadline_at <= ?"
        ") "
        "RETURNING number, day, key, queued_at, claimed_at, sent_at",
        (at, day, stale_before, *states, overdue_before),
    ).fetchone()


def release_digest(connection: sqlite3.Connection, number: int, claimed_at: str) -> None:
    connection.execute(
        "UPDATE digests SET claimed_at = NULL "
        "WHERE number = ? AND sent_at IS NULL AND claimed_at = ?",
        (number, claimed_at),
    )


def mark_digest_sent(connection: sqlite3.Connection, number: int, at: str) -> sqlite3.Cursor:
    return connection.execute(
        "UPDATE digests SET sent_at = ? WHERE number = ? AND sent_at IS NULL",
        (at, number),
    )


def select_digest(connection: sqlite3.Connection, day: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT number, day, key, queued_at, claimed_at, sent_at FROM digests WHERE day = ?",
        (day,),
    ).fetchone()


def select_digest_by_number(connection: sqlite3.Connection, number: int) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT number, day, key, queued_at, claimed_at, sent_at FROM digests WHERE number = ?",
        (number,),
    ).fetchone()


def select_digest_tasks(connection: sqlite3.Connection, digest: int) -> list[sqlite3.Row]:
    return connection.execute(
        "SELECT task FROM digest_tasks WHERE digest = ? ORDER BY task",
        (digest,),
    ).fetchall()
