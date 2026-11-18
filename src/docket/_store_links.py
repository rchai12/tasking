"""Ordinary links SQL. The caller owns the connection and the transaction."""

import sqlite3


def insert_link(
    connection: sqlite3.Connection,
    task: int,
    provider: str,
    message_id: str,
    link: str,
    created_at: str,
) -> sqlite3.Cursor:
    return connection.execute(
        "INSERT INTO links (task, provider, message_id, link, created_at) VALUES (?, ?, ?, ?, ?)",
        (task, provider, message_id, link, created_at),
    )


def select_links(connection: sqlite3.Connection, task: int) -> list[sqlite3.Row]:
    return connection.execute(
        "SELECT number, task, provider, message_id, link, created_at "
        "FROM links WHERE task = ? ORDER BY number",
        (task,),
    ).fetchall()


def select_existence(connection: sqlite3.Connection, number: int) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT 1 FROM links WHERE number = ?",
        (number,),
    ).fetchone()


def select_link(connection: sqlite3.Connection, number: int) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT number, task, provider, message_id, link, created_at FROM links WHERE number = ?",
        (number,),
    ).fetchone()
