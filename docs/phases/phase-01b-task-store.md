# Phase 1b: Task store

## Goal

Give the app its database: one private SQLite file in the data folder holding tasks and an audit log that can never be rewritten, opened safely by several processes at once (the service, the `docket` command and the MCP server Conductor starts). This phase builds the store's reads and writes and the transactions every change will run in. It decides nothing about tasks: the state rules, the title rule, and writing one audit row per change belong to `docket.core` in Phase 1c, and the `docket tasks` commands to Phase 1d.

Sections: `core`. The `tooling` section runs in the full check.

Follow `docs/phase-conventions.md`. N is 152, the tests the previous phase left passing.

Start: `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_store.py` must show `152 passed`. The ignored file imports the module you create.

## Facts

Each checked on this machine on 2026-11-14 with Python 3.12.16 and SQLite 3.54.1.

- **Transactions.** Python's `sqlite3` with its default `isolation_level` opens a transaction on its own before an INSERT (`in_transaction` is true after one). Connected with `isolation_level=None`, nothing is implicit, and `BEGIN IMMEDIATE` takes the write lock at once.
- **Locks.** While one connection holds `BEGIN IMMEDIATE`, a second connection's `BEGIN IMMEDIATE` waits for its `busy_timeout`, then raises `sqlite3.OperationalError("database is locked")`; with `timeout=0` it raises at once. In WAL mode a reader is never blocked by a writer and sees only committed rows.
- **WAL files.** With `PRAGMA journal_mode = WAL` on a file of mode `0600`, the `-wal` and `-shm` files are created `0600` too, even under umask `022`. The journal mode is stored in the file, so every later connection is in WAL mode.
- **Ids.** `INTEGER PRIMARY KEY AUTOINCREMENT` never hands out a committed number again. A rolled-back insert's number is handed out again, since its `sqlite_sequence` update is rolled back with it.
- **STRICT tables** turn an integer into text in a TEXT column without an error, so the schema is no type check: the code that writes is.
- **Triggers** with `RAISE(ABORT, '...')` stop an UPDATE or DELETE with `sqlite3.IntegrityError` carrying that text.
- **UTC.** `datetime.fromisoformat("2026-11-14T09:30:00.250000+00:00").tzinfo is datetime.UTC`, so instants read back satisfy Phase 1a's `Deadline` and `WorkTime` checks.
- Migration 1 was run on a scratch database: valid rows go in; all 19 bad task rows and 4 bad audit rows tried are refused; the three triggers fire.

## Owner's decisions

Decided 2026-11-14:

