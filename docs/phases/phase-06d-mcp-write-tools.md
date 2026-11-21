# Phase 6d: MCP write tools

## Goal

Give the MCP server three write tools, `create_task`, `complete_task` and `cancel_task`, so Conductor can make the changes the owner approved in one of its steps. Each tool takes a `request_key` that Conductor's code fills with `<run id>:<step id>`, and a retried step with the same key and the same arguments changes nothing a second time. A new module `docket.writes` turns each call into one keyed `docket.core` call; `core` gains `change_state_once`, the keyed form of `change_state`. This phase adds no edit tool (6e), changes no read tool's answers, and changes nothing in the HTTP intake, the web pages or the CLI.

Sections: `core`. The `tooling` section runs in the full check.

Follow `docs/phase-conventions.md`. N is 1707, the tests the previous phase left passing.

Start: `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_core_state_keys.py --ignore=tests/integration/test_writes.py --ignore=tests/integration/test_mcp_writes.py` must show `1707 passed`. The ignored files are this phase's new given tests; the fourth given file, `tests/integration/test_mcp_server.py`, is an edited earlier file that passes today and after.

## Facts

- `core.create_task_once(store, *, client, key, request, title, source, ...)` already keeps a key for a create: it checks the client against `domain.CORE_CLIENTS` (`email`, `agent`), the key with `_check_key` (a string of 1 to 200 characters, else `invalid_key`), reads the clock, then in one transaction returns the kept task with `changed` False when `store.request_key(client, key)` holds the same request (`_same_request`), and raises `key_reused` when it holds another.
- The `request_keys` table (client, key, request as canonical JSON, task, link, created_at; primary key client and key) takes a state-change key with no migration: `link` is NULL for every `agent` row, and the task column names the changed task.
- `core.change_state(store, task_id, action, *, actor)` checks the action and actor, reads the clock, then in one transaction looks the task up (`unknown_task`), gets the next state from `_next_state` (`task_ended` for `done` on a cancelled task or `cancel` on a done one; no change for `done` on a done task or `cancel` on a cancelled one), updates the row, appends the audit row, and voids or plans reminders.
- `core._ACTOR_FOR_SOURCE` (`domain.SOURCE_ACTORS`) maps client `agent` to actor `agent` and `email` to `email`.
- `parsing.parse_date` and `parsing.parse_time` take any value and raise `ParseError` unless it is a `YYYY-MM-DD` or `HH:MM` string naming a real day or minute; `deadlines.make_deadline(day, time or None, zone)` uses 17:00 for no time, picks the earlier instant of a repeated hour (fold 0), and raises `DeadlineError` for a zone that is not an exact IANA name, a non-string zone included.
- In the MCP SDK (mcp 2.3.0), `ToolError(code)` reaches the caller as `Error executing tool <name>: <code>`; any other exception reaches it as `Error executing tool <name>` with no text. A pydantic model with `extra="forbid"` lists `additionalProperties: false` in the input schema. When an argument has the wrong JSON type, the SDK refuses it with pydantic's own validation text, which can quote the value: this is the known limit 6a accepted, and the given tests do not cover it.
- `reads.py` and `mcp_server/server.py` were covered at 100% after 6a but are not in `scripts/critical_modules.txt`.
- A throwaway draft of this phase changed about 140 lines in `core.py`, `server.py` and `critical_modules.txt`, plus a 70-line `writes.py`; the given tests alone covered all four files completely.

## Owner's decisions

- **State-change keys (2026-11-21):** `complete_task` and `cancel_task` keep their `request_key` in `request_keys`, as `create_task` does, so a retried step after the owner reopens a task changes nothing (not a stateless "already in that state" check).
- **Already in the end state (2026-11-21):** `complete_task` on a done task and `cancel_task` on a cancelled one answer the task with `changed` false and keep the key; they are not refused. `done` on a cancelled task or `cancel` on a done one is refused with `task_ended`. This drops the `already_done` refusal Conductor's handoff lists, which is work in Conductor's project.
- **Answer (2026-11-21):** every write tool answers the task, in `get_task`'s task fields, plus `changed` (not an id alone).

## Architect's decisions

- The deadline argument is `null` or an object with exactly `date`, `time` and `time_zone`; `time` is required and may be `null`. It is parsed before anything else, so a bad deadline is refused before the key or the title is checked.
- The kept request is `{"tool": "create_task", "title": ..., "deadline": ...}` with the deadline object as given (or `null`), and `{"tool": "complete_task" or "cancel_task", "id": ...}`. The tool name is part of it, so a create key reused on a completion, or a complete key on a cancel, is `key_reused`.
- The key is looked up before the task, so a kept key with another request is `key_reused` even for an unknown task. A refused change (`unknown_task`, `task_ended`) keeps no key.
- An id that is not a string is `unknown_task`, before the key check.
- All three tools have hints read-only false, destructive false, idempotent true, open-world false.
- The intake's `POST /tasks` and the CLI are not changed; `change_state` keeps its signature and behaviour.

## Requirements

