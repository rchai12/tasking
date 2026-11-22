# Phase 5d: One source per closed list

## Goal

Give every closed list and shared bound one source in `docket.domain` (audit finding 6). Today the open and ended states are slices of `STATES`, the reminder kinds are spelled out again in the planner, `core` and `reads`, the 30-minute due window is two separate numbers, the email client is a bare `"email"` in four modules, and the retry-key bound is checked by four hand-written comparisons. After this phase `domain` names each of them once, the other modules derive from it, and every answer the app gives stays exactly as it is. The intake replay status becomes a plain `200`, and a dead branch in intake goes. Visible reminder passes are Phase 5e.

Sections: `core`. The `tooling` section runs in the full check.

Follow `docs/phase-conventions.md`. N is 1908, the tests the previous phase left passing.

Start: `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_closed_lists.py` must show `1908 passed`. The ignored file is this phase's new given test file.

## Facts

- `domain.py` (imports nothing from `docket`):
  - `OPEN_STATES = STATES[:2]` and `ENDED_STATES = STATES[2:]`, slices of `STATES = tuple(STATE_LABELS)`.
  - `CORE_CLIENTS = ("email", "agent")`, `REQUEST_KEY_MAX = 200`, `REMINDER_KINDS = ("start", "before", "due_soon", "due", "late")`.
- Reminder kinds spelled out again:
  - `reminder_plan.py:10`: `_KIND_ORDER = {"start": 0, "before": 1, "due_soon": 2, "due": 3, "late": 4}`.
  - `reminder_plan.py:26`: `kind: Literal["start", "before", "due_soon", "due", "late"]`. A `Literal` needs its values written out.
  - `core.py:441` and `445`, in `_replace_reminders`: `kinds=("before", "due_soon", "due", "late")` and `kinds=("start",)`.
  - `views.py:164-170`: the `_NOTICE` table gives each kind its text.
  - `schema.py`: the `reminders.kind` CHECK, literal SQL that tests compare with `domain`.
