"""Ordinary post SQL. The caller owns the connection and the transaction."""

import sqlite3


def insert_post(
    connection: sqlite3.Connection,
    task: int,
    key: str,
    kind: str,
    missed: int,
    queued_at: str,
) -> sqlite3.Cursor:
    return connection.execute(
        "INSERT INTO posts (task, key, kind, missed, queued_at) VALUES (?, ?, ?, ?, ?)",
        (task, key, kind, missed, queued_at),
    )


def insert_post_reminder(connection: sqlite3.Connection, post: int, reminder: int) -> None:
    connection.execute(
        "INSERT INTO post_reminders (post, reminder) VALUES (?, ?)",
        (post, reminder),
    )


def claim_posts(connection: sqlite3.Connection, at: str, stale_before: str) -> list[sqlite3.Row]:
    return connection.execute(
        "UPDATE posts SET claimed_at = ? "
        "WHERE sent_at IS NULL AND (claimed_at IS NULL OR claimed_at < ?) "
        "AND EXISTS ("
        "SELECT 1 FROM post_reminders "
        "JOIN reminders ON reminders.number = post_reminders.reminder "
        "WHERE post_reminders.post = posts.number AND reminders.voided_at IS NULL"
        ") "
        "RETURNING number, task, key, kind, missed, queued_at, claimed_at, sent_at",
        (at, stale_before),
    ).fetchall()


def release_post(connection: sqlite3.Connection, number: int, claimed_at: str) -> None:
    connection.execute(
        "UPDATE posts SET claimed_at = NULL "
        "WHERE number = ? AND sent_at IS NULL AND claimed_at = ?",
        (number, claimed_at),
    )


def mark_post_sent(connection: sqlite3.Connection, number: int, at: str) -> sqlite3.Cursor:
    return connection.execute(
        "UPDATE posts SET sent_at = ? WHERE number = ? AND sent_at IS NULL",
        (at, number),
    )


def select_post(connection: sqlite3.Connection, number: int) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT number, task, key, kind, missed, queued_at, claimed_at, sent_at "
        "FROM posts WHERE number = ?",
        (number,),
    ).fetchone()


def select_posts(connection: sqlite3.Connection, task: int) -> list[sqlite3.Row]:
    return connection.execute(
        "SELECT number, task, key, kind, missed, queued_at, claimed_at, sent_at "
        "FROM posts WHERE task = ? ORDER BY number",
        (task,),
    ).fetchall()


def select_post_reminders(connection: sqlite3.Connection, post: int) -> list[sqlite3.Row]:
    return connection.execute(
        "SELECT reminder FROM post_reminders WHERE post = ? ORDER BY reminder",
        (post,),
    ).fetchall()
