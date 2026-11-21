# Phase 6e: MCP edit tools

## Goal

Give the MCP server its last two write tools for now, `change_deadline` and `plan_work_time`, so Conductor can move a task's deadline or plan the time to work on it once the owner approves the step. Each takes a `request_key`, kept as in 6d, so a retried step changes nothing a second time. `docket.writes` gains the two functions and `parse_work_time`; `core` gains `edit_task_once`, the keyed form of `edit_task`. This phase queues no calendar update (Stage 7), adds no `check_availability` (Stage 8) or `snooze_task` (Stage 4), and changes nothing in the HTTP intake, the web pages or the CLI.

Sections: `core`. The `tooling` section runs in the full check.

Follow `docs/phase-conventions.md`. N is 1775, the tests the previous phase left passing.

Start: `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_core_edit_keys.py --ignore=tests/integration/test_writes_edits.py --ignore=tests/integration/test_mcp_edits.py` must show `1775 passed`. The ignored files are this phase's new given tests; the edited earlier files, `tests/integration/test_mcp_writes.py` and `docs/verification/probe-06d.py`, pass today and after.

## Facts

- `core.edit_task(store, task_id, *, actor, title=UNCHANGED, deadline=UNCHANGED, work=UNCHANGED)` checks the actor, the title and the value types (`_check_values`: `invalid_deadline`, `invalid_work`), reads the clock, then in one transaction refuses an unknown task (`unknown_task`), an ended one (`task_ended`) and a work time that ends after the deadline (`work_after_deadline`, `work.end > deadline.at`, so ending exactly at the deadline is allowed). A value equal to the current one is no change; each changed field writes one audit row (`deadline`, `work_time`) and replans reminders (`_replace_reminders`).
- `core.change_state_once` (6d) is the pattern: client (`invalid_client`), key (`_check_key`), clock, then in one transaction the kept-key lookup (`_same_request`: same request returns the task as it is now, `changed` False; another request is `key_reused`), the shared private body, and `store.insert_request_key` with no link, whether the change was made or was no change.
- `deadlines.make_work_time(day, start, minutes, zone, deadline)` refuses with `DeadlineError` a length outside 5 to 720 minutes (`domain.WORK_MINUTES_MIN`, `WORK_MINUTES_MAX`), a zone that is not an exact IANA name (non-strings included), and a work time that ends after the next local midnight. It reads a skipped or repeated local time with fold 0, so 2027-03-14 02:30 in New York is 07:30Z and 2026-11-01 01:30 is 05:30Z. `docket tasks plan` passes `None` as the deadline and lets `core` refuse a late work time; the writes do the same.
- `writes.parse_deadline` (6d) already reads the deadline argument; `WorkTime(start, minutes, zone)` checks its own length, so `True` (1 minute) is refused without a separate boolean check, but `60.0` is not.
- The MCP SDK refuses an argument of the wrong JSON type with pydantic's own text, the known limit 6a accepted; a float for an `int` argument may be coerced by pydantic before `writes` sees it. The given tests call `writes` directly for those values.
- A throwaway draft changed about 230 lines in `core.py`, `writes.py` and `server.py`; the given tests alone covered all three at 100%.

## Owner's decisions

- **Removing a deadline (2026-11-21):** `change_deadline` takes `deadline` null to remove the task's deadline, as `docket tasks edit --no-due` does (not refused).
- **Start shape (2026-11-21):** `plan_work_time`'s `start` is `{date, time, time_zone}`, the deadline's object with `time` required as `HH:MM` (not a local ISO string and a separate zone).
- **Minutes (2026-11-21):** `minutes` is required; there is no default from `DOCKET_WORK_MINUTES`, so the kept request always holds the length.
- **Clearing a work time (2026-11-21):** not through MCP in 6e; clearing stays `docket tasks plan --clear`.

## Architect's decisions

- `change_deadline`'s `deadline` is required in the schema and may be null, so leaving it out is refused by the SDK and never removes a deadline.
- Refusal order in `writes`: a non-string id (`unknown_task`), then the value (`invalid_deadline` or `invalid_work`), then core's client and key checks, then the kept key, then the task. A kept key with a bad value is therefore `invalid_deadline` or `invalid_work`, not `key_reused`.
- The kept requests are `{"tool": "change_deadline", "id": ..., "deadline": ...}` and `{"tool": "plan_work_time", "id": ..., "start": ..., "minutes": ...}`, with the arguments as given.
- `minutes` must be an `int` exactly (`type(minutes) is int`); anything else is `invalid_work`.
- `edit_task_once` takes no title: no MCP tool renames a task.
- The new `INSTRUCTIONS` names the read tools and says every other tool writes; the 6d listing test and probe-06d now allow tools beyond their own.

## Requirements