- `reads.py:17`: `_OPEN_STATES = ("open", "in_progress")`, used at line 65. `reads.STATUSES` (line 10) is a different list: states and the deadline statuses `due` and `overdue`.
- The due window: `deadlines.py:9` `DUE_WINDOW = timedelta(minutes=30)` (used by `status`), and `reminder_plan.py:8` `LATE_MINUTES = (30, 60, 120, 180, 240, 480, 720)`, whose first late reminder falls when the due window ends.
- The email client, as the API client (not as a task's source):
  - `clients.py:5`: `CLIENTS = ("email",)`.
  - `core.py:344`, `350` and `370`, in `add_link`: `client != "email"`, `store.request_key("email", ...)` and `client="email"`.
  - `intake.py:44` and `76`: `client != "email"`.
  - Each comparison is guarded by `isinstance(client, str)`. `tests/integration/test_intake_identity.py::test_only_email_identity_can_enter_intake[equal-nonstring]` passes a non-string that compares equal to `"email"` and expects `invalid_client`.
  - `"email"` as a source stays: `core.py:347` (`_check_reference("email", ...)`), `core.py:460`, `intake.py:83` and `views.py:61`.
- The retry-key bound is checked in four places, each with its own refusal:
  - `core.py:450-452` `_check_key` raises `CoreError(INVALID_KEY)`, used by the four keyed core calls;
  - `intake.py:101-102` `_valid_key`, answered with `400 {"error": "missing_key"}`;
  - `web.py:81`, answered with `400 {"error": "missing_key"}` before the body is parsed;
  - `store.py:193-195` `_check_retry_key(key, message)` raises `StoreError(message)` (`invalid post key`, `invalid digest key`).
- `intake.py:27-28`: `_CREATED = 201` and `_REPLAY = _CREATED - 1`. The arithmetic exists only because `tests/integration/test_domain_schema.py::test_consumers_do_not_keep_copied_parsers_domains_or_limits` refused any integer `200` in `intake`, a key bound or not (commit `54d79a3` rewrote `else 200` that way).
- `intake._text` (line 115) returns a string or raises `_BadDeadline`. `accept_task` calls it on `source`, `provider`, `message_id` and `link` (lines 60-64), which `_object` has already checked are strings, so that branch can never run there. Its one live use is the deadline's `time_zone` (line 127).
- Tests pin these values, which stay: `clients.CLIENTS == ("email",)` and its two messages, `DUE_WINDOW == timedelta(minutes=30)`, `LATE_MINUTES`, `OPEN_STATES`, `ENDED_STATES`, `CORE_CLIENTS` and `REMINDER_KINDS`. No test reaches `_REPLAY`, `_text`, `_valid_key`, `_check_key`, `_check_retry_key` or `reads._OPEN_STATES`.
- A throwaway draft changed 39 lines and deleted 32 in nine modules (`domain` 13 and 4, `intake` 10 and 13, `core` 6 and 6, the rest at most 3 each). With it, the full suite passed (1935) and every `docket` module was covered at 100% with branches.

## Owner's decisions

- **Due window (2026-11-22):** one constant, `domain.DUE_WINDOW_MINUTES = 30`. `deadlines.DUE_WINDOW` and the first late reminder are built from it.
- **Retry keys (2026-11-22):** one helper, `domain.valid_request_key(key)`. Each caller keeps its own refusal and message.
- **Email client (2026-11-22):** domain constants `EMAIL_CLIENT` and `API_CLIENTS`. `clients.CLIENTS` is `API_CLIENTS`, and the client messages keep their words.

## Architect's decisions

- **Reminder kinds.** `domain` spells out `WORK_KINDS = ("start",)` and `DEADLINE_KINDS = ("before", "due_soon", "due", "late")`, and `REMINDER_KINDS = WORK_KINDS + DEADLINE_KINDS`, so the order and the split cannot drift.
- **States.** `OPEN_STATES` and `ENDED_STATES` are spelled-out tuples, not slices; a guard test checks that together they are `STATE_LABELS`' keys in order. `STATES` stays `tuple(STATE_LABELS)`.
- **What may still spell a list.** The planner's `Literal` (Python needs its values written) and `views._NOTICE` (each kind's text) stay, and given tests check each equals `REMINDER_KINDS`. The schema's CHECKs stay literal SQL. `reads.STATUSES` stays: it is not a list `domain` owns.
- **Names kept.** `_KIND_ORDER` keeps its name, built from `REMINDER_KINDS` in order. `reads._OPEN_STATES` goes, and `reads` uses `domain.OPEN_STATES`.
- **The helper is reached through the module.** Every caller writes `domain.valid_request_key(...)`, never `from docket.domain import valid_request_key`, as the time and id rules do, so a test can replace it in one place.
- **The client type check stays.** `isinstance(client, str)` stays before each `EMAIL_CLIENT` comparison, as the existing non-string test requires.
- **The copied-limits guard is narrowed (a given edit).** `test_consumers_do_not_keep_copied_parsers_domains_or_limits` now refuses a limit (5, 100, 200, 720) only where it is a bound: one side of a comparison, or a `ge`, `gt`, `le`, `lt`, `min_length` or `max_length` keyword. An HTTP status is not a copied limit, so `_REPLAY` is the plain `200` it means. The narrowed guard still refuses `1 <= len(key) <= 200` and `Field(ge=5)`.
- **`_text` stays for the zone only.** `accept_task` passes the four already-checked strings through without `_text` (for example with `typing.cast`).

## Requirements

1. **Domain lists.** `domain.py` assigns, at module level and spelled exactly so (the given test reads the source):

   | Name | Spelled | Value |
   |---|---|---|
   | `OPEN_STATES` | `("open", "in_progress")` | as written |
   | `ENDED_STATES` | `("done", "cancelled")` | as written |
   | `WORK_KINDS` | `("start",)` | as written |
   | `DEADLINE_KINDS` | `("before", "due_soon", "due", "late")` | as written |
   | `REMINDER_KINDS` | `WORK_KINDS + DEADLINE_KINDS` | `("start", "before", "due_soon", "due", "late")` |
   | `DUE_WINDOW_MINUTES` | `30` | `30` |
   | `EMAIL_CLIENT` | `"email"` | `"email"` |
   | `API_CLIENTS` | `(EMAIL_CLIENT,)` | `("email",)` |
   | `CORE_CLIENTS` | `(EMAIL_CLIENT, "agent")` | `("email", "agent")` |

   `domain` still imports nothing from `docket`.