1. **`docket.writes`** (new) defines `INVALID_DEADLINE = "invalid_deadline"`, `UNKNOWN_TASK = "unknown_task"` and `class WriteRefused(Exception)` whose `code` attribute and `str()` are the code. `parse_deadline(value: object) -> Deadline | None` returns `None` for `None`, and otherwise needs a dict with exactly the keys `date`, `time`, `time_zone`, read through `parsing.parse_date`, `parsing.parse_time` (when `time` is not `None`) and `deadlines.make_deadline`. Anything else raises `WriteRefused(INVALID_DEADLINE)`, never another exception.
2. **`writes.create_task(store, *, title: object, deadline: object, request_key: object) -> Outcome`** parses the deadline first, then calls `core.create_task_once` with client `agent`, source `agent`, the key, the parsed deadline and the request of the architect's decisions. A `CoreError` becomes `WriteRefused` with the same code.
3. **`writes.complete_task(store, task_id: object, *, request_key: object) -> Outcome`** and **`writes.cancel_task(...)`**, same signature, refuse a non-string id with `WriteRefused(UNKNOWN_TASK)`, then call `core.change_state_once` with action `done` or `cancel`, client `agent` and the request of the architect's decisions. A `CoreError` becomes `WriteRefused` with the same code.
4. **`core.change_state_once(store, task_id: str, action: str, *, client: object, key: object, request: dict[str, object]) -> Outcome`** checks, in this order and before reading the clock, the action (`invalid_action`), the client (`invalid_client`) and the key (`invalid_key`, `_check_key`). It then reads `clock.now()` once and, in one transaction: a kept key with no link and the same request returns the task as it is now with `changed` False and writes nothing; a kept key with another request raises `key_reused`; otherwise it makes the change exactly as `change_state` does, with actor `_ACTOR_FOR_SOURCE[client]`, and keeps the key, the request and the task id with `created_at` the clock's moment, whether the change was made or was no change. A refusal keeps no key and writes nothing.
5. **`change_state` is unchanged** in signature and behaviour; it and `change_state_once` share one private body, so a press, a command and a tool make the same change.
6. **The three tools** are added to `build_server` beside the two read tools, with the descriptions `CREATE_TASK`, `COMPLETE_TASK` and `CANCEL_TASK` and the new `INSTRUCTIONS`, word for word as the given tests hold them. Arguments: `create_task(title: str, request_key: str, deadline: DeadlineInput | None = None)` and `complete_task` and `cancel_task(id: str, request_key: str)`. `DeadlineInput` is a pydantic model with `extra="forbid"` and the fields `date: str`, `time: str | None` (required) and `time_zone: str`; the tool passes its plain dict, or `None`, to `writes`. Each tool opens one store per call, as the read tools do, and closes it.
7. **Answers.** Each write tool's output model is `TaskChangeResult`, `TaskResult` plus `changed: bool`, with structured output. A `WriteRefused` becomes `ToolError(code)`; any other exception passes on, so the caller sees only `Error executing tool <name>`.
8. **Critical modules.** `scripts/critical_modules.txt` adds the lines `reads.py`, `writes.py` and `mcp_server/server.py` (paths under `src/docket/`, as the file's other lines are).
9. **Given markers**: the given test files carry strict `xfail` markers with reasons starting `Phase 6d given test: remove this marker`: 8 in `tests/integration/test_core_state_keys.py`, 7 in `tests/integration/test_writes.py` and 7 in `tests/integration/test_mcp_writes.py`, one line each. Delete all 22 once requirements 1 to 8 are done, and nothing else in those files; the `MARK` constants stay. A strict marker on a passing test fails the run, so `check.py` tells you when.
10. **Progress entry** for `## Phase 6d: MCP write tools (YYYY-MM-DD)` at the end of `docs/progress.md`.

## Given files

Already committed with this spec; never change them, except the markers of requirement 9.

| File | What it is |
|---|---|
| `tests/integration/test_core_state_keys.py` | `core.change_state_once`: a keyed done changes the task once and keeps its key and audit row; a retry after the owner reopens changes nothing; a new key on a finished task is no change and is kept; a key used for another request is refused with nothing written; bad client and key refused before the clock; the action first; an unknown or ended task keeps the key free; keys are per client |
| `tests/integration/test_writes.py` | `docket.writes`: deadlines read in their own zone across both 2026–27 daylight-saving changes; 13 bad deadlines refused; a create made once per key; a key reused with other arguments refused; refusal order (deadline, key, title) before the clock; complete and cancel as keyed changes; the state-change refusals |
| `tests/integration/test_mcp_writes.py` | Through an in-memory MCP client: the new `INSTRUCTIONS`, the five tools, the writes' descriptions and hints; the input and output schemas; the create, complete and cancel answers; nine refusals as constant codes; an unexpected error with no text |
| `tests/integration/test_mcp_server.py` | Edited, unmarked: the instructions are now pinned in `test_mcp_writes.py`, and the read tools' listing and schema tests look at the two read tools only |
| `docs/verification/probe-06d.py` | The verifier's probe |

Given test count: **67** new (`test_core_state_keys.py`: 8 functions, 14 tests; `test_writes.py`: 7 functions, 36 tests; `test_mcp_writes.py`: 7 functions, 17 tests), plus the 5 tests of `test_mcp_server.py`, which N already counts. Before you start, the three new files show 67 xfailed and `test_mcp_server.py` 5 passed.

## Tests to write

None are required: the given tests cover requirements 1 to 7 and every new line and branch of the draft. If you add a private helper with a branch the given tests miss, cover it in a new `tests/integration/test_writes_more.py`, never by changing a given test.

## Scope

| Path | Change |
|---|---|
| `src/docket/writes.py` | create: requirements 1 to 3 |
| `src/docket/core.py` | edit: requirements 4 and 5 |
| `src/docket/mcp_server/server.py` | edit: requirements 6 and 7 |
| `scripts/critical_modules.txt` | edit: requirement 8 |
| `tests/integration/test_core_state_keys.py` | delete the 8 markers only |
| `tests/integration/test_writes.py` | delete the 7 markers only |
| `tests/integration/test_mcp_writes.py` | delete the 7 markers only |
| `tests/integration/test_writes_more.py` | create, only if you need it |
| `docs/progress.md` | append your entry |

## Out of scope

- An `edit_task` tool, parsing work times, or any other write tool (6e).
- A tool that approves or presses a proposal, or any write that does not come from an approved Conductor step.
- Changing a read tool's answers, `reads.py`, the store, a migration, `intake.py`, `web.py`, `cli.py`, `views.py` or `domain`.
- Catching pydantic's validation text for a wrong-typed argument (the known limit in Facts).
- Checking the title in `writes` (core's `check_title` does), or any retry, timeout or queue in the server.
- Any change to a given file beyond the markers, `AGENTS.md` or the design docs.

## Rules that bite

- **Nothing without approval**: a task is created or changed only by the call the tool receives; no code path creates or changes a task on its own.
- **Retry-safe**: the key is looked up and kept in the same transaction as the change; a replay writes no row.
- **Every change goes through `core`**: `writes` and the server call only `core`; neither calls a store write.
- **Error messages are constant text**: a refusal is its code alone; no title, key, id or exception text reaches the caller.
- **Critical modules**: every new line and branch of `core.py`, `writes.py` and `server.py` is covered, with no `pragma: no cover`.
- **Time through the module**: `clock.now()`, never `datetime.now()`, and never `from docket.clock import now`.
- If you stop before finishing, still write the progress entry with a `Stopped:` first follow-up (`docs/phase-conventions.md`, "When you stop").
- Commands start with `.venv/bin/python`; no bare `python3`, `pytest` or `ruff`.

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_core_state_keys.py --ignore=tests/integration/test_writes.py --ignore=tests/integration/test_mcp_writes.py` (before you start) | `1707 passed` |
| `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1774 passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest tests/integration/test_core_state_keys.py tests/integration/test_writes.py tests/integration/test_mcp_writes.py --no-cov -q` | `67 passed` |
| `.venv/bin/python -m coverage report --include=src/docket/writes.py,src/docket/core.py,src/docket/mcp_server/server.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| `.venv/bin/python docs/verification/probe-06d.py` | last line `FAILURES 0` |
| `grep -c "^## Phase 6d: " docs/progress.md` | `1` |
| `.venv/bin/python scripts/check_reports.py --phase 6d` | `Reports OK.` |
| `git diff HEAD --stat -- docs/verification/probe-06d.py tests/support.py tests/conftest.py tests/mcp_cases.py tests/sections.toml docs/reviews AGENTS.md pyproject.toml scripts/check.py` | no output |
| `git diff HEAD --numstat -- tests/integration/test_core_state_keys.py tests/integration/test_writes.py tests/integration/test_mcp_writes.py tests/integration/test_mcp_server.py` | three lines: 0 added, 8 deleted, `tests/integration/test_core_state_keys.py`; 0 added, 7 deleted, `tests/integration/test_mcp_writes.py`; 0 added, 7 deleted, `tests/integration/test_writes.py` (the markers, nothing else; `test_mcp_server.py` stays unchanged) |
| `git status --short` | only the Scope paths |

### Searches

Each prints nothing.

```zsh
git grep --untracked -n -E 'import (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)|from (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)' -- src
git grep --untracked -n -E 'print\(|logging|logger|warnings\.warn' -- src ':!src/docket/cli.py'
git grep --untracked -n -E 'ollama|anthropic|openai|langchain' -- src
git grep --untracked -n -E 'datetime\.now|datetime\.utcnow|date\.today|time\.time\(|from docket\.(clock|ids) import' -- src ':!src/docket/clock.py'
git grep --untracked -n -E '\.(insert_task|update_task|append_audit|insert_link|insert_request_key)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'
git grep --untracked -n -E 'pragma: no cover|noqa' -- src/docket/writes.py src/docket/core.py src/docket/mcp_server/server.py
```
