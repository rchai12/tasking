# Phase 1c: Task rules

## Goal

Make `docket.core` the one place where a task is created or changed, so that a Discord press, a `docket` command and a Conductor tool all go through the same rules and leave the same record. This phase builds the title rule, creating a task, the state changes (start, done, cancel, reopen) and edits (title, deadline, work time), each committed with its audit rows in one transaction. Repeating a change is harmless: it reports that nothing changed and writes nothing. Retry keys from a source (`Idempotency-Key`, `request_key`) come with the intake API (stage 2) and the MCP tools (stage 6); the `docket tasks` commands are Phase 1d.

Sections: `core`. The `tooling` section runs in the full check.

Follow `docs/phase-conventions.md`. N is 202, the tests the previous phase left passing.

Start: `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_core.py` must show `202 passed`. The ignored file imports the module you create.

## Facts

Each checked on this machine on 2026-11-14 with Python 3.12.16.

- **`str.strip()`** removes Unicode whitespace at the ends, the no-break space (` `, category Zs) and the line and paragraph separators included, but not the zero-width space (`​`) or the byte-order mark (`﻿`), which are category Cf and not whitespace. So the title rule needs both the strip comparison and the category check.
- **The zero-width joiner** (`‍`) is category Cf, so an emoji sequence joined by it (a family emoji) is refused. The email service's extractor refuses the same categories, so the two agree.
- **The store** (Phase 1b) refuses a write outside `Store.transaction()`, refuses a non-UTC `at`, raises `StoreError(UNKNOWN_TASK_MESSAGE)` from `update_task` and `append_audit` for an unknown id, returns `None` from `task()` for an unknown or malformed id, and lets the schema's CHECKs fail as `sqlite3.IntegrityError`. Its `audit_log.action` CHECK allows exactly `create`, `start`, `done`, `cancel`, `reopen`, `retitle`, `deadline`, `work_time`, and `actor` exactly `owner`, `agent`, `email`.
- **`tests.support.fixed_times`** makes `clock.now()` return its moments in order and raises `StopIteration` once they run out, so a test with no moments fails on any clock read.

## Owner's decisions

Decided 2026-11-14:

- **An ended task must be reopened before any edit**: on a done or cancelled task only Reopen works; an edit of its title, deadline or work time is refused.
- **A deadline that would end before the planned work time is refused**; nothing is cleared to make room. The same holds for a work time that would end after the deadline.
- **Past deadlines and work times are allowed**, at creation and in an edit: the approval already happened. The task is overdue at once.
- **One phase, three functions**: `create_task`, `change_state` (start, done, cancel, reopen) and `edit_task` (title, deadline, work time).
- Earlier: done and cancelled tasks can be reopened at any time; titles are refused, never rewritten; task ids are `t1`, `t2`.

## Architect's decisions

