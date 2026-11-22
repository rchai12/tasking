# Phase 5c: Import direction

## Goal

Remove the import cycle that two hidden imports keep working today (`store` → `reminders` → `store`, and `reminders` → `views` → `core` → `reminders`). The pure reminder planner moves to a new `src/docket/reminder_plan.py`, which imports no store. The reminder notice text and the digest heading move to `views`. `core`, `store` and `_store_migrate` import the planner at module top. After that, no `docket` import is hidden in a function or a `TYPE_CHECKING` block except the one that keeps the MCP SDK out of other commands. Every planned reminder, notice and heading stays word for word and instant for instant, and every name tests reach through `reminders` stays there. One source per closed list (audit finding 6) is Phase 5d.

Sections: `core`. The `tooling` section runs in the full check.

Follow `docs/phase-conventions.md`. N is 1896, the tests the previous phase left passing.

Start: `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_import_direction.py` must show `1896 passed`. The ignored file is this phase's new given test file.

## Facts

- Hidden `docket` imports today:
  - `store.py:30-31`: `PlannedReminder` from `docket.reminders`, under `if TYPE_CHECKING`.
  - `_store_migrate.py:10-11`: `Store` from `docket.store`, under `if TYPE_CHECKING`.
  - `_store_migrate.py:81`: `from docket import reminders`, inside the backfill.
  - `reminders.py:117`: `from docket.views import deadline_text`, inside `send_digest`.
  - `cli.py:80`: `from docket.mcp_server import server`, inside `mcp serve`, so other commands never load the MCP SDK.
- `reminders.py` holds the planner (`LATE_MINUTES`, `_HOUR`, `_KIND_ORDER`, `PlannedReminder`, `plan_reminders`, lines 12-50) beside the sender, the digest and the loop. `plan_reminders(task, now)` reads only `task.state`, `task.deadline` and `task.work`. `send_digest` also uses `LATE_MINUTES`.
- `notice_text` and its `_NOTICE` table (`reminders.py:16-23` and `53-57`) and `digest_heading` (`reminders.py:102-104`) are pure text.
- Tests reach the moved names through `reminders`:
  - `reminders.plan_reminders` and `from docket.reminders import plan_reminders`.
  - `reminders.PlannedReminder` (11 uses).
  - `reminders.LATE_MINUTES`.
  - `reminders.notice_text` and `reminders.digest_heading`, including two `inspect.signature` checks.
  - No test replaces any of them with `monkeypatch`.