1. **`core.edit_task_once(store, task_id: str, *, client: object, key: object, request: dict[str, object], deadline: object = UNCHANGED, work: object = UNCHANGED) -> Outcome`** checks, in this order and before reading the clock, the client (`invalid_client`), the key (`invalid_key`) and the values (`_check_values`). It then reads `clock.now()` once and, in one transaction: a kept key with no link and the same request returns the task as it is now with `changed` False and writes nothing; a kept key with another request raises `key_reused`; otherwise it makes the edit exactly as `edit_task` does, with actor `_ACTOR_FOR_SOURCE[client]`, and keeps the key, the request and the task id with `created_at` the clock's moment, whether the edit changed the task or not. A refusal keeps no key and writes nothing.
2. **`edit_task` is unchanged** in signature and behaviour; it and `edit_task_once` share one private body.
3. **`writes.INVALID_WORK = "invalid_work"`** and **`writes.parse_work_time(start: object, minutes: object) -> WorkTime`**: `start` must be a dict with exactly the keys `date`, `time`, `time_zone`, read through `parsing.parse_date`, `parsing.parse_time` and `deadlines.make_work_time(..., None)`; `minutes` must be an `int` exactly. Anything else raises `WriteRefused(INVALID_WORK)`, never another exception.
4. **`writes.change_deadline(store, task_id: object, *, deadline: object, request_key: object) -> Outcome`** refuses a non-string id with `WriteRefused(UNKNOWN_TASK)`, parses the deadline with `parse_deadline` (null removes it), then calls `core.edit_task_once` with client `agent`, the key, the request of the architect's decisions and `deadline=` the parsed value. A `CoreError` becomes `WriteRefused` with the same code.
5. **`writes.plan_work_time(store, task_id: object, *, start: object, minutes: object, request_key: object) -> Outcome`** does the same with `parse_work_time` and `work=`.
6. **The two tools** are added to `build_server` beside the other five, with the hints of 6d's writes (read-only false, destructive false, idempotent true, open-world false), the descriptions `CHANGE_DEADLINE` and `PLAN_WORK_TIME` and the new `INSTRUCTIONS`, word for word as `tests/integration/test_mcp_edits.py` holds them. Arguments: `change_deadline(id: str, request_key: str, deadline: DeadlineInput | None)` with no default, and `plan_work_time(id: str, start: WorkStartInput, minutes: int, request_key: str)`. `WorkStartInput` is a pydantic model with `extra="forbid"` and the fields `date: str`, `time: str` and `time_zone: str`. Each tool passes plain dicts (or `None`) to `writes`, opens one store per call and closes it.
7. **Answers** are `TaskChangeResult`, as in 6d. A `WriteRefused` becomes `ToolError(code)`; any other exception passes on, so the caller sees only `Error executing tool <name>`.
8. **Given markers**: the three new given test files carry strict `xfail` markers with reasons starting `Phase 6e given test: remove this marker`, one line each: 7 in `tests/integration/test_core_edit_keys.py`, 5 in `tests/integration/test_writes_edits.py` and 6 in `tests/integration/test_mcp_edits.py`. Delete all 18 once requirements 1 to 7 are done, and nothing else in those files. A strict marker on a passing test fails the run, so `check.py` tells you when.
9. **Progress entry** for `## Phase 6e: MCP edit tools (YYYY-MM-DD)` at the end of `docs/progress.md`.

## Given files

Already committed with this spec; never change them, except the markers of requirement 8.

| File | What it is |
|---|---|
| `tests/integration/test_core_edit_keys.py` | `core.edit_task_once`: a keyed deadline change made once with its key and audit row; a retry after the owner moves the deadline back changes nothing; a keyed work time planned once, and a new key on the same work time kept as no change; a key used for another request, another tool, a create or a completion refused with nothing written; bad client, key and values refused before the clock, in order; refused edits keep the key free; moving the deadline before the work time refused, removing it allowed |
| `tests/integration/test_writes_edits.py` | `docket.writes`: work times read in their own zone across both daylight-saving changes, at the 5- and 720-minute bounds and ending at midnight; 21 bad work times refused; `change_deadline` moves and removes once per key; `plan_work_time` plans and moves once per key; the refusal order and codes |
| `tests/integration/test_mcp_edits.py` | Through an in-memory MCP client: the new `INSTRUCTIONS`, the seven tools, the two descriptions and hints; the input and output schemas; the change and plan answers and their retries; ten refusals as constant codes; an unexpected error with no text |
| `tests/integration/test_mcp_writes.py` | Edited: the listing test now checks 6d's tools among the listed ones, and no longer pins the instructions |
| `docs/verification/probe-06d.py` | Edited the same way: 6d's tools among the listed ones |
| `docs/verification/probe-06e.py` | The verifier's probe |

Given test count: **74** new (`test_core_edit_keys.py`: 7 functions, 17 tests; `test_writes_edits.py`: 5 functions, 41 tests; `test_mcp_edits.py`: 6 functions, 16 tests). Before you start, the three new files show 74 xfailed.

