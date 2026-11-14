# Phase 1e: Adding and listing tasks

## Goal

Give you the first working commands: `docket tasks add` to create a task, `docket tasks list` to see what's open, and `docket tasks show` for one task in full. They go through `docket.core` and `docket.views` like every later caller, so a task added here reads the same on Discord later. Refusals are plain sentences on stderr with exit code 1. The commands that change a task (`start`, `done`, `cancel`, `reopen`, `edit`, `plan`) are Phase 1f.

Sections: `core`. The `tooling` section runs in the full check.

Follow `docs/phase-conventions.md`. N is 345, the tests the previous phase left passing.

Start: `.venv/bin/python -m pytest --no-cov -q --ignore=tests/e2e/test_cli_tasks.py --ignore=tests/unit/test_views_tasks.py` must show `345 passed`. The ignored files import names you create.

## Facts

Each checked on this machine on 2026-11-14 with Python 3.12.16, typer 0.29.1 and rich 15.0.0.

- **Typer's test runner** keeps `result.stdout` and `result.stderr` apart. `raise typer.Exit(1)` exits 1. A usage mistake exits 2 with rich's boxed message on stderr, for example `Missing argument 'title'.`, `Got unexpected extra argument(s) (extra)`, `No such command 'nope'.`; the names in those messages are the parameters' names. `add -- -x` passes a title that starts with a dash.
- **`date.fromisoformat` is lenient**: it accepts `20261120` and `2026-W47-1`. **`time.fromisoformat` is lenient**: it accepts `1700`, `17`, `T17:00`, `17:00:30` and `17:00Z`. Both refuse full-width digits, `2026-11-31`, `2026-1-5`, `24:00`, `17:60` and `7:00`. So the shape is checked with an ASCII pattern before parsing.
- **Phase 1d's views**: `when`, `deadline_text`, `work_text`, `status_text` exist as specified; `home_zone(settings)` raises `ConfigError("DOCKET_TIME_ZONE is not set")`, and `get_settings()` raises `ConfigError("DOCKET_TIME_ZONE must be a time zone name")` for a bad zone.
- **Phase 1c's core** reads the clock once in `create_task`, after its checks; `CoreError.code` is one of eight codes.
- Every expected line in the given tests was built with the standard library (`ljust`, `astimezone`, `tzname()`), not typed by hand.

## Owner's decisions

Decided 2026-11-14:

- **Split:** 1e `add`, `list`, `show`, the list line and the detail view (this phase); 1f `start`, `done`, `cancel`, `reopen`, `edit`, `plan`.
- **The list shows open and in-progress tasks by default, soonest deadline first** (overdue at the top), then undated tasks by id; `--all` adds done and cancelled tasks in the same order.
- **A refusal is a plain sentence and exit code 1.** The codes stay for the MCP tools.
- **`add` takes `--due DATE [--at HH:MM]`.** Without `--at` it's 17:00 and marked no time given; `--at` without `--due` is refused.
- Earlier: dates and times are ISO in your zone; `DOCKET_TIME_ZONE` has no default.

## Architect's decisions

- **Every `docket tasks` command needs `DOCKET_TIME_ZONE`**, checked first, before the store is opened or the clock read, so a missing zone never leaves a half-done command.
- **`add` reads no clock of its own**: it shows the new task's deadline against the task's `created_at`, the core's one clock read. `list` and `show` read the clock once.
- **Columns**: the id padded to 5 then one space, the status padded to 21 then one space, then the title, then `  due <deadline>` when there is one. A longer id or status pushes the line right but is never joined to the next column.
- **A tie on the deadline instant keeps id order**, so the list is the same every time.
- **Success goes to stdout, refusals to stderr**, each ending in a newline.

## Requirements

1. **`src/docket/views.py`, `task_line(task: Task, home: str, now: datetime) -> str`**: `task.id.ljust(5)`, a space, `status_text(task, now).ljust(21)`, a space, the title; then, with a deadline, two spaces, `due `, and `deadline_text(task.deadline, home, now)`.
2. **`task_detail(task: Task, home: str, now: datetime) -> list[str]`**, in this order:
   - `<id>  <title>`;
   - `State: <status_text>`;
   - `Due: <deadline_text>` or `Due: none`;
   - `Work: <work_text>` or `Work: none`;
   - `Source: <source>`, and for an email task `Source: email, <provider> <message_id>`;
   - `Link: <link>`, only when the task has a link;
   - `Created: <when(created_at, home, now)>`;
   - `Updated: <when(updated_at, home, now)>`.