- **Errors are codes.** `CoreError` carries one constant code, which is also its text, so an MCP tool or an API route can pass it on unchanged. No code names a title, an id or a value.
- **Repeats change nothing.** A state change to the state the task is already in, and an edit to values it already has, return `Outcome(changed=False)` and write nothing, no audit row and no `updated_at`.
- **A press on the wrong ended task is refused, not ignored**: Done on a cancelled task, Cancel on a done task, and Start on either raise `task_ended`, so the caller can show the task's real state.
- **The actor of a creation follows its source**: `email` for `email`, `agent` for `agent`, `owner` for `owner` and for `proposal` (the owner's press approved it).
- **Checks in a fixed order**: the arguments first, with no clock read and no store access; then one clock read; then, inside one transaction, the task's existence, whether it has ended, and the work-time conflict.
- **The audit rows** carry only what changed, as JSON values; a deadline and a work time as small objects with their instant written like the store's text.
- **Critical module:** `core.py` (added to `scripts/critical_modules.txt`).

## Requirements

1. **`src/docket/core.py`, codes**: `UNKNOWN_TASK = "unknown_task"`, `INVALID_TITLE = "invalid_title"`, `INVALID_SOURCE = "invalid_source"`, `INVALID_REFERENCE = "invalid_reference"`, `INVALID_ACTOR = "invalid_actor"`, `INVALID_ACTION = "invalid_action"`, `TASK_ENDED = "task_ended"`, `WORK_AFTER_DEADLINE = "work_after_deadline"`. `class CoreError(Exception)`: built with one code; its `code` attribute and `str()` are that code.
2. **`Outcome`**, a frozen dataclass: `task: Task`, `changed: bool`.
3. **`check_title(title: object) -> None`** raises `CoreError(INVALID_TITLE)` unless `title` is a `str` of 1 to 100 characters, equal to `title.strip()`, with no character whose `unicodedata.category` is `Cc`, `Cf`, `Zl` or `Zp`. It never changes a title.
4. **Snapshots** used in audit rows: a deadline is `{"at": <at.isoformat(timespec="microseconds")>, "zone": <zone>, "time_given": <bool>}`, a work time is `{"start": <start.isoformat(timespec="microseconds")>, "minutes": <int>, "zone": <zone>}`, and no deadline or work time is `None`.
5. **`create_task(store, *, title, source, deadline=None, work=None, provider=None, message_id=None, link=None) -> Task`** checks, in this order, raising the first that fails:
   - the title (requirement 3);
   - the source, one of `email`, `agent`, `proposal`, `owner` (`INVALID_SOURCE`);
   - the reference (`INVALID_REFERENCE`): for `email`, `provider` is `gmail`, `outlook` or `yahoo` and `message_id` and `link` are non-empty strings; for any other source all three are `None`;
   - when both a deadline and a work time are given, `work.end <= deadline.at` (`WORK_AFTER_DEADLINE`).

   Then it reads the clock once and, in one transaction, inserts the task as `open` with `created_at` and `updated_at` that moment and appends one `create` row: `before` is `{}`, `after` is `{"title", "state", "deadline", "work", "source", "provider", "message_id", "link"}` with the snapshot of each, and the actor follows the source (Architect's decisions). It returns the new `Task`.
6. **`change_state(store, task_id, action, *, actor) -> Outcome`** checks the action, one of `start`, `done`, `cancel`, `reopen` (`INVALID_ACTION`), then the actor, one of `owner`, `agent`, `email` (`INVALID_ACTOR`). Then it reads the clock once and, in one transaction, loads the task (`UNKNOWN_TASK` when there is none) and applies this table:

   | State | start | done | cancel | reopen |
   |---|---|---|---|---|
   | open | in_progress | done | cancelled | no change |
   | in_progress | no change | done | cancelled | no change |
   | done | `TASK_ENDED` | no change | `TASK_ENDED` | open |
   | cancelled | `TASK_ENDED` | `TASK_ENDED` | no change | open |

   A change sets the state and `updated_at` and appends one row whose action is the action, with `before` `{"state": <old>}` and `after` `{"state": <new>}`. No change returns `Outcome(task, False)` with the task as stored and writes nothing. A change returns `Outcome(<the updated task>, True)`.
7. **`edit_task(store, task_id, *, actor, title=UNCHANGED, deadline=UNCHANGED, work=UNCHANGED) -> Outcome`** (`UNCHANGED` is the store's) checks the actor (`INVALID_ACTOR`), then the title when one is given (requirement 3). Then it reads the clock once and, in one transaction:
   - loads the task (`UNKNOWN_TASK`);
   - refuses an ended task (`done` or `cancelled`) with `TASK_ENDED`, whatever was given;
   - takes the new deadline and work time (the given value, or the task's own when `UNCHANGED`; `None` clears) and refuses `WORK_AFTER_DEADLINE` when both are set and the work time ends after the deadline;
   - finds the fields whose new value differs from the stored one. None: returns `Outcome(task, False)` and writes nothing. Otherwise it updates those fields and `updated_at` in one `update_task` call and appends one row per changed field, in this order: `retitle` (`{"title": <old>}` to `{"title": <new>}`), `deadline` (`{"deadline": <snapshot>}`), `work_time` (`{"work": <snapshot>}`), and returns `Outcome(<the updated task>, True)`.
8. **One transaction per call.** The task is read, and every write made, inside one `store.transaction()`, so a failure anywhere leaves the store as it was and two processes changing the same task queue instead of both changing it.
9. **The clock** is read through the module (`clock.now()`), exactly once in each call that passes its argument checks, and never in a call refused by them.
10. **Only the core writes.** No other module calls `insert_task`, `update_task` or `append_audit`.
11. **Progress entry** for `## Phase 1c: Task rules (YYYY-MM-DD)` at the end of `docs/progress.md`.

## Given files

Already committed with this spec; never change them.

| File | What it is |
|---|---|
| `tests/integration/test_core.py` | 89 tests from 22 functions (requirements 1 to 10) |
| `scripts/critical_modules.txt` | Adds `core.py` |
| `docs/verification/probe-01c.py` | The verifier's probe |

Given test count: **89**.

## Tests to write

The given tests cover every requirement's main cases. To reach full coverage, add behaviour tests in a new `tests/integration/test_core_more.py`, never by changing a given test.

## Scope

| Path | Change |
|---|---|
| `src/docket/core.py` | create |
| `tests/integration/test_core_more.py` | create, only if coverage needs it |
| `docs/progress.md` | append your entry |

## Out of scope

- Retry keys from a source (`Idempotency-Key`, `request_key`), follow-up links, proposals and their approval (stages 2, 6 and 10).
- Reminders, planning them on a change, voiding them on Done (stage 3), and calendar writes (stage 7).
- Commands, display text, settings (Phase 1d).
- Checking that a deadline or work time is in the future: the owner allows past ones.
- Clearing a work time to make room for a deadline, or moving one with the other.
- Validating `Deadline` and `WorkTime` again: they check themselves (Phase 1a).
- Any SQL, a cache, threads or retries in the core.
- Any change to a given file, `AGENTS.md` or the design docs.

## Rules that bite

- **Nothing without approval**: the core trusts its caller to be an approved source; it adds no way to create a task other than `create_task`.
- **Every change and its audit rows commit together**, or nothing does.
- **Error messages are the codes only**: never a title, an id or a library's error text.
- **Time through the module**: `clock.now()`, never `datetime.now()`, and never `from docket.clock import now`.
- Commands start with `.venv/bin/python`; no bare `python3`, `pytest` or `ruff`.

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_core.py` (before you start) | `202 passed` |
| `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 291 passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest tests/integration/test_core.py --no-cov -q` | `89 passed` |
| `.venv/bin/python -m coverage report --include=src/docket/core.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| `.venv/bin/python docs/verification/probe-01c.py` | last line `FAILURES 0` |
| `grep -c "^## Phase 1c: " docs/progress.md` | `1` |
| `.venv/bin/python scripts/check_reports.py --phase 1c` | `Reports OK.` |
| `git diff HEAD --stat -- tests/integration/test_core.py scripts/critical_modules.txt docs/verification/probe-01c.py` | no output |
| `git status --short` | only the Scope paths |

### Searches

Each prints nothing.

```zsh
git grep --untracked -n -E 'import (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)|from (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)' -- src
git grep --untracked -n -E 'print\(|logging|logger|warnings\.warn' -- src ':!src/docket/cli.py'
git grep --untracked -n -E 'datetime\.now|datetime\.utcnow|date\.today|time\.time\(|from docket\.(clock|ids) import' -- src ':!src/docket/clock.py'
git grep --untracked -n -E '\.(insert_task|update_task|append_audit)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'
git grep --untracked -n -E 'sqlite3|execute\(|_connection' -- src/docket/core.py
git grep --untracked -n -E 'ollama|anthropic|openai|langchain' -- src
git grep --untracked -n -E 'pragma: no cover|noqa' -- src/docket/core.py
```