2. **Key helper.** `domain.valid_request_key(key: object) -> bool` is true exactly when `key` is a `str` of 1 to `REQUEST_KEY_MAX` characters.
3. **Every key check asks it.** `core`'s keyed calls, `intake.accept_task` and `accept_link`, `web`'s header check and the store's post and digest keys each call `domain.valid_request_key` and keep their own refusal: `CoreError(INVALID_KEY)`, `400 {"error": "missing_key"}` (web before it parses the body), and `StoreError` with `invalid post key` or `invalid digest key`. No module but `domain` names `REQUEST_KEY_MAX`.
4. **Due window.** `deadlines.DUE_WINDOW` is `timedelta(minutes=domain.DUE_WINDOW_MINUTES)`, and the first entry of `reminder_plan.LATE_MINUTES` is `domain.DUE_WINDOW_MINUTES`; the other six entries stay. Both are read from `domain` when their module loads.
5. **Kinds and states derive.** `reminder_plan._KIND_ORDER` maps each kind of `domain.REMINDER_KINDS` to its position. `core._replace_reminders` voids `domain.DEADLINE_KINDS` on a deadline change and `domain.WORK_KINDS` on a work-time change. `reads` uses `domain.OPEN_STATES`. Outside `domain.py`, no literal tuple, list, set or dict key set under `src/docket/` holds only states or only reminder kinds, except the planner's `Literal` and `views._NOTICE`.
6. **Email client.** `clients.CLIENTS` is `domain.API_CLIENTS` (the same object). `core.add_link` and both intake calls compare the client with `domain.EMAIL_CLIENT` after `isinstance(client, str)`, and `add_link` stores its request key and link under `domain.EMAIL_CLIENT`. Outside `domain.py`, no comparison of `client` with `"email"`, `client="email"` argument, `request_key("email", ...)` call or `*CLIENTS` assignment holding `"email"` remains. `"email"` as a source stays.
7. **Intake.** `intake._REPLAY = 200`. `_text` is called only on the deadline's `time_zone`.
8. **Same answers.** No message, status, public signature, schema, reminder time or audit row changes. Every existing test passes, with the one given edit to `tests/integration/test_domain_schema.py`.
9. **Given markers**: `tests/integration/test_closed_lists.py` carries 8 strict `xfail` markers with reasons starting `Phase 5d given test: remove this marker`, one line each. Delete all 8 once requirements 1 to 8 are done, and nothing else in the file. A strict marker on a passing test fails the run, so `check.py` tells you when.
10. **Progress entry** for `## Phase 5d: One source per closed list (YYYY-MM-DD)` at the end of `docs/progress.md`.

## Given files

Already committed with this spec; never change them, except the markers of requirement 9.

| File | What it is |
|---|---|
| `tests/integration/test_closed_lists.py` | Tests that each list and bound has one source (list below) |
| `tests/integration/test_domain_schema.py` | Edited: the copied-limits guard refuses a limit only where it is a bound |
| `docs/verification/probe-05d.py` | The verifier's probe |

The given tests check that:

- `domain` spells each name of requirement 1 as the table gives it, with its value;
- the open and ended states together are `STATE_LABELS`' keys in order (a guard that passes today);
- `valid_request_key` at no key, a number, bytes, and 0, 1, 200 and 201 characters;
- core, intake, web and the store each refuse a key when `domain.valid_request_key` says no, and ask it about that key;
- in a fresh interpreter where `domain`'s due window, kind order and API clients are changed first, `deadlines`, `reminder_plan` and `clients` take the changed values;
- no module but `domain` spells a list of states or kinds, except the two allowed;
- the planner's `Literal` and `views._NOTICE` equal `REMINDER_KINDS` (a guard that passes today);
- no module but `domain` names the email client;
- `_REPLAY` is spelled `200`, and `_text` is called only on `value['time_zone']`.

Given test count: **27** new (`test_closed_lists.py`: 10 functions, 27 tests). Before you start, the file shows 25 xfailed and 2 passed: `test_the_states_split_into_open_and_ended` and `test_the_allowed_lists_match_domain` guard behaviour that must not change. The edit to `test_domain_schema.py` adds no test.

## Tests to write

None are required: the given tests, the existing key, intake, planner, deadline and client tests, and the probe cover requirements 1 to 8 and every line and branch of the draft. If a helper you add has a branch they miss, cover it in a new `tests/integration/test_closed_lists_more.py`, never by changing a given test.

## Scope

