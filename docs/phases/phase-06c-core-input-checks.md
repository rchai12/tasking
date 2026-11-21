# Phase 6c: Core input checks

## Goal

Make `docket.core` refuse a deadline or a work time that is not a real `Deadline`, `WorkTime` or `None`, with a fixed code and before it reads the clock or the store, in all three functions that take them: `create_task`, `create_task_once` and `edit_task`. Give every refusal code `core` can raise a sentence in `views.refusal_text`. Today a string or dict passed as `deadline` gets past `core` and fails in the store with `AttributeError`, and `refusal_text` raises `KeyError` for `invalid_client`, `invalid_key` and `key_reused`. The MCP write tools (6d and 6e) will call these functions with values built from agent input. This phase builds no MCP tool and changes no store, intake or CLI behaviour.

Sections: `core`. The `tooling` section runs in the full check.

Follow `docs/phase-conventions.md`. N is 1653, the tests the previous phase left passing.

Start: `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_core_value_types.py --ignore=tests/unit/test_refusal_sentences.py` must show `1653 passed`. The ignored files are this phase's given tests.

## Facts

- `core.create_task` and `core.create_task_once` take `deadline: Deadline | None` and `work: WorkTime | None`; `core.edit_task` takes `deadline: object` and `work: object`, defaulting to `store.UNCHANGED`. None of them checks the type: `_work_after_deadline` returns `False` for a value that is not an instance, and the value reaches `Store` (`core.py:63`, `core.py:124`, `core.py:188`).
- `edit_task` reads `clock.now()` after its actor and title checks and before the store; the two create functions read it after `_work_after_deadline`. The given tests give no clock moment to a refused call, so a check placed after the clock read fails with `StopIteration`.
- `Deadline` and `WorkTime` (`deadlines.py`) are frozen dataclasses that check their own fields in `__post_init__`, so an instance is always well formed; `True` and `False` are not instances of either.
- `views._REFUSALS` has sentences for 7 codes; `refusal_text` handles `unknown_task` and `task_ended` itself and looks every other code up in `_REFUSALS`, raising `KeyError` for `invalid_client`, `invalid_key` and `key_reused`.
- The HTTP intake already answers `{"error": "invalid_deadline"}` (`intake.INVALID_DEADLINE`) for a deadline it cannot parse. It always passes `core` a real `Deadline` or `None`, so nothing it answers changes.
- Every `CoreError` in `core.py` is raised with a module constant (25 calls); no other module raises `CoreError`.
- `core.py` is a critical module (`scripts/critical_modules.txt`): every line and branch must be covered. A throwaway draft of this phase changed 19 lines in `core.py` and `views.py`, and the given tests alone covered both files completely.

## Owner's decisions

- **Scope (2026-11-21):** the checks go into `edit_task`, `create_task` and `create_task_once`, so 6d's create tool is covered too (not `edit_task` only).
- **Codes (2026-11-21):** two codes, `invalid_deadline` and `invalid_work` (not one shared code). `invalid_deadline` is the same string the HTTP intake already uses.
- **Missing sentences (2026-11-21):** `refusal_text` stays a strict lookup that raises `KeyError` for a code with no sentence; a given test walks every code `core` defines, so a gap is caught before it ships (no generic fallback sentence).

## Architect's decisions

- The deadline is checked before the work time, and both come after the checks each function already makes before them (actor and title in `edit_task`; client, key, title, source and reference in the create functions), and before `_work_after_deadline` and the clock read.
- `store.UNCHANGED` means "leave it" only in `edit_task`. Passed to `create_task` or `create_task_once` it is a wrong value and is refused like any other.
- Signatures do not change: the create functions keep their annotations; the check is at run time.
- The sentences are architect's wording, in the style of the existing ones; they never echo the value.

## Requirements

1. **Codes.** `docket.core` defines `INVALID_DEADLINE = "invalid_deadline"` and `INVALID_WORK = "invalid_work"`.
2. **The check.** A `deadline` that is neither `None` nor an instance of `Deadline` raises `CoreError(INVALID_DEADLINE)`; a `work` that is neither `None` nor an instance of `WorkTime` raises `CoreError(INVALID_WORK)`. When both are wrong, the deadline's code wins.
3. **`create_task` and `create_task_once`** make the check after their existing reference check and before `_work_after_deadline`, so a refused call reads no clock, opens no transaction, writes nothing, and in `create_task_once` leaves the request key unused: the same key with right values then creates the task.
4. **`edit_task`** makes the check after its title check and before `clock.now()`, on each of `deadline` and `work` that is not `UNCHANGED`. A refused edit reads no clock and changes no row.
5. **Sentences.** `views.refusal_text` returns these, with or without a task id:

   | Code | Sentence |
   |---|---|
   | `invalid_client` | `That client is not allowed.` |
   | `invalid_key` | `A request key is 1 to 200 characters.` |
   | `key_reused` | `That request key was already used for a different request.` |
   | `invalid_deadline` | `That is not a valid deadline.` |
   | `invalid_work` | `That is not a valid work time.` |

   Every other existing sentence stays as it is, and a code with no sentence still raises `KeyError`.
