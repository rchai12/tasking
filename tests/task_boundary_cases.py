"""Extend the given SQL recorder to task queries without changing earlier given files."""

import inspect
import re
import sqlite3

from tests.store_boundary_cases import (
    TABLE_MODULES,
    InjectedSqlFailure,
    RecordingConnection,
)

ALL_TABLE_MODULES = {**TABLE_MODULES, "tasks": "docket._store_tasks"}
_TASK = re.compile(r"\b(?:FROM|INTO|UPDATE)\s+tasks\b", re.I)
_WRITE = re.compile(r"^\s*(INSERT\s+INTO|UPDATE)\s+tasks\b", re.I)


class TaskConnection(RecordingConnection):
    interrupt_task: str | None = None

    def execute(self, sql, parameters=()):
        caller = ""
        if self.recording:
            frame = inspect.currentframe()
            try:
                assert frame is not None and frame.f_back is not None
                caller = frame.f_back.f_globals["__name__"]
            finally:
                del frame
        before = len(self.events)
        if self.recording and _TASK.search(sql):
            self.events.append(("tasks", caller, self.in_transaction))
        try:
            result = super().execute(sql, parameters)
        finally:
            # The parent sees this wrapper; retain the actual SQL caller for all four tables.
            for index in range(before, len(self.events)):
                table, _wrapper, transaction = self.events[index]
                self.events[index] = table, caller, transaction
        write = _WRITE.match(sql)
        if self.recording and write and self.interrupt_task == write[1].lower().split()[0]:
            raise InjectedSqlFailure
        return result


def record_task_connections(monkeypatch):
    original = sqlite3.connect
    opened = []

    def connect(*args, **kwargs):
        connection = original(*args, **kwargs, factory=TaskConnection)
        connection.events = []
        opened.append(connection)
        return connection

    monkeypatch.setattr(sqlite3, "connect", connect)
    return opened