| Path | Change |
|---|---|
| `src/docket/domain.py` | edit: requirements 1 and 2 |
| `src/docket/core.py` | edit: requirements 3, 5 and 6 |
| `src/docket/intake.py` | edit: requirements 3, 6 and 7 |
| `src/docket/web.py` | edit: requirement 3 |
| `src/docket/store.py` | edit: requirement 3 |
| `src/docket/deadlines.py` | edit: requirement 4 |
| `src/docket/reminder_plan.py` | edit: requirements 4 and 5 |
| `src/docket/reads.py` | edit: requirement 5 |
| `src/docket/clients.py` | edit: requirement 6 |
| `tests/integration/test_closed_lists.py` | delete the 8 markers only |
| `tests/integration/test_closed_lists_more.py` | create, only if you need it |
| `docs/progress.md` | append your entry |

## Out of scope

- The planner's `Literal`, `views._NOTICE`, the schema's CHECKs and `reads.STATUSES`.
- `"email"` as a source, and any other use of the word that is not the API client.
- The client messages' words, any refusal's text, and any public signature, schema, migration or reminder rule.
- Visible reminder passes (Phase 5e).
- Any change to a given file beyond the markers, `AGENTS.md` or the design docs.

## Rules that bite

- **Code decides everything**: reminder times and deadline statuses are unchanged instant for instant. The probe compares plans, statuses and reminder rows with the spec commit's.
- **Through the module**: `domain.valid_request_key(...)`, as `clock.now()` and `ids.new_id()` are called. The given tests replace it on `domain`.
- **Error messages are constant text**: each refusal keeps its exact words.
- **Critical modules**: all nine modules in Scope are critical; every line and branch is covered, with no `pragma: no cover`.
- **Every existing test passes**, with only the given edit to `test_domain_schema.py`.
- If you stop before finishing, still write the progress entry with a `Stopped:` first follow-up (`docs/phase-conventions.md`, "When you stop").
- Commands start with `.venv/bin/python`; no bare `python3`, `pytest` or `ruff`.

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_closed_lists.py` (before you start) | `1908 passed` |
| `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1935 passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest tests/integration/test_closed_lists.py --no-cov -q` | `27 passed` |
| `.venv/bin/python -m coverage report --include=src/docket/domain.py,src/docket/core.py,src/docket/intake.py,src/docket/web.py,src/docket/store.py,src/docket/deadlines.py,src/docket/reminder_plan.py,src/docket/reads.py,src/docket/clients.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| `.venv/bin/python docs/verification/probe-05d.py` | last line `FAILURES 0` |
| `grep -c "^## Phase 5d: " docs/progress.md` | `1` |
| `.venv/bin/python scripts/check_reports.py --phase 5d` | `Reports OK.` |
| `git diff HEAD --stat -- docs/verification/probe-05d.py tests/integration/test_domain_schema.py tests/support.py tests/conftest.py tests/sections.toml docs/reviews AGENTS.md pyproject.toml scripts/check.py scripts/critical_modules.txt scripts/tooling_modules.txt src/docket/schema.py src/docket/views.py src/docket/cli.py` | no output |
| `git diff HEAD --numstat -- tests/integration/test_closed_lists.py` | `0	8	tests/integration/test_closed_lists.py` (the markers, nothing else) |
| `git status --short` | only the Scope paths |

### Searches

Each prints nothing.

```zsh
git grep --untracked -n -E 'import (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)|from (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)' -- src
git grep --untracked -n -E 'print\(|logging|logger|warnings\.warn' -- src ':!src/docket/cli.py'
git grep --untracked -n -E 'datetime\.now|datetime\.utcnow|date\.today|time\.time\(|from docket\.(clock|ids) import' -- src ':!src/docket/clock.py'
git grep --untracked -n -E 'pragma: no cover|noqa' -- src/docket/domain.py src/docket/core.py src/docket/intake.py src/docket/web.py src/docket/store.py src/docket/deadlines.py src/docket/reminder_plan.py src/docket/reads.py src/docket/clients.py
git grep --untracked -n -E 'REQUEST_KEY_MAX|from docket\.domain import .*valid_request_key' -- src ':!src/docket/domain.py'
git grep --untracked -n -E '_CREATED - 1|_OPEN_STATES|STATES\[|minutes=30|\(30, 60' -- src
git grep --untracked -n -E 'client != "email"|client="email"|request_key\("email"|CLIENTS = \("email"' -- src
```