## Tests to write

None are required: the given tests cover requirements 1 to 7 and every new line and branch of the draft. If you add a private helper with a branch the given tests miss, cover it in a new `tests/integration/test_writes_edits_more.py`, never by changing a given test.

## Scope

| Path | Change |
|---|---|
| `src/docket/core.py` | edit: requirements 1 and 2 |
| `src/docket/writes.py` | edit: requirements 3 to 5 |
| `src/docket/mcp_server/server.py` | edit: requirements 6 and 7 |
| `tests/integration/test_core_edit_keys.py` | delete the 7 markers only |
| `tests/integration/test_writes_edits.py` | delete the 5 markers only |
| `tests/integration/test_mcp_edits.py` | delete the 6 markers only |
| `tests/integration/test_writes_edits_more.py` | create, only if you need it |
| `docs/progress.md` | append your entry |

## Out of scope

- Clearing a work time through MCP, renaming a task, `snooze_task`, `check_availability` or any other tool.
- Queuing a calendar update for a moved deadline or work time (Stage 7).
- A default length from `DOCKET_WORK_MINUTES` for `plan_work_time`.
- Changing `edit_task`'s or `change_state_once`'s behaviour, a read tool, the store, a migration, `intake.py`, `web.py`, `cli.py`, `views.py` or `domain`.
- Catching pydantic's validation text for a wrong-typed argument (the known limit in Facts).
- Any change to a given file beyond the markers, `AGENTS.md` or the design docs.

## Rules that bite

- **Nothing without approval**: a task changes only by the call the tool receives; no code path changes a deadline or work time on its own.
- **Retry-safe**: the key is looked up and kept in the same transaction as the edit; a replay writes no row.
- **Every change goes through `core`**: `writes` and the server call only `core`; neither calls a store write.
- **Error messages are constant text**: a refusal is its code alone; no title, key, id, date or exception text reaches the caller.
- **Critical modules**: `core.py`, `writes.py` and `server.py` are critical; every new line and branch is covered, with no `pragma: no cover`.
- **Time through the module**: `clock.now()`, never `datetime.now()`, and never `from docket.clock import now`.
- If you stop before finishing, still write the progress entry with a `Stopped:` first follow-up (`docs/phase-conventions.md`, "When you stop").
- Commands start with `.venv/bin/python`; no bare `python3`, `pytest` or `ruff`.

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_core_edit_keys.py --ignore=tests/integration/test_writes_edits.py --ignore=tests/integration/test_mcp_edits.py` (before you start) | `1775 passed` |
| `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1849 passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest tests/integration/test_core_edit_keys.py tests/integration/test_writes_edits.py tests/integration/test_mcp_edits.py --no-cov -q` | `74 passed` |
| `.venv/bin/python -m coverage report --include=src/docket/core.py,src/docket/writes.py,src/docket/mcp_server/server.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| `.venv/bin/python docs/verification/probe-06e.py` | last line `FAILURES 0` |
| `.venv/bin/python docs/verification/probe-06d.py` | last line `FAILURES 0` |
| `grep -c "^## Phase 6e: " docs/progress.md` | `1` |
| `.venv/bin/python scripts/check_reports.py --phase 6e` | `Reports OK.` |
| `git diff HEAD --stat -- tests/integration/test_mcp_writes.py docs/verification/probe-06d.py docs/verification/probe-06e.py tests/support.py tests/conftest.py tests/mcp_cases.py tests/sections.toml docs/reviews AGENTS.md pyproject.toml scripts` | no output |
| `git diff HEAD --numstat -- tests/integration/test_core_edit_keys.py tests/integration/test_writes_edits.py tests/integration/test_mcp_edits.py` | three lines: 0 added, 7 deleted, `tests/integration/test_core_edit_keys.py`; 0 added, 6 deleted, `tests/integration/test_mcp_edits.py`; 0 added, 5 deleted, `tests/integration/test_writes_edits.py` (the markers, nothing else) |
| `git status --short` | only the Scope paths |

### Searches

Each prints nothing.

```zsh
git grep --untracked -n -E 'import (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)|from (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)' -- src
git grep --untracked -n -E 'print\(|logging|logger|warnings\.warn' -- src ':!src/docket/cli.py'
git grep --untracked -n -E 'ollama|anthropic|openai|langchain' -- src
git grep --untracked -n -E 'datetime\.now|datetime\.utcnow|date\.today|time\.time\(|from docket\.(clock|ids) import' -- src ':!src/docket/clock.py'
git grep --untracked -n -E '\.(insert_task|update_task|append_audit|insert_link|insert_request_key)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'
git grep --untracked -n -E 'pragma: no cover|noqa' -- src/docket/core.py src/docket/writes.py src/docket/mcp_server/server.py
```