- `views.py` imports `core` only for `Outcome` (owner's decision: it stays). Once `core` imports the planner from `reminder_plan`, nothing `views` imports leads back to `reminders`.
- `store` imports `_store_migrate` and `_store_migrate` imports `store`, both at module top. This works in either order, as Phase 5b showed, so the given cycle test treats `store` and its `_store_*` parts as one node.
- Starting all of the package's modules in fresh interpreters at once takes about 0.4 s here.
- A throwaway draft changed about 120 lines and added a 47-line `reminder_plan.py`:

  | Module | Lines added | Lines deleted |
  |---|---|---|
  | `reminders.py` | 7 | 55 |
  | `views.py` | 21 | 0 |
  | `_store_migrate.py` | 9 | 14 |
  | `store.py` | 4 | 6 |
  | `core.py` | 1 | 1 |

  With it, the full suite passed (1907) and every `docket` module was covered at 100% with branches.

## Owner's decisions

- **Split (2026-11-22):** the per-aggregate store split (old 5c and 5d) is dropped. Audit finding 3's layout closes with the table modules and `_store_migrate.py`. The remaining work is renumbered:

  | Phase | Covers |
  |---|---|
  | 5c (this one) | Import direction (finding 5) |
  | 5d | One source per closed list (finding 6) |
  | 5e | Visible reminder passes |
  | 5f on | The service |

- **`Outcome` (2026-11-22):** it stays in `core`, and `views` keeps importing it.
- **Notice text (2026-11-22):** the notice texts and the digest heading move to `views.py`, not a new module.

## Architect's decisions

- **The planner's input.** `reminder_plan` defines a `Plannable` protocol: read-only `state`, `deadline` and `work`. `plan_reminders(task: Plannable, now: datetime)` keeps its name, parameters and behaviour. A `Task` is one, and so is any object with those three attributes.
- **Where the moved names live.** `LATE_MINUTES`, the private kind order and the hour step move with the planner. `CLAIM_MINUTES` stays in `reminders`.
- **Old names stay reachable.** `reminders` re-exports `LATE_MINUTES`, `PlannedReminder` and `plan_reminders`. It imports `notice_text` and `digest_heading` from `views`, so each name in `reminders` is the same object as in its new home.
- **The `_store_migrate` annotation.** It names the store as `"store_module.Store"` (a string annotation), so it needs no `TYPE_CHECKING` block.

## Requirements

1. **Planner module.** A new `src/docket/reminder_plan.py` holds `LATE_MINUTES`, `PlannedReminder`, `Plannable` and `plan_reminders`, moved from `reminders.py` unchanged apart from the input annotation. From `docket` it imports only `docket.deadlines` and `docket.domain`.
2. **Names kept in `reminders`.** `reminders.LATE_MINUTES`, `reminders.PlannedReminder`, `reminders.plan_reminders`, `reminders.notice_text` and `reminders.digest_heading` are the same objects as in their new modules. `reminders.py` defines none of them itself.
3. **Text in `views`.** `notice_text(kind, missed)`, its notice table and `digest_heading(count)` move to `views.py` word for word. `reminders` imports them, and `deadline_text`, from `views` at module top.
4. **Planner imports at the top.** `core` imports `plan_reminders` from `docket.reminder_plan`. `store` imports `PlannedReminder` from it at module top. `_store_migrate` imports `docket.reminder_plan` at module top. None of the three imports `docket.reminders`.
5. **Nothing hidden.** No module under `src/docket/` imports a `docket` module inside a function, a class or an `if` block, `TYPE_CHECKING` included. The one exception is `cli.py`'s `from docket.mcp_server import server`.
6. **No cycle.** The `docket` import graph has no cycle, with `store` and its `_store_*` parts counted as one node.
7. **Same answers.** Every plan, notice and heading equals what the spec commit's `reminders` gives for the same input. No public signature changes, and every existing test passes unchanged.
8. **Critical module.** `scripts/critical_modules.txt` gains the line `reminder_plan.py`, directly after `reminders.py`.
9. **Given markers**: `tests/integration/test_import_direction.py` carries 6 strict `xfail` markers with reasons starting `Phase 5c given test: remove this marker`, one line each. Delete all 6 once requirements 1 to 8 are done, and nothing else in the file. A strict marker on a passing test fails the run, so `check.py` tells you when.
10. **Progress entry** for `## Phase 5c: Import direction (YYYY-MM-DD)` at the end of `docs/progress.md`.

## Given files

Already committed with this spec; never change them, except the markers of requirement 9.

| File | What it is |
|---|---|
| `tests/integration/test_import_direction.py` | Tests that the moved code imports and answers as required (list below) |
| `docs/verification/probe-05c.py` | The verifier's probe |

The given tests check that:

- every module under `src/docket/` imports alone in a fresh interpreter (a guard that passes today);
- the only hidden `docket` import is `cli.py`'s MCP server import;
- the import graph has no cycle, with store parts counted as one node;
- `reminder_plan` imports only `deadlines` and `domain`;
- `plan_reminders` plans an object that is not a `Task`, with a New York deadline on 2026-11-01;
- the five moved names are the same objects through `reminders`;
- `core`, `store` and `_store_migrate` import the planner module, and not `reminders`.

Given test count: **11** new (`test_import_direction.py`: 7 functions, 11 tests). Before you start, the file shows 10 xfailed and 1 passed: `test_every_module_imports_alone_in_a_fresh_interpreter` guards behaviour that must not change.

## Tests to write

None are required: the given tests, the existing planner, sending and digest tests, and the probe cover requirements 1 to 8 and every line and branch of the draft. If a helper you add has a branch they miss, cover it in a new `tests/integration/test_import_direction_more.py`, never by changing a given test.

## Scope

| Path | Change |
|---|---|
| `src/docket/reminder_plan.py` | create: requirement 1 |
| `src/docket/reminders.py` | edit: requirements 1 to 3 |
| `src/docket/views.py` | edit: requirement 3 |
| `src/docket/core.py` | edit: requirement 4 (the import line only) |
| `src/docket/store.py` | edit: requirement 4 |
| `src/docket/_store_migrate.py` | edit: requirements 4 and 5 |
| `scripts/critical_modules.txt` | edit: requirement 8 |
| `tests/integration/test_import_direction.py` | delete the 6 markers only |
| `tests/integration/test_import_direction_more.py` | create, only if you need it |
| `docs/progress.md` | append your entry |

## Out of scope

- Audit finding 6 (Phase 5d):
  - `DEADLINE_KINDS`, `ENDED_STATES` or an explicit `OPEN_STATES` in `domain`;
  - deriving the kind order or `core._replace_reminders` from `REMINDER_KINDS`;
  - `DUE_WINDOW` and `LATE_MINUTES[0]`;
  - the email client, the retry-key bound, `intake._REPLAY` and `intake._text`.
- Moving `Outcome` out of `core` (owner's decision).
- Moving `cli.py`'s MCP server import to the top.
- Any public signature, schema, migration, message or reminder rule.
- Any change to a given file beyond the markers, `AGENTS.md` or the design docs.

## Rules that bite

- **Code decides everything**: reminder times are unchanged instant for instant. The probe compares every plan with the spec commit's.
- **Titles are untrusted** and notice text is constant: the moved text keeps its exact words.
- **Critical modules**: `reminder_plan.py`, `reminders.py`, `store.py` and `_store_migrate.py` are critical; every line and branch is covered, with no `pragma: no cover`.
- **Every existing test passes unchanged**, the planner's daylight-saving cases included.
- If you stop before finishing, still write the progress entry with a `Stopped:` first follow-up (`docs/phase-conventions.md`, "When you stop").
- Commands start with `.venv/bin/python`; no bare `python3`, `pytest` or `ruff`.

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_import_direction.py` (before you start) | `1896 passed` |
| `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1907 passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest tests/integration/test_import_direction.py --no-cov -q` | `11 passed` |
| `.venv/bin/python -m coverage report --include=src/docket/reminder_plan.py,src/docket/reminders.py,src/docket/store.py,src/docket/_store_migrate.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| `.venv/bin/python docs/verification/probe-05c.py` | last line `FAILURES 0` |
| `grep -c "^## Phase 5c: " docs/progress.md` | `1` |
| `.venv/bin/python scripts/check_reports.py --phase 5c` | `Reports OK.` |
| `git diff HEAD --stat -- docs/verification/probe-05c.py tests/support.py tests/conftest.py tests/sections.toml docs/reviews AGENTS.md pyproject.toml scripts/check.py scripts/tooling_modules.txt src/docket/schema.py src/docket/domain.py src/docket/deadlines.py src/docket/cli.py` | no output |
| `git diff HEAD --numstat -- tests/integration/test_import_direction.py` | `0	6	tests/integration/test_import_direction.py` (the markers, nothing else) |
| `git diff HEAD --numstat -- scripts/critical_modules.txt src/docket/core.py` | `1	0	scripts/critical_modules.txt` and `1	1	src/docket/core.py` |
| `git status --short` | only the Scope paths |

### Searches

Each prints nothing.

```zsh
git grep --untracked -n -E 'import (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)|from (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)' -- src
git grep --untracked -n -E 'print\(|logging|logger|warnings\.warn' -- src ':!src/docket/cli.py'
git grep --untracked -n -E 'datetime\.now|datetime\.utcnow|date\.today|time\.time\(|from docket\.(clock|ids) import' -- src ':!src/docket/clock.py'
git grep --untracked -n -E 'pragma: no cover|noqa' -- src/docket/reminder_plan.py src/docket/reminders.py src/docket/store.py src/docket/_store_migrate.py src/docket/views.py
git grep --untracked -n -E 'TYPE_CHECKING' -- src
git grep --untracked -n -E 'from docket\.reminders import|from docket import .*reminders([^_A-Za-z]|$)' -- src/docket/core.py src/docket/store.py src/docket/_store_migrate.py src/docket/reminder_plan.py src/docket/views.py
git grep --untracked -n -E '_NOTICE|def (notice_text|digest_heading|plan_reminders)\(|class PlannedReminder' -- src/docket/reminders.py
```