- **Split of the rest of stage 1:** 1b the store (this phase), 1c `docket.core` (state rules, title rule, one audit row per change), 1d the `docket tasks` commands.
- **Task ids are short numbers:** `t1`, `t2`, and so on, given out in order and never reused.
- **Done and cancelled tasks can be reopened at any time** (the `reopen` audit action; the rule itself is Phase 1c's).
- **Titles are refused, never rewritten** (the rule is Phase 1c's; the schema only bounds the length).

## Architect's decisions

- **One file, many processes.** WAL mode, `busy_timeout` of 5000 ms, `foreign_keys` on, `isolation_level=None`, and every write inside `Store.transaction()`, which is `BEGIN IMMEDIATE` so two writers queue instead of failing halfway.
- **Writes need a transaction**, so Phase 1c can put a change and its audit row in one commit. A write outside one is refused before anything is written.
- **The store decides nothing.** It doesn't validate states, sources, actions, actors or titles; the schema's CHECKs are its last layer and surface as `sqlite3.IntegrityError`. It doesn't read the clock: every write is given its instant.
- **The audit log and tasks are never rewritten or removed**, enforced by triggers. A wrong change is corrected by a later change with its own audit row.
- **Instants are stored as text** with `isoformat(timespec="microseconds")` in UTC, so stored values sort as text and always have the same width.
- **Audit before and after** are JSON objects written with `json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))`.
- **Critical modules:** `schema.py` and `store.py` (added to `scripts/critical_modules.txt`).

## Requirements

1. **`src/docket/schema.py`** is given (migration 1: `tasks` and `audit_log`, an index, three triggers; `MIGRATIONS`, `SCHEMA_VERSION = 1`). Do not change it.
2. **`src/docket/store.py`, names**: `DB_FILENAME = "docket.sqlite3"`; `SCHEMA_MESSAGE = "unsupported schema version"`; `TRANSACTION_MESSAGE = "a write needs a transaction"`; `NESTED_MESSAGE = "a transaction is already open"`; `UNKNOWN_TASK_MESSAGE = "unknown task"`; `class StoreError(Exception)`; `UNCHANGED`, a unique sentinel object.
3. **`Task`**, a frozen dataclass with fields in this order: `id: str`, `title: str`, `state: str`, `deadline: Deadline | None`, `work: WorkTime | None`, `source: str`, `provider: str | None`, `message_id: str | None`, `link: str | None`, `created_at: datetime`, `updated_at: datetime`. `id` is `"t"` followed by the row's `number`. **`AuditEntry`**, a frozen dataclass: `task_id: str`, `at: datetime`, `action: str`, `actor: str`, `before: dict`, `after: dict`.
4. **`Store(path: Path)`** opens or creates the database:
   - the file's mode is `0600` after opening, whether it was new or existed with another mode;
   - the connection uses `isolation_level=None`, `PRAGMA journal_mode = WAL`, `PRAGMA busy_timeout = 5000` and `PRAGMA foreign_keys = ON`;
   - each migration from `PRAGMA user_version` up to `SCHEMA_VERSION` runs with its `user_version` bump inside one `BEGIN IMMEDIATE` ... `COMMIT`;
   - a `user_version` above `SCHEMA_VERSION` closes the connection and raises `StoreError` with text `"unsupported schema version: <version>"`.

   `close()` closes it; `Store` is a context manager that closes on exit.
5. **`open_store(settings: Settings) -> Store`** calls `prepare_data_dir(settings)` and opens `settings.data_dir / DB_FILENAME`.
6. **`transaction()`**, a context manager: `BEGIN IMMEDIATE`; `COMMIT` when the block ends normally; `ROLLBACK` and re-raise when it raises anything (`BaseException`). Opening one while one is open raises `StoreError(NESTED_MESSAGE)` and leaves the open one as it was.
7. **Writes**, each raising `StoreError(TRANSACTION_MESSAGE)` outside a transaction, then `StoreError(INSTANT_MESSAGE)` (Phase 1a's text) unless `at.tzinfo is datetime.UTC`, before writing anything:
   - `insert_task(*, title, state, deadline, work, source, provider, message_id, link, at) -> Task` inserts a row with `created_at` and `updated_at` both `at`, and returns the new `Task`;
   - `update_task(task_id, *, at, title=UNCHANGED, state=UNCHANGED, deadline=UNCHANGED, work=UNCHANGED) -> Task` sets each field given (`None` clears a deadline or work time) and `updated_at`, and returns the `Task` as now stored;
   - `append_audit(task_id, *, at, action, actor, before, after) -> AuditEntry` appends one row.

   `update_task` and `append_audit` raise `StoreError(UNKNOWN_TASK_MESSAGE)` for an id that names no task (requirement 8's rule), after the two checks above.
8. **Reads**: `task(task_id) -> Task | None`; `tasks(states: Collection[str] | None = None) -> list[Task]`, every task when `states` is `None`, else only those whose state is in `states` (none for an empty collection), ordered by `number`; `audit(task_id) -> list[AuditEntry]`, in the order appended. An id names a task only if it is exactly `t` followed by a number without a leading zero in ASCII digits (`t1`, `t12`; not `t0`, `t01`, `T1`, `t1 `, `t١`); any other id finds nothing (`None`, `[]`).
9. **Stored text**: instants as `at.isoformat(timespec="microseconds")` (for example `2026-11-14T09:30:00.250000+00:00`); a deadline as `deadline_at`, `deadline_zone` and `deadline_time_given` (1 or 0); a work time as `work_start`, `work_minutes`, `work_zone`; audit `before` and `after` as in Architect's decisions. Values read back are equal to those written (`Deadline`, `WorkTime`, dicts and instants in UTC).
10. **No clock.** The store never calls `clock.now()`; every instant comes from the caller.
11. **Progress entry** for `## Phase 1b: Task store (YYYY-MM-DD)` at the end of `docs/progress.md`.

## Given files

Already committed with this spec; never change them.

| File | What it is |
|---|---|
| `src/docket/schema.py` | Migration 1 (requirement 1) |
| `tests/integration/test_store.py` | 50 tests from 24 functions (requirements 2 to 10) |
| `scripts/critical_modules.txt` | Adds `schema.py` and `store.py` |
| `docs/verification/probe-01b.py` | The verifier's probe |

Given test count: **50**.

## Tests to write

The given tests cover every requirement's main cases. To reach full coverage, add behaviour tests in a new `tests/integration/test_store_more.py`, never by changing a given test.

## Scope

| Path | Change |
|---|---|
| `src/docket/store.py` | create |
| `tests/integration/test_store_more.py` | create, only if coverage needs it |
| `docs/progress.md` | append your entry |

## Out of scope

- The state rules, the title rule, writing an audit row for each change, reopening (Phase 1c, `docket.core`).
- Commands, display text, settings (Phase 1d).
- Any other table: idempotency keys, links, proposals, reminders, calendar links (their phases).
- Deleting or renumbering tasks, editing audit rows, a backup or export.
- Validating states, sources, actions, actors or titles in Python: the schema is the store's only check of them.
- A connection pool, threads, retries around `database is locked`, or a cache of tasks.
- Any change to a given file, `AGENTS.md` or the design docs.

## Rules that bite

- **No clock**: every instant is an argument. **No machine zone**: instants are UTC only.
- **Every write in a transaction, rolled back as a whole** on any exception, and the lock released.
- **Error messages are constant text**, plus only the schema version number; never a title, a value or a library's error text.
- **Plain SQL with `?` parameters**: never put a value into SQL text. Column names from a fixed list in the code (an UPDATE's SET clause) and the migration's `user_version` number are not values.
- Commands start with `.venv/bin/python`; no bare `python3`, `pytest` or `ruff`.

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_store.py` (before you start) | `152 passed` |
| `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 202 passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest tests/integration/test_store.py --no-cov -q` | `50 passed` |
| `.venv/bin/python -m coverage report --include=src/docket/schema.py,src/docket/store.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| `.venv/bin/python docs/verification/probe-01b.py` | last line `FAILURES 0` |
| `grep -c "^## Phase 1b: " docs/progress.md` | `1` |
| `.venv/bin/python scripts/check_reports.py --phase 1b` | `Reports OK.` |
| `git diff HEAD --stat -- src/docket/schema.py tests/integration/test_store.py scripts/critical_modules.txt docs/verification/probe-01b.py` | no output |
| `git status --short` | only the Scope paths |

### Searches

Each prints nothing.

```zsh
git grep --untracked -n -E 'import (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)|from (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)' -- src
git grep --untracked -n -E 'print\(|logging|logger|warnings\.warn' -- src ':!src/docket/cli.py'
git grep --untracked -n -E 'datetime\.now|datetime\.utcnow|date\.today|time\.time\(|from docket\.(clock|ids) import' -- src ':!src/docket/clock.py'
git grep --untracked -n -E 'clock\.now|import clock|get_settings\(' -- src/docket/store.py
git grep --untracked -n -E 'execute(script|many)?\([^)]*(%|\.format\()' -- src
git grep --untracked -n -E 'DELETE FROM|UPDATE audit_log|DROP |isolation_level=(""|.DEFERRED.)' -- src/docket/store.py
git grep --untracked -n -E 'ollama|anthropic|openai|langchain' -- src
git grep --untracked -n -E 'pragma: no cover|noqa' -- src/docket/store.py src/docket/schema.py
```