3. **`refusal_text(code: str, task_id: str | None = None) -> str`**, for the eight core codes:

   | Code | With an id | Without |
   |---|---|---|
   | `unknown_task` | `There is no task <id>.` | `There is no such task.` |
   | `invalid_title` | `A title is 1 to 100 characters on one line, with no space at either end.` | the same |
   | `invalid_source` | `That source is not allowed.` | the same |
   | `invalid_reference` | `That email reference is not complete.` | the same |
   | `invalid_actor` | `That actor is not allowed.` | the same |
   | `invalid_action` | `That is not a state change.` | the same |
   | `task_ended` | `Task <id> has ended; reopen it first.` | `That task has ended; reopen it first.` |
   | `work_after_deadline` | `The work time must end by the deadline.` | the same |
4. **`src/docket/cli.py`, messages**: `DUE_MESSAGE = "--due must be a date like 2026-11-20."`, `AT_MESSAGE = "--at must be a time like 17:00."`, `AT_WITHOUT_DUE_MESSAGE = "--at needs --due."`, `NO_TASKS_MESSAGE = "No tasks."`.
5. **A `tasks` command group** on `app`, so the commands are `docket tasks add`, `docket tasks list` and `docket tasks show`. `docket version` stays as it is.
6. **Every `tasks` command starts the same way**: `get_settings()`, then `home_zone(settings)`. A `ConfigError` prints its text to stderr and exits 1, before the store is opened or the clock read. A `StoreError` from opening the store prints its text to stderr and exits 1.
7. **`docket tasks add TITLE [--due YYYY-MM-DD] [--at HH:MM]`** (the argument is named `title`). After requirement 6 it checks, in order, printing the message to stderr and exiting 1 on the first that fails: `--at` given without `--due` (`AT_WITHOUT_DUE_MESSAGE`); `--due` not matching `[0-9]{4}-[0-9]{2}-[0-9]{2}` or not a real date (`DUE_MESSAGE`); `--at` not matching `[0-9]{2}:[0-9]{2}` or not a real time (`AT_MESSAGE`). It builds the deadline with `make_deadline(day, at or None, home)`, opens the store with `open_store(settings)`, and calls `core.create_task(store, title=title, source="owner", deadline=deadline)`. A `CoreError` prints `refusal_text(code)` to stderr and exits 1. On success it prints `Added <id>: <title>` and, with a deadline, `, due <deadline_text(deadline, home, task.created_at)>`. It reads no clock itself.
8. **`docket tasks list [--all]`**: after requirement 6, one clock read, then the tasks in state `open` or `in_progress` (every task with `--all`), sorted by: tasks with a deadline first; then the deadline's instant; then the id's number. It prints one `task_line` each, or `NO_TASKS_MESSAGE` when there are none.
9. **`docket tasks show TASK_ID`** (the argument is named `task_id`): after requirement 6, one clock read; an id that finds no task prints `refusal_text("unknown_task", task_id)` to stderr and exits 1; otherwise it prints the `task_detail` lines.
10. **The commands decide nothing**: they parse, call `get_settings`, `home_zone`, `open_store`, `make_deadline`, the core and the views, and print. They read no environment variable themselves and write to the store only through the core.
11. **Progress entry** for `## Phase 1e: Adding and listing tasks (YYYY-MM-DD)` at the end of `docs/progress.md`.

## Given files

Already committed with this spec; never change them.

| File | What it is |
|---|---|
| `tests/unit/test_views_tasks.py` | 20 tests from 5 functions (requirements 1 to 3) |
| `tests/e2e/test_cli_tasks.py` | 46 tests from 13 functions (requirements 4 to 10) |
| `docs/verification/probe-01e.py` | The verifier's probe |

Given test count: **66**.

## Tests to write

