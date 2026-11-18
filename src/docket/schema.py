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

MIGRATION_2 = """
CREATE TABLE links (
    number INTEGER PRIMARY KEY AUTOINCREMENT,
    task INTEGER NOT NULL REFERENCES tasks (number),
    provider TEXT NOT NULL CHECK (provider IN ('gmail', 'outlook', 'yahoo')),
    message_id TEXT NOT NULL CHECK (length(message_id) >= 1),
    link TEXT NOT NULL CHECK (length(link) >= 1),
    created_at TEXT NOT NULL
) STRICT;

CREATE INDEX links_by_task ON links (task, number);

CREATE TABLE request_keys (
    client TEXT NOT NULL CHECK (client IN ('email', 'agent')),
    key TEXT NOT NULL CHECK (length(key) BETWEEN 1 AND 200),
    request TEXT NOT NULL,
    task INTEGER NOT NULL REFERENCES tasks (number),
    link INTEGER REFERENCES links (number),
    created_at TEXT NOT NULL,
    PRIMARY KEY (client, key),
    CHECK ((client = 'agent') <= (link IS NULL))
) STRICT;
"""

MIGRATION_3 = """
CREATE TEMP TABLE reference_sequences (name TEXT PRIMARY KEY, seq INTEGER);
INSERT INTO reference_sequences SELECT name, seq FROM sqlite_sequence
    WHERE name IN ('tasks', 'links');

CREATE TABLE tasks_bounded (
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
    message_id TEXT CHECK (length(message_id) BETWEEN 1 AND 512 AND instr(message_id, char(0)) = 0),
    link TEXT CHECK (length(link) BETWEEN 1 AND 2048 AND instr(link, char(0)) = 0),
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

CREATE TABLE links_bounded (
    number INTEGER PRIMARY KEY AUTOINCREMENT,
    task INTEGER NOT NULL REFERENCES tasks (number),
    provider TEXT NOT NULL CHECK (provider IN ('gmail', 'outlook', 'yahoo')),
    message_id TEXT NOT NULL CHECK (
        length(message_id) BETWEEN 1 AND 512 AND instr(message_id, char(0)) = 0
    ),
    link TEXT NOT NULL CHECK (length(link) BETWEEN 1 AND 2048 AND instr(link, char(0)) = 0),
    created_at TEXT NOT NULL
) STRICT;

INSERT INTO tasks_bounded SELECT * FROM tasks;
INSERT INTO links_bounded SELECT * FROM links;
DROP TABLE links;
DROP TABLE tasks;
ALTER TABLE tasks_bounded RENAME TO tasks;
ALTER TABLE links_bounded RENAME TO links;
CREATE INDEX links_by_task ON links (task, number);
CREATE TRIGGER tasks_are_never_removed BEFORE DELETE ON tasks
BEGIN
    SELECT RAISE(ABORT, 'tasks are never removed');
END;
DELETE FROM sqlite_sequence WHERE name IN ('tasks', 'links');
INSERT INTO sqlite_sequence SELECT name, seq FROM reference_sequences;
DROP TABLE reference_sequences;
"""

MIGRATION_4 = """
CREATE TABLE reminders (
    number INTEGER PRIMARY KEY AUTOINCREMENT CHECK (number > 0),
    task INTEGER NOT NULL REFERENCES tasks (number),
    kind TEXT NOT NULL CHECK (kind IN ('start', 'before', 'due_soon', 'due', 'late')),
    fire_at TEXT NOT NULL,
    planned_at TEXT NOT NULL,
    claimed_at TEXT,
    sent_at TEXT,
    voided_at TEXT
) STRICT;
CREATE INDEX reminders_by_task ON reminders (task, number);
CREATE INDEX reminders_pending ON reminders (fire_at, number)
    WHERE sent_at IS NULL AND voided_at IS NULL;
CREATE TRIGGER reminders_are_never_removed BEFORE DELETE ON reminders
BEGIN
    SELECT RAISE(ABORT, 'reminders are never removed');
END;
CREATE TRIGGER reminder_plans_are_immutable
BEFORE UPDATE OF number, task, kind, fire_at, planned_at ON reminders
BEGIN
    SELECT RAISE(ABORT, 'reminder plan is immutable');
END;
"""

