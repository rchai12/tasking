# Phase 1g: Edit and plan

## Goal

Finish stage 1's commands: `docket tasks edit` changes a task's title or deadline, and `docket tasks plan` sets or clears its planned work time. Both go through `core.edit_task` as you, so the rules that a work time must end by the deadline and that an ended task must be reopened first come from the core. A change prints the task after it; a repeat prints `Nothing changed for t3.` with exit code 0. After this phase every task command in the roadmap's stage 1 exists.

Sections: `core`. The `tooling` section runs in the full check.

Follow `docs/phase-conventions.md`. N is 466, the tests the previous phase left passing.

Start: `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_views_edits.py --ignore=tests/e2e/test_cli_edits.py` must show `466 passed`. The ignored files import names you create.

## Facts

Each checked on this machine on 2026-11-14 with typer 0.29.1.

- **Optional positional arguments**: `day: str | None = typer.Argument(None)` and `start: str | None = typer.Argument(None)` after `task_id` accept `plan t1 --clear`, `plan t1 2026-11-20 14:00 --minutes 90`, and `plan t1 --clear 2026-11-20` (the date still arrives, with `clear` true).
- **A non-number `--minutes`** (`int | None = typer.Option(None, "--minutes")`) is a usage mistake: exit 2, stderr containing `Invalid value for '--minutes'`.
- **`core.edit_task(store, task_id, *, actor, title=UNCHANGED, deadline=UNCHANGED, work=UNCHANGED)`** checks the actor, then the title when given (before the clock read and before looking the task up), then reads the clock once, then in one transaction: unknown task, ended task, a work time ending after the deadline (`work_after_deadline`), and no change (`changed=False`, nothing written).
- **`make_work_time(day, start, minutes, zone, None)`** raises `DeadlineError` with `WORK_LENGTH_MESSAGE` outside 5 to 720 minutes and `WORK_DAY_MESSAGE` past midnight; with the shapes checked first, its time and zone checks can't fail here.
- **`settings.work_minutes`** (Phase 1d) is the default length, already checked to be 5 to 720.
- **Phase 1f's review** found its S6 row's broken value wrong: a test that gives `fixed_times` no moments stops a broken command at the core's clock read, so an empty clock list is a layer. This phase's spot checks trace it.

## Owner's decisions

Decided 2026-11-14:

- **One phase for `edit` and `plan`.**
- **`edit` prints the task after the change**: `Updated t3: Pay rent, due Sat Nov 21 09:00 EST`, or `Updated t3: Pay rent, no deadline`.
- **An edit with no options is refused**: `Give --title, --due or --no-due.`, exit 1.
- Earlier: `plan t3 2026-11-20 14:00 [--minutes N]` and `plan t3 --clear`; in `edit`, `--at` needs `--due` as in `add`, and `--no-due` clears; a repeat says so and exits 0; refusals are sentences on stderr with exit 1.

## Architect's decisions

- **A repeat of either command prints `Nothing changed for <id>.`**, exit 0, nothing written.
- **`plan` prints the span**: `Planned t3: Fri Nov 20 14:00 to 15:00 EST`; clearing prints `Cleared the work time of t3.`
- **Every check the command makes itself runs before the store is opened**: the option rules, the shapes, the length and midnight. The deadline conflict, the ended task, the unknown task and the title are the core's, so they come after.
- **The texts are shown against the task's `updated_at`**, so neither command reads a clock of its own.
- **`plan` passes no deadline to `make_work_time`**: the core alone decides the deadline conflict, with the deadline as stored.

## Requirements

