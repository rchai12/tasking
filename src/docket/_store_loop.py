"""Ordinary loop-status SQL. The caller owns the connection and the transaction."""

import sqlite3


def save_status(
    connection: sqlite3.Connection,
    pass_at: str,
    sent: int,
    digest: int,
    reminders_failures: int,
    digest_failures: int,
    skipped: str,
) -> None:
    connection.execute(
        "INSERT INTO loop_status "
        "(number, pass_at, sent, digest, reminders_failures, digest_failures, skipped) "
        "VALUES (1, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT (number) DO UPDATE SET pass_at = excluded.pass_at, "
        "sent = excluded.sent, digest = excluded.digest, "
        "reminders_failures = excluded.reminders_failures, "
        "digest_failures = excluded.digest_failures, skipped = excluded.skipped",
        (pass_at, sent, digest, reminders_failures, digest_failures, skipped),
    )


def select_status(connection: sqlite3.Connection) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT pass_at, sent, digest, reminders_failures, digest_failures, skipped "
        "FROM loop_status WHERE number = 1"
    ).fetchone()
