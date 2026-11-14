"""The database schema as numbered migrations.

`MIGRATIONS[i]` moves a database from `PRAGMA user_version` i to i + 1. A later phase appends to
this tuple; a shipped migration is never edited. Instants are UTC text written with
`isoformat(timespec="microseconds")`. SQLite cannot change a CHECK, so a later migration that
widens one rebuilds the table.
"""

MIGRATION_1 = """
CREATE TABLE tasks (
    number INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND 100),
    state TEXT NOT NULL CHECK (state IN ('open', 'in_progress', 'done', 'cancelled')),
    deadline_at TEXT,
    deadline_zone TEXT,
    deadline_time_given INTEGER CHECK (deadline_time_given IN (0, 1)),
    work_start TEXT,
    work_minutes INTEGER CHECK (work_minutes BETWEEN 5 AND 720),
    work_zone TEXT,
    source TEXT NOT NULL CHECK (source IN ('email', 'agent', 'proposal', 'owner')),
    provider TEXT CHECK (provider IN ('gmail', 'outlook', 'yahoo')),
    message_id TEXT CHECK (length(message_id) >= 1),
    link TEXT CHECK (length(link) >= 1),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK ((deadline_at IS NULL) = (deadline_zone IS NULL)),
    CHECK ((deadline_at IS NULL) = (deadline_time_given IS NULL)),
    CHECK ((work_start IS NULL) = (work_minutes IS NULL)),
    CHECK ((work_start IS NULL) = (work_zone IS NULL)),
    CHECK ((provider IS NULL) = (message_id IS NULL)),
    CHECK ((provider IS NULL) = (link IS NULL)),
    CHECK ((source = 'email') = (provider IS NOT NULL))
) STRICT;

CREATE TABLE audit_log (
    number INTEGER PRIMARY KEY AUTOINCREMENT,
    task INTEGER NOT NULL REFERENCES tasks (number),
    at TEXT NOT NULL,
    action TEXT NOT NULL CHECK (
        action IN (
            'create', 'start', 'done', 'cancel', 'reopen', 'retitle', 'deadline', 'work_time'
        )
    ),
    actor TEXT NOT NULL CHECK (actor IN ('owner', 'agent', 'email')),
    before TEXT NOT NULL,
    after TEXT NOT NULL
) STRICT;

CREATE INDEX audit_log_by_task ON audit_log (task, number);

CREATE TRIGGER tasks_are_never_removed BEFORE DELETE ON tasks
BEGIN
    SELECT RAISE(ABORT, 'tasks are never removed');
END;

CREATE TRIGGER audit_rows_are_never_changed BEFORE UPDATE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'audit rows are never changed');
END;

CREATE TRIGGER audit_rows_are_never_removed BEFORE DELETE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'audit rows are never removed');
END;
"""

MIGRATIONS: tuple[str, ...] = (MIGRATION_1,)
SCHEMA_VERSION = len(MIGRATIONS)
