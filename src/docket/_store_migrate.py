"""Schema migrations and the reminder backfill, run once per open by `Store`."""

import sqlite3
from typing import TYPE_CHECKING, cast

from docket import domain
from docket import store as store_module
from docket.references import LINK_MAX, MESSAGE_ID_MAX, valid_reference

if TYPE_CHECKING:
    from docket.store import Store


def migrate(db: "Store") -> None:
    while True:
        rebuild = False
        with db.transaction():
            version = _user_version(db)
            if version > store_module.SCHEMA_VERSION:
                raise store_module.StoreError(f"{store_module.SCHEMA_MESSAGE}: {version}")
            if version == store_module.SCHEMA_VERSION:
                return
            if version == 2:
                rebuild = True
            else:
                _apply_migration(db, version)
        if rebuild:
            _migrate_references(db)


def _apply_migration(db: "Store", version: int) -> None:
    for statement in store_module._statements(store_module.MIGRATIONS[version]):
        db._connection.execute(statement)
    if version == 3:
        _backfill_reminders(db)
    db._connection.execute(f"PRAGMA user_version = {version + 1}")


def _user_version(db: "Store") -> int:
    found = cast(sqlite3.Row, db._connection.execute("PRAGMA user_version").fetchone())
    return int(found[0])


def _migrate_references(db: "Store") -> None:
    db._connection.execute("PRAGMA foreign_keys = OFF")
    try:
        with db.transaction():
            version = _user_version(db)
            if version > store_module.SCHEMA_VERSION:
                raise store_module.StoreError(f"{store_module.SCHEMA_MESSAGE}: {version}")
            if version == 2:
                _refuse_invalid_references(db)
                for statement in store_module._statements(store_module.MIGRATIONS[2]):
                    db._connection.execute(statement)
                if db._connection.execute("PRAGMA foreign_key_check").fetchall():
                    raise store_module.StoreError("invalid reference migration")
                db._connection.execute("PRAGMA user_version = 3")
    finally:
        db._connection.execute("PRAGMA foreign_keys = ON")


def _refuse_invalid_references(db: "Store") -> None:
    tasks = db._connection.execute(
        "SELECT number, message_id, link FROM tasks WHERE source = 'email' ORDER BY number"
    )
    for row in tasks:
        _refuse_reference(f"t{row['number']}", row["message_id"], row["link"])
    links = db._connection.execute("SELECT number, message_id, link FROM links ORDER BY number")
    for row in links:
        _refuse_reference(f"l{row['number']}", row["message_id"], row["link"])


def _refuse_reference(identifier: str, message_id: object, link: object) -> None:
    if not valid_reference(message_id, MESSAGE_ID_MAX):
        raise store_module.StoreError(f"invalid stored reference: {identifier} message_id")
    if not valid_reference(link, LINK_MAX):
        raise store_module.StoreError(f"invalid stored reference: {identifier} link")


def _backfill_reminders(db: "Store") -> None:
    from docket import reminders

    rows = db._connection.execute(
        "SELECT number, title, state, deadline_at, deadline_zone, deadline_time_given, "
        "work_start, work_minutes, work_zone, source, provider, message_id, link, "
        "created_at, updated_at FROM tasks WHERE state IN ("
        + ", ".join("?" for _ in domain.OPEN_STATES)
        + ") ORDER BY number",
        domain.OPEN_STATES,
    ).fetchall()
    for row in rows:
        task = db._task_from(row)
        try:
            plans = reminders.plan_reminders(task, task.updated_at)
        except OverflowError:
            raise store_module.StoreError(f"invalid reminder plan: {task.id}") from None
        db._write_reminders(task.id, int(row["number"]), plans, task.updated_at)
