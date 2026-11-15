# Phase 2b: Intake rules

## Goal

Turn the email service's requests into the tasks app's answers, still with no HTTP: `docket.intake` checks the retry key, the exact JSON body of an approved task or a follow-up link, and its deadline, calls Phase 2a's keyed core, and answers with the status code and JSON body the email service expects (201, 200, 400, 404, 409 or 422). Phase 2c puts these answers behind HTTP routes and client tokens, and 2d serves them; a malformed JSON document, a wrong path and sign-in are theirs.

Sections: `core`. The `tooling` section runs in the full check.

Follow `docs/phase-conventions.md`. N is 579, the tests the previous phase left passing.

Start: `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_intake.py` must show `579 passed`. The ignored files import names you create.

## Facts

Each checked on this machine on 2026-11-14.

- **The email service's fake tasks app** (`emails/tests/fakes.py`, `FakeTasksApp`) answers a task: 400 for an `Idempotency-Key` outside 1 to 200 characters, 422 for a body that isn't exactly `source`, `title`, `deadline`, `provider`, `message_id`, `link` (with `deadline` null or exactly `date`, `time`, `time_zone`), 409 for a key reused with another body, 200 with the same id for a repeat, 201 for a new one. A link: 400, then 404 for an unknown task, then 422 for a body that isn't exactly `source`, `provider`, `message_id`, `link`, then 409, 200 or 201. The email service reads only the status and, on 201 or 200, `id`.
- **The email service's payload** (`mailroom.tasks_app.task_payload`) sends `time` as `strftime("%H:%M")` or null and `time_zone` from its setting, which it checks only by loading `ZoneInfo`, so on macOS a wrong-case name like `america/new_york` passes there.
- **`core.create_task_once` raises `TypeError`, not `CoreError`, for a list as `provider`** (`provider in {...}` needs a hashable value), so intake checks every text field is a string before calling the core.
- **Phase 2a's core** looks up a key before its task and compares requests as canonical JSON; Phase 1a's `make_deadline` refuses a zone not in `available_timezones()` with `DeadlineError(ZONE_MESSAGE)`.

## Owner's decisions

Decided 2026-11-14:

- **A zone that is right but wrongly spelled is refused** (422 `invalid_deadline`), never rewritten; the email service gains a work item to check its own setting against `available_timezones()`.
- **A link follows the fake's order**: the key (400), the task (404), the body (422), then the key's history (409, 200 or 201).
- Earlier: stage 2's split; per-client keys; the email service's approval is final.

## Architect's decisions

- **Intake serves the email client only**: Conductor reaches the core through MCP (stage 6), so `accept_task` and `accept_link` always pass `client="email"`.
- **Every answer body is `{"id": <id>}` or `{"error": <code>}`**, never an echo of the request; the codes are the core's plus three of intake's own.
- **Shape before meaning**: the body's fields and their JSON types first (`invalid_body`), then the deadline (`invalid_deadline`), then the core's own checks (title, source, reference) with the core's codes.
- **The stored request is the body as sent**, so a repeat compares the whole body, deadline included.
- **A link's task is looked up by intake before its body is checked**, so an unknown task is 404 whatever the body; the core still decides a repeat or a reuse.

## Requirements

1. **`src/docket/intake.py`, names**: `MISSING_KEY = "missing_key"`, `INVALID_BODY = "invalid_body"`, `INVALID_DEADLINE = "invalid_deadline"`. `Answer`, a frozen dataclass: `status: int`, `body: dict`.
2. **`accept_task(store, *, key: str | None, body: object) -> Answer`** answers, in this order:
   - `key` not a string of 1 to 200 characters: `Answer(400, {"error": MISSING_KEY})`;
   - `body` not a JSON object with exactly the keys `source`, `title`, `deadline`, `provider`, `message_id`, `link`, or any of those but `deadline` not a string: 422 `invalid_body`;
   - `deadline` not null and not exactly `{"date", "time", "time_zone"}`, or `date` not matching `[0-9]{4}-[0-9]{2}-[0-9]{2}` and a real date, or `time` not null and not matching `[0-9]{2}:[0-9]{2}` and a real time, or `make_deadline(day, time, time_zone)` refusing it (an inexact zone included): 422 `invalid_deadline`;
   - then `core.create_task_once(store, client="email", key=key, request=body, title=…, source=…, deadline=…, provider=…, message_id=…, link=…)`: `key_reused` is 409, any other `CoreError` 422, each with `{"error": <code>}`; a new task is `Answer(201, {"id": <task id>})`, a repeat `Answer(200, {"id": <task id>})`.