6. **Nothing else changes**: no other module under `src/`, no store, intake, web, CLI or MCP behaviour, and no existing test.
7. **Given markers**: the two given test files carry strict `xfail` markers with reasons starting `Phase 6c given test: remove this marker`: seven in `tests/integration/test_core_value_types.py` and two in `tests/unit/test_refusal_sentences.py`, three lines each. Delete all nine once requirements 1 to 5 are done, and nothing else in those files. A strict marker on a passing test fails the run, so `check.py` tells you when.
8. **Progress entry** for `## Phase 6c: Core input checks (YYYY-MM-DD)` at the end of `docs/progress.md`.

## Given files

Already committed with this spec; never change them, except the markers of requirement 7.

| File | What it is |
|---|---|
| `tests/integration/test_core_value_types.py` | Each of the three functions refuses wrong-typed deadlines and work times (strings, dicts, numbers, booleans, lists, the other type, and `UNCHANGED` for the creates) with the right code, no clock read and an unchanged database; the deadline is checked first; earlier checks still come first; real values and `None` still pass; a refused keyed create leaves its key free |
| `tests/unit/test_refusal_sentences.py` | The five new sentences; every public string constant of `docket.core` has a sentence; every `CoreError` in `core.py` is raised with such a constant; an unknown code still raises `KeyError` |
| `docs/verification/probe-06c.py` | The verifier's probe |

Given test count: **53** (`test_core_value_types.py`: 9 functions, 45 tests; `test_refusal_sentences.py`: 4 functions, 8 tests). Before you start, 4 pass and 49 show as `xfailed`.

## Tests to write

None are required: the given tests cover requirements 1 to 5 and every new line and branch. If you add a private helper with a branch the given tests miss, cover it in a new `tests/integration/test_core_value_types_more.py`, never by changing a given test.

## Scope

| Path | Change |
|---|---|
| `src/docket/core.py` | edit: requirements 1 to 4 |
| `src/docket/views.py` | edit: requirement 5 |
| `tests/integration/test_core_value_types.py` | delete the seven markers only |
| `tests/unit/test_refusal_sentences.py` | delete the two markers only |
| `tests/integration/test_core_value_types_more.py` | create, only if you need it |
| `docs/progress.md` | append your entry |

## Out of scope

- Any MCP write tool, or parsing agent input into a `Deadline` or `WorkTime` (6d and 6e).
- Checking the type of any other argument, changing `check_title`, or checking a `Deadline`'s or `WorkTime`'s fields again in `core`.
- A generic fallback in `refusal_text`, new sentences for codes `core` does not define (the intake's HTTP codes), or rewording an existing sentence.
- Changing a public signature, the store, `intake.py`, `web.py`, `cli.py` or the closed lists in `domain` (5c).
- Any change to a given file beyond the markers, `AGENTS.md` or the design docs.

## Rules that bite

- **Error messages are constant text**: a sentence never names the refused value, and a `CoreError` carries only its code.
- **Refuse before reading or writing**: no `clock.now()`, no `store.transaction()` and no store call before the check; the given tests give a refused call no clock moment.
- **Every change goes through `core`**: the checks live in `core.py`, not in a caller.
- **Critical module**: every new line and branch of `core.py` is covered, with no `pragma: no cover`.
- **Time through the module**: `clock.now()`, never `datetime.now()`, and never `from docket.clock import now`.
- If you stop before finishing, still write the progress entry with a `Stopped:` first follow-up (`docs/phase-conventions.md`, "When you stop").
- Commands start with `.venv/bin/python`; no bare `python3`, `pytest` or `ruff`.

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_core_value_types.py --ignore=tests/unit/test_refusal_sentences.py` (before you start) | `1653 passed` |
| `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1706 passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest tests/integration/test_core_value_types.py tests/unit/test_refusal_sentences.py --no-cov -q` | `53 passed` |
| `.venv/bin/python -m coverage report --include=src/docket/core.py,src/docket/views.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| `.venv/bin/python docs/verification/probe-06c.py` | last line `FAILURES 0` |
| `grep -c "^## Phase 6c: " docs/progress.md` | `1` |
| `.venv/bin/python scripts/check_reports.py --phase 6c` | `Reports OK.` |
| `git diff HEAD --stat -- docs/verification/probe-06c.py tests/support.py tests/conftest.py tests/sections.toml docs/reviews AGENTS.md pyproject.toml scripts` | no output |
| `git diff HEAD --numstat -- tests/integration/test_core_value_types.py tests/unit/test_refusal_sentences.py` | two lines: 0 added, 21 deleted, `tests/integration/test_core_value_types.py`; 0 added, 6 deleted, `tests/unit/test_refusal_sentences.py` (the markers, nothing else) |
| `git status --short` | only the Scope paths |

### Searches

Each prints nothing.

```zsh
git grep --untracked -n -E 'import (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)|from (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)' -- src
git grep --untracked -n -E 'ollama|anthropic|openai|langchain' -- src
git grep --untracked -n -E 'datetime\.now|datetime\.utcnow|date\.today|time\.time\(|from docket\.(clock|ids) import' -- src ':!src/docket/clock.py'
git grep --untracked -n -E 'pragma: no cover|noqa' -- src/docket/core.py src/docket/views.py
```