1. **`src/docket/views.py`, `edited_text(outcome: Outcome, home: str) -> str`**: unchanged: `Nothing changed for <id>.`; changed: `Updated <id>: <title>`, then `, due <deadline_text(deadline, home, task.updated_at)>` or `, no deadline`.
2. **`planned_text(outcome: Outcome, home: str) -> str`**: unchanged: `Nothing changed for <id>.`; changed with no work time: `Cleared the work time of <id>.`; changed with one: `Planned <id>: <work_text(work, home, task.updated_at)>`.
3. **`src/docket/cli.py`, messages**: `NOTHING_TO_EDIT_MESSAGE = "Give --title, --due or --no-due."`, `BOTH_DUES_MESSAGE = "--due and --no-due can't be used together."`, `PLAN_NEEDS_MESSAGE = "Give a date and a start time, or --clear."`, `CLEAR_ALONE_MESSAGE = "--clear takes no date, start time or --minutes."`, `PLAN_DATE_MESSAGE = "The date must look like 2026-11-20."`, `PLAN_TIME_MESSAGE = "The start time must look like 14:00."`, `MINUTES_MESSAGE = "--minutes must be 5 to 720."`, `MIDNIGHT_MESSAGE = "A work time must end by midnight."`.
4. **`docket tasks edit TASK_ID [--title T] [--due YYYY-MM-DD [--at HH:MM]] [--no-due]`**. After the shared start (Phase 1e, requirement 6) it checks, in order, each printed to stderr with exit 1:
   - none of `--title`, `--due`, `--no-due`, `--at` given (`NOTHING_TO_EDIT_MESSAGE`; an empty `--title ""` counts as given);
   - `--due` and `--no-due` together (`BOTH_DUES_MESSAGE`);
   - `--at` without `--due` (Phase 1e's `AT_WITHOUT_DUE_MESSAGE`);
   - `--due` and `--at` as Phase 1e's `add` checks them (`DUE_MESSAGE`, `AT_MESSAGE`), giving the deadline `make_deadline(day, at or None, home)`.

   Then it opens the store and calls `core.edit_task(store, task_id, actor="owner", title=<given or UNCHANGED>, deadline=<the new deadline, None for --no-due, or UNCHANGED>)`. A `CoreError` prints `refusal_text(code, task_id)` to stderr and exits 1; otherwise it prints `edited_text(outcome, home)` and exits 0.
5. **`docket tasks plan TASK_ID [DATE START] [--minutes N] [--clear]`** (arguments `task_id`, `day`, `start`). After the shared start it checks, in order:
   - `--clear` with a date, a start or `--minutes` (`CLEAR_ALONE_MESSAGE`);
   - without `--clear`, a missing date or start (`PLAN_NEEDS_MESSAGE`);
   - the date against `[0-9]{4}-[0-9]{2}-[0-9]{2}` and as a real date (`PLAN_DATE_MESSAGE`), then the start against `[0-9]{2}:[0-9]{2}` and as a real time (`PLAN_TIME_MESSAGE`);
   - `make_work_time(day, start, minutes, home, None)` with `minutes` from `--minutes` or `settings.work_minutes`: its length refusal prints `MINUTES_MESSAGE`, its midnight refusal `MIDNIGHT_MESSAGE`.

   Then it opens the store and calls `core.edit_task(store, task_id, actor="owner", work=<the work time, or None for --clear>)`, with refusals as in requirement 4, and prints `planned_text(outcome, home)`.
6. **No clock of their own**: `edit` and `plan` never call `clock.now()`.
7. **The commands decide nothing** beyond their own option and shape checks: the conflict, the ended task, the title and repeats come from the core.
8. **Progress entry** for `## Phase 1g: Edit and plan (YYYY-MM-DD)` at the end of `docs/progress.md`.

## Given files

Already committed with this spec; never change them.

| File | What it is |
|---|---|
| `tests/unit/test_views_edits.py` | 10 tests from 3 functions (requirements 1 and 2) |
| `tests/e2e/test_cli_edits.py` | 46 tests from 11 functions (requirements 3 to 7) |
| `docs/verification/probe-01g.py` | The verifier's probe |

Given test count: **56**.

## Tests to write

The given tests cover every requirement's main cases. To reach full coverage, add behaviour tests in new `*_more.py` files beside them, never by changing a given test.

## Scope

| Path | Change |
|---|---|
| `src/docket/views.py` | edit: add `edited_text`, `planned_text` |
| `src/docket/cli.py` | edit: the messages, `edit`, `plan` |
| `tests/unit/test_views_edits_more.py`, `tests/e2e/test_cli_edits_more.py` | create, only if coverage needs them |
| `docs/progress.md` | append your entry |

## Out of scope

- Moving only the time of a deadline (`--at` alone), words for dates, a `--zone` option.
- Clearing or moving a work time to make room for a new deadline: the core refuses instead.
- Editing the source, the state or the email reference; several tasks at once.
- Any change to `core.py`, `deadlines.py`, `store.py`, `config.py`, earlier commands, a given file, `AGENTS.md` or the design docs.

## Rules that bite

- **Nothing without approval**: both commands change tasks only through `core.edit_task`, with actor `owner`.
- **Error output is constant text**: only a task id you typed is echoed.
- **Time through the module**: these commands read no clock at all.
- If you stop before finishing, still write the progress entry with a `Stopped:` first follow-up (`docs/phase-conventions.md`, "When you stop").
- Commands start with `.venv/bin/python`; no bare `python3`, `pytest` or `ruff`.

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_views_edits.py --ignore=tests/e2e/test_cli_edits.py` (before you start) | `466 passed` |
| `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 522 passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest tests/unit/test_views_edits.py tests/e2e/test_cli_edits.py --no-cov -q` | `56 passed` |
| `.venv/bin/python -m coverage report --include=src/docket/views.py,src/docket/cli.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| `.venv/bin/python docs/verification/probe-01g.py` | last line `FAILURES 0` |
| `grep -c "^## Phase 1g: " docs/progress.md` | `1` |
| `.venv/bin/python scripts/check_reports.py --phase 1g` | `Reports OK.` |
| `git diff HEAD --stat -- tests/unit/test_views_edits.py tests/e2e/test_cli_edits.py docs/verification/probe-01g.py` | no output |
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

## Corrections

Added 2026-11-14, after the first coder run stopped on the probe (its `Stopped:` follow-up) and the first review reported the stop.

1. **`docs/verification/probe-01g.py`.** Every one of the walk's 900 answers agreed with the probe's oracle; the check failed only on its own reach count: a plain `--clear` on an open task with a work time came up 5 times, short of 15, because the random walk seldom lined those up. That was the probe's fault, not the code's. The walk now forces one such clear every 15 steps. Against the code the coder already wrote, the corrected probe prints `FAILURES 0`, with every kind of answer reached at least 20 times; `check.py --first core`, the coverage command and every search also pass on that code.

Nothing else changes: no requirement, message, given test or count. The coder keeps its code, runs every command under Acceptance again, and updates its existing Phase 1g entry in `docs/progress.md` (replacing the `Stopped:` follow-up), adding no second entry.
