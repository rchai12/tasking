"""Synthetic SQLite instrumentation; nothing opens a real application database."""

import inspect
import re
import sqlite3

from docket import core

TABLE_MODULES = {
    "audit_log": "docket._store_audit",
    "links": "docket._store_links",
    "request_keys": "docket._store_keys",
}
_TABLE = re.compile(r"\b(?:FROM|INTO|UPDATE)\s+(audit_log|links|request_keys)\b", re.I)
_INSERT = re.compile(r"^\s*INSERT\s+INTO\s+(audit_log|links|request_keys)\b", re.I)


class InjectedSqlFailure(Exception):
    pass


class RecordingConnection(sqlite3.Connection):
    recording = False
    interrupt_table: str | None = None

    def execute(self, sql, parameters=()):
        match = _TABLE.search(sql)
        if self.recording and match:
            frame = inspect.currentframe()
            assert frame is not None and frame.f_back is not None
            caller = frame.f_back.f_globals["__name__"]
            self.events.append((match[1].lower(), caller, self.in_transaction))
        result = super().execute(sql, parameters)
        inserted = _INSERT.match(sql)
        if (
            self.recording
            and self.interrupt_table is not None
            and inserted is not None
            and inserted[1].lower() == self.interrupt_table
        ):
            raise InjectedSqlFailure
        return result


def record_connections(monkeypatch):
    original = sqlite3.connect
    opened = []

    def connect(*args, **kwargs):
        connection = original(*args, **kwargs, factory=RecordingConnection)
        connection.events = []
        opened.append(connection)
        return connection

    monkeypatch.setattr(sqlite3, "connect", connect)
    return opened


def create_agent(store):
    return core.create_task_once(
        store,
        client="agent",
        key="synthetic-create",
        request={"z": None, "a": "雪"},
        title="Synthetic ' task",
        source="agent",
    )


def add_email(store):
    return core.add_link(
        store,
        "t1",
        client="email",
        key="synthetic-link",
        request={"a": "雪", "z": None},
        provider="gmail",
        message_id="synthetic/'1",
        link="https://mail.example/'1",
    )


def snapshot(connection):
    recording = connection.recording
    connection.recording = False
    try:
        return {
            table: [
                tuple(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY 1, 2")
            ]
            for table in ("tasks", "audit_log", "links", "request_keys", "sqlite_sequence")
        }
    finally:
        connection.recording = recording
