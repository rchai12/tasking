"""Ordinary request_keys SQL. The caller owns the connection and the transaction."""

import sqlite3


def insert_request_key(
    connection: sqlite3.Connection,
    client: str,
    key: str,
    request: str,
    task: int,
    link: int | None,
    created_at: str,
) -> sqlite3.Cursor:
    return connection.execute(
        "INSERT INTO request_keys (client, key, request, task, link, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (client, key, request, task, link, created_at),
    )


def select_request_key(connection: sqlite3.Connection, client: str, key: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT client, key, request, task, link, created_at FROM request_keys "
        "WHERE client = ? AND key = ?",
        (client, key),
    ).fetchone()