The given tests cover every requirement's main cases. To reach full coverage, add behaviour tests in new `*_more.py` files beside them, never by changing a given test. One case the given tests leave to you: a database with a newer schema makes every `tasks` command print `unsupported schema version: <n>` to stderr and exit 1 (requirement 6).

## Scope

| Path | Change |
|---|---|
| `src/docket/views.py` | edit: add `task_line`, `task_detail`, `refusal_text` |
| `src/docket/cli.py` | edit: the messages, the `tasks` group, `add`, `list`, `show` |
| `tests/unit/test_views_tasks_more.py`, `tests/e2e/test_cli_tasks_more.py` | create, only if coverage needs them |
| `docs/progress.md` | append your entry |

## Out of scope

- `start`, `done`, `cancel`, `reopen`, `edit` and `plan` (Phase 1f).
- The audit history in `show`; filters other than `--all`; JSON output; colour, tables or rich formatting of your own; paging.
- Words for dates ("Friday", "tomorrow"); any `--zone` option.
- A `--source` option: every task added here is the owner's.
- Any change to `deadlines.py`, `store.py`, `core.py`, `config.py`, a given file, `AGENTS.md` or the design docs.

## Rules that bite

- **Nothing without approval**: `add` creates only through `core.create_task` with source `owner`; no command writes to the store any other way.
- **No machine zone, no locale**: every time is shown through `docket.views` in `DOCKET_TIME_ZONE`.
- **Error output is constant text** (the messages above, the core's sentences, the settings' messages); only a task id you typed is ever echoed.
- **Time through the module**: `clock.now()`, never `datetime.now()`, and never `from docket.clock import now`.
- Commands start with `.venv/bin/python`; no bare `python3`, `pytest` or `ruff`.

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest --no-cov -q --ignore=tests/e2e/test_cli_tasks.py --ignore=tests/unit/test_views_tasks.py` (before you start) | `345 passed` |
| `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 411 passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest tests/unit/test_views_tasks.py tests/e2e/test_cli_tasks.py --no-cov -q` | `66 passed` |
| `.venv/bin/python -m coverage report --include=src/docket/views.py,src/docket/cli.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| `.venv/bin/python docs/verification/probe-01e.py` | last line `FAILURES 0` |
| `grep -c "^## Phase 1e: " docs/progress.md` | `1` |
| `.venv/bin/python scripts/check_reports.py --phase 1e` | `Reports OK.` |
| `git diff HEAD --stat -- tests/unit/test_views_tasks.py tests/e2e/test_cli_tasks.py docs/verification/probe-01e.py` | no output |
| `git status --short` | only the Scope paths |

### Searches

Each prints nothing.

```zsh
git grep --untracked -n -E 'import (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)|from (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)' -- src
git grep --untracked -n -E 'print\(|logging|logger|warnings\.warn' -- src ':!src/docket/cli.py'
git grep --untracked -n -E 'datetime\.now|datetime\.utcnow|date\.today|time\.time\(|from docket\.(clock|ids) import' -- src ':!src/docket/clock.py'
git grep --untracked -n -E '\.(insert_task|update_task|append_audit)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'
git grep --untracked -n -E 'os\.environ|getenv\(|strftime\(|import locale' -- src/docket/cli.py src/docket/views.py
git grep --untracked -n -E 'ollama|anthropic|openai|langchain' -- src
git grep --untracked -n -E 'pragma: no cover|noqa' -- src/docket/cli.py src/docket/views.py
```

## Corrections

Added 2026-11-14, after the first coder run stopped and the first review found no progress entry.

1. **`tests/e2e/test_cli_tasks.py::test_every_task_command_needs_your_time_zone`, rows `wrong-case-add`, `wrong-case-list`, `wrong-case-show`.** The test set `DOCKET_TIME_ZONE=america/new_york` and then, to find the data folder, called `get_settings()` itself, which raises `ConfigError` for that zone. The command was right; the test's own last line could not run. The test now takes the data folder from `tmp_path / "data"` (where `tests/conftest.py` puts `DOCKET_DATA_DIR`), and imports `Path`. Nothing else in the spec changes: no requirement, message or count. The 66 given tests pass against the code the coder already wrote, with no change to it.

The coder keeps the code it wrote and finishes the phase: run every command under Acceptance, then write the progress entry.
