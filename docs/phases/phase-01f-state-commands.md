# Phase 1f: State commands

## Goal

Let you move a task through its states from the command line: `docket tasks start`, `done`, `cancel` and `reopen`. Each goes through `core.change_state` with you as the actor, prints one sentence, and treats a repeat as harmless: `t3 is already done.` with exit code 0 and nothing written. This phase also adds the given test Phase 1e's review found missing, that `add --due` reads no clock of its own. `edit` and `plan` are Phase 1g.

Sections: `core`. The `tooling` section runs in the full check.

Follow `docs/phase-conventions.md`. N is 414, the tests the previous phase left passing.

Start: `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_views_changes.py --ignore=tests/e2e/test_cli_states.py` must show `414 passed`. The ignored files import a name you create or call commands you create.

## Facts

Each checked on this machine on 2026-11-14.

- **Phase 1c's `change_state(store, task_id, action, *, actor)`** checks the action and the actor, reads the clock once, then loads the task inside one transaction; it returns `Outcome(task, changed)` and raises `CoreError` with `unknown_task` or `task_ended`. A repeat returns `changed=False` with the task as stored.
- **Phase 1e's `cli.py`** has private helpers for the shared start (`_home`: settings, then `home_zone`), opening the store (`_store`), and refusing (`_fail`: stderr, exit 1). `refusal_text("task_ended", "t1")` is `Task t1 has ended; reopen it first.`; `refusal_text("unknown_task", "t9")` is `There is no task t9.`
- **Phase 1e's review** found that no given test catches `add` reading the clock for its due line: its spot check's test added a task with no deadline. `test_adding_with_a_deadline_reads_only_the_cores_clock` closes that gap. It passes on today's code (a guard).
- **Typer** reports a missing argument as `Missing argument '<parameter name>'.` on stderr with exit 2.

## Owner's decisions

Decided 2026-11-14:

- **Split:** 1f the four state commands and the `add --due` clock test (this phase); 1g `edit` and `plan`.
- **A repeat says so and exits 0**: `t3 is already done.`, nothing written.
- Earlier: refusals are plain sentences on stderr with exit 1; every `docket tasks` command needs `DOCKET_TIME_ZONE`.

## Architect's decisions

- **The actor is always `owner`**: the command line is you.
- **The already-sentence names the task's state as stored**, not the action's target: Reopen on a task in progress says `t3 is already in progress.`
- **The state commands read no clock**: their sentences carry no time, so the core's one read is the only one.
- **Every `tasks` command still checks `DOCKET_TIME_ZONE` first**, though these four print no time, so the rule has no exceptions.

## Requirements

1. **`src/docket/views.py`, `change_text(action: str, outcome: Outcome) -> str`**: when `outcome.changed`, `<Verb> <id>: <title>` with `Started`, `Done`, `Cancelled` or `Reopened` for `start`, `done`, `cancel` or `reopen`; otherwise `<id> is already <state>.` with the state as `open`, `in progress`, `done` or `cancelled`.
2. **Four commands on the `tasks` group**: `docket tasks start TASK_ID`, `done TASK_ID`, `cancel TASK_ID`, `reopen TASK_ID` (the argument is named `task_id`). Each:
   - starts as every `tasks` command does (Phase 1e, requirement 6), before the store is opened or the clock read;
   - opens the store and calls `core.change_state(store, task_id, <its action>, actor="owner")`;
   - on a `CoreError`, prints `refusal_text(code, task_id)` to stderr and exits 1;
   - otherwise prints `change_text(<its action>, outcome)` to stdout and exits 0, whether or not anything changed.
3. **No clock of their own**: the four commands never call `clock.now()`; `add` still reads none (Phase 1e).
4. **The commands decide nothing**: the transition, the repeat and the refusal all come from `core.change_state`.
5. **Progress entry** for `## Phase 1f: State commands (YYYY-MM-DD)` at the end of `docs/progress.md`.

## Given files

Already committed with this spec; never change them.

| File | What it is |
|---|---|
| `tests/unit/test_views_changes.py` | 10 tests from 2 functions (requirement 1) |
| `tests/e2e/test_cli_states.py` | 42 tests from 9 functions (requirements 2 to 4). `test_adding_with_a_deadline_reads_only_the_cores_clock` passes today: it guards Phase 1e's `add` |
| `docs/verification/probe-01f.py` | The verifier's probe |

Given test count: **52**.

## Tests to write

The given tests cover every requirement's main cases. To reach full coverage, add behaviour tests in new `*_more.py` files beside them, never by changing a given test.

## Scope

| Path | Change |
|---|---|
| `src/docket/views.py` | edit: add `change_text` |
| `src/docket/cli.py` | edit: add `start`, `done`, `cancel`, `reopen` |
| `tests/unit/test_views_changes_more.py`, `tests/e2e/test_cli_states_more.py` | create, only if coverage needs them |
| `docs/progress.md` | append your entry |

## Out of scope

- `edit` and `plan` (Phase 1g).
- Several ids in one command, a `--yes` prompt, or undo.
- Any change to `core.py`, `store.py`, `config.py`, Phase 1e's commands, a given file, `AGENTS.md` or the design docs.

## Rules that bite

- **Nothing without approval**: the commands change tasks only through `core.change_state`, with actor `owner`.
- **Error output is constant text**: only a task id you typed is echoed.
- **Time through the module**: these commands read no clock at all.
- If you stop before finishing, still write the progress entry with a `Stopped:` first follow-up (`docs/phase-conventions.md`, "When you stop").
- Commands start with `.venv/bin/python`; no bare `python3`, `pytest` or `ruff`.

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_views_changes.py --ignore=tests/e2e/test_cli_states.py` (before you start) | `414 passed` |
| `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 466 passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest tests/unit/test_views_changes.py tests/e2e/test_cli_states.py --no-cov -q` | `52 passed` |
| `.venv/bin/python -m coverage report --include=src/docket/views.py,src/docket/cli.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| `.venv/bin/python docs/verification/probe-01f.py` | last line `FAILURES 0` |
| `grep -c "^## Phase 1f: " docs/progress.md` | `1` |
| `.venv/bin/python scripts/check_reports.py --phase 1f` | `Reports OK.` |
| `git diff HEAD --stat -- tests/unit/test_views_changes.py tests/e2e/test_cli_states.py docs/verification/probe-01f.py` | no output |
| `git status --short` | only the Scope paths |

### Searches

Each prints nothing.

```zsh
git grep --untracked -n -E 'import (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)|from (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)' -- src
git grep --untracked -n -E 'print\(|logging|logger|warnings\.warn' -- src ':!src/docket/cli.py'
git grep --untracked -n -E 'datetime\.now|datetime\.utcnow|date\.today|time\.time\(|from docket\.(clock|ids) import' -- src ':!src/docket/clock.py'
git grep --untracked -n -E '\.(insert_task|update_task|append_audit)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'
git grep --untracked -n -E 'actor=.(agent|email).' -- src/docket/cli.py
git grep --untracked -n -E 'os\.environ|getenv\(|strftime\(|import locale' -- src/docket/cli.py src/docket/views.py
git grep --untracked -n -E 'ollama|anthropic|openai|langchain' -- src
git grep --untracked -n -E 'pragma: no cover|noqa' -- src/docket/cli.py src/docket/views.py
```