3. **`accept_link(store, task_id: str, *, key: str | None, body: object) -> Answer`** answers, in this order:
   - the key as in requirement 2 (400);
   - `store.task(task_id)` finding nothing: `Answer(404, {"error": "unknown_task"})`;
   - `body` not exactly `source`, `provider`, `message_id`, `link`, all strings: 422 `invalid_body`; `source` not `"email"`: 422 `invalid_source`;
   - then `core.add_link(store, task_id, client="email", key=key, request=body, provider=…, message_id=…, link=…)`: `key_reused` 409, `unknown_task` 404, any other `CoreError` 422; a new link `Answer(201, {"id": <link id>})`, a repeat `Answer(200, {"id": <link id>})`.
4. **No exception escapes** `accept_task` or `accept_link` for any JSON value as `body` (objects, arrays, strings, numbers, null, nested in any field); a store failure is not a JSON value and still raises.
5. **Answers carry no request text**: an answer body is exactly `{"id": …}` or `{"error": <code>}`.
6. **Intake decides only shapes**: it writes through `core.create_task_once` and `core.add_link` only, and reads no clock, settings or environment of its own.

7. **Progress entry** for `## Phase 2b: Intake rules (YYYY-MM-DD)` at the end of `docs/progress.md`.

## Given files

Already committed with this spec; never change them.

| File | What it is |
|---|---|
| `tests/integration/test_intake.py` | 55 tests from 13 functions (requirements 1 to 6) |
| `scripts/critical_modules.txt` | Adds `intake.py` |
| `docs/verification/probe-02b.py` | The verifier's probe |

Given test count: **55**.

## Tests to write

The given tests cover every requirement's main cases. To reach full coverage, add behaviour tests in new `*_more.py` files beside them, never by changing a given test.

## Scope

| Path | Change |
|---|---|
| `src/docket/intake.py` | create |
| `docs/progress.md` | append your entry |

## Out of scope

- HTTP: routes, FastAPI, parsing a JSON document, the host check, client tokens, `docket serve` (2c, 2d).
- Accepting other clients, proposals (`POST /proposals`), or Conductor's requests.
- Rewriting anything sent: trimming a title, fixing a zone's case, filling a missing field.
- Showing links in `docket tasks show`.
- Any change to `core.py`, `store.py`, `deadlines.py`, a given file, `AGENTS.md` or the design docs.
- Any change to a given file, `AGENTS.md` or the design docs.

## Rules that bite

- **Nothing without approval**: intake creates only through `core.create_task_once` as the email client, whose own approval came first.
- **Everything is retry-safe**: the key's history is the core's, in one transaction; intake never answers a repeat from anything but the core's outcome.
- **No email text out**: an answer never echoes a title, a key, a link or any part of the body.
- **Time through the module**: `clock.now()`, never `datetime.now()`, and never `from docket.clock import now`.
- If you stop before finishing, still write the progress entry with a `Stopped:` first follow-up (`docs/phase-conventions.md`, "When you stop").
- Commands start with `.venv/bin/python`; no bare `python3`, `pytest` or `ruff`.

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_intake.py` (before you start) | `579 passed` |
| `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 634 passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest tests/integration/test_intake.py --no-cov -q` | `55 passed` |
| `.venv/bin/python -m coverage report --include=src/docket/intake.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| `.venv/bin/python docs/verification/probe-02b.py` | last line `FAILURES 0` |
| `grep -c "^## Phase 2b: " docs/progress.md` | `1` |
| `.venv/bin/python scripts/check_reports.py --phase 2b` | `Reports OK.` |
| `git diff HEAD --stat -- tests/integration/test_intake.py scripts/critical_modules.txt docs/verification/probe-02b.py` | no output |
| `git status --short` | only the Scope paths |

### Searches

Each prints nothing.

```zsh
git grep --untracked -n -E 'import (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)|from (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)' -- src
git grep --untracked -n -E 'print\(|logging|logger|warnings\.warn' -- src ':!src/docket/cli.py'
git grep --untracked -n -E 'datetime\.now|datetime\.utcnow|date\.today|time\.time\(|from docket\.(clock|ids) import' -- src ':!src/docket/clock.py'
git grep --untracked -n -E '\.(insert_task|update_task|append_audit|insert_link|insert_request_key)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'
git grep --untracked -n -E 'ollama|anthropic|openai|langchain' -- src
git grep --untracked -n -E 'pragma: no cover|noqa' -- src/docket/intake.py
git grep --untracked -n -E 'fastapi|starlette|uvicorn|os\.environ|getenv\(|get_settings\(|clock\.now' -- src/docket/intake.py
```
