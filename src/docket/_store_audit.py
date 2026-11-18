"""Ordinary audit_log SQL. The caller owns the connection and the transaction."""

import sqlite3


def insert_audit(
    connection: sqlite3.Connection,
    task: int,
    at: str,
    action: str,
    actor: str,
    before: str,
    after: str,
) -> sqlite3.Cursor:
    return connection.execute(
        "INSERT INTO audit_log (task, at, action, actor, before, after) VALUES (?, ?, ?, ?, ?, ?)",
        (task, at, action, actor, before, after),
    )


def select_audit(connection: sqlite3.Connection, task: int) -> list[sqlite3.Row]:
    return connection.execute(
        "SELECT at, action, actor, before, after FROM audit_log WHERE task = ? ORDER BY number",
        (task,),
    ).fetchall()