MIGRATION_5 = """
CREATE TABLE posts (
    number INTEGER PRIMARY KEY AUTOINCREMENT CHECK (number > 0),
    task INTEGER NOT NULL REFERENCES tasks (number),
    key TEXT NOT NULL UNIQUE CHECK (length(key) BETWEEN 1 AND 200),
    kind TEXT NOT NULL CHECK (kind IN ('start', 'before', 'due_soon', 'due', 'late')),
    missed INTEGER NOT NULL CHECK (missed >= 0),
    queued_at TEXT NOT NULL,
    claimed_at TEXT,
    sent_at TEXT
) STRICT;
CREATE TABLE post_reminders (
    post INTEGER NOT NULL REFERENCES posts (number),
    reminder INTEGER NOT NULL UNIQUE REFERENCES reminders (number),
    PRIMARY KEY (post, reminder)
) STRICT;
CREATE INDEX posts_unsent ON posts (number) WHERE sent_at IS NULL;
CREATE TRIGGER posts_are_never_removed BEFORE DELETE ON posts
BEGIN
    SELECT RAISE(ABORT, 'posts are never removed');
END;
CREATE TRIGGER post_contents_are_immutable
BEFORE UPDATE OF number, task, key, kind, missed, queued_at ON posts
BEGIN
    SELECT RAISE(ABORT, 'post contents are immutable');
END;
CREATE TRIGGER post_reminders_are_never_removed BEFORE DELETE ON post_reminders
BEGIN
    SELECT RAISE(ABORT, 'post reminders are never removed');
END;
CREATE TRIGGER post_reminders_are_immutable BEFORE UPDATE ON post_reminders
BEGIN
    SELECT RAISE(ABORT, 'post reminders are immutable');
END;
"""

MIGRATION_6 = """
CREATE TABLE digests (
    number INTEGER PRIMARY KEY AUTOINCREMENT CHECK (number > 0),
    day TEXT NOT NULL UNIQUE CHECK (date(day) IS day),
    key TEXT NOT NULL UNIQUE CHECK (length(key) BETWEEN 1 AND 200),
    queued_at TEXT NOT NULL,
    claimed_at TEXT,
    sent_at TEXT
) STRICT;
CREATE TABLE digest_tasks (
    digest INTEGER NOT NULL REFERENCES digests (number),
    task INTEGER NOT NULL REFERENCES tasks (number),
    PRIMARY KEY (digest, task)
) STRICT;
CREATE TRIGGER digests_are_never_removed BEFORE DELETE ON digests
BEGIN
    SELECT RAISE(ABORT, 'digests are never removed');
END;
CREATE TRIGGER digest_contents_are_immutable
BEFORE UPDATE OF number, day, key, queued_at ON digests
BEGIN
    SELECT RAISE(ABORT, 'digest contents are immutable');
END;
CREATE TRIGGER digest_tasks_are_never_removed BEFORE DELETE ON digest_tasks
BEGIN
    SELECT RAISE(ABORT, 'digest tasks are never removed');
END;
CREATE TRIGGER digest_tasks_are_immutable BEFORE UPDATE ON digest_tasks
BEGIN
    SELECT RAISE(ABORT, 'digest tasks are immutable');
END;
"""

MIGRATIONS: tuple[str, ...] = (
    MIGRATION_1,
    MIGRATION_2,
    MIGRATION_3,
    MIGRATION_4,
    MIGRATION_5,
    MIGRATION_6,
)
SCHEMA_VERSION = len(MIGRATIONS)
