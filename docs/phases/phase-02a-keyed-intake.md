# Phase 2a: Keyed intake

## Goal

Make creating a task and adding a follow-up link safe to retry: a request carries a key, and the same key with the same request answers with what it made the first time, never a second task or link. This is the core the intake API (2b, 2c, 2d) and later Conductor's MCP tools stand on: `docket.core` checks the key, makes the task or link, and records the key in one transaction. Migration 2 adds the two tables. Checking the email service's JSON and every HTTP answer are Phase 2b and 2c; pruning old links and keys is a later job of the service.

Sections: `core`. The `tooling` section runs in the full check.

Follow `docs/phase-conventions.md`. N is 522, the tests the previous phase left passing.

Start: `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_store_links.py --ignore=tests/integration/test_core_keyed.py` must show `522 passed`. The ignored files import names you create.

## Facts

Each checked on this machine on 2026-11-14.

- **Migration 2** was run on a scratch database with a task in it: valid links and keys go in, the same key under two clients is allowed, and all 12 bad rows tried are refused (unknown task or link, unknown provider or client, empty message id, link or key, a 201-character key, a duplicate key, an agent key pointing at a link, a missing request). Links and keys can be deleted; tasks still can't.
- **The store runs a migration's statements one by one** inside one transaction (Phase 1b's approved deviation, with `sqlite3.complete_statement`), so migration 2 is plain SQL with no `BEGIN`.
- **Earlier pins move**: `tests/integration/test_store.py` checks `SCHEMA_VERSION == 1` and `PRAGMA user_version == (1,)`; both become 2. Phase 1e's `tests/e2e/test_cli_tasks_more.py` used version 2 as "newer than the store knows"; it becomes 99. All three are given edits.
- **`BEGIN IMMEDIATE`** (Phase 1b) makes a second writer wait, so two senders of one key at once can't both find it missing.
- **The email service's keys** are `<provider>:<message id>` with its account (`gmail:personal/18c2f0a1`), at most about 160 characters; it answers 409 for a key reused with another body or task.

## Owner's decisions

Decided 2026-11-14:

- **Split of stage 2:** 2a keyed creation and links in the core with migration 2 (this phase); 2b the email service's JSON checked and mapped to answers; 2c the HTTP routes with client tokens; 2d `docket serve`.
- **A retry key is matched per client**: the same key from two clients is two requests.
- **Links and keys of tasks ended more than a year ago are pruned** by a later job, so neither table is protected the way tasks and the audit log are.
- **Tokens** come from `docket clients add email`, printed once (Phase 2c).

## Architect's decisions

- **The source is the client**: a keyed task from client `email` has source `email`, from `agent` source `agent`. Owner commands and proposals don't use keys.
- **A request is compared as data**: two requests are the same when their canonical JSON is (`json.dumps(request, sort_keys=True, ensure_ascii=False, separators=(",", ":"))`), so key order doesn't matter.
- **A repeat answers with the task as it is now**, edits included, with `changed=False`.
- **A key names one thing**: a key that made a task can't be reused for a link, or the other way round (`key_reused`).
- **Links come only from the email client**, and may follow an ended task: a later email is still worth keeping, and nothing about the task changes. A link writes no audit row; the links table is its record.
- **The key is looked up before the task**: a repeated link answers with its link even if the request would now be refused.
- **Link ids are `l1`, `l2`**, given out in order like task ids.

## Requirements

1. **`src/docket/schema.py`** is given: migration 2 adds `links` and `request_keys`; `SCHEMA_VERSION` is 2. Do not change it.
2. **`src/docket/store.py`, names**: `UNKNOWN_LINK_MESSAGE = "unknown link"`. `Link`, a frozen dataclass: `id: str` (`"l"` and the row's number), `task_id: str`, `provider: str`, `message_id: str`, `link: str`, `created_at: datetime`. `RequestKey`, a frozen dataclass: `client: str`, `key: str`, `request: dict`, `task_id: str`, `link_id: str | None`, `created_at: datetime`.
3. **`Store.insert_link(task_id, *, provider, message_id, link, at) -> Link`** and **`Store.insert_request_key(*, client, key, request, task_id, link_id, at) -> RequestKey`**: outside a transaction `StoreError(TRANSACTION_MESSAGE)`, then a non-UTC `at` `StoreError(INSTANT_MESSAGE)`, then an id naming no task `StoreError(UNKNOWN_TASK_MESSAGE)`, then (for a key) a `link_id` naming no link `StoreError(UNKNOWN_LINK_MESSAGE)`; anything else the schema refuses surfaces as `sqlite3.IntegrityError`. The request is stored as its canonical JSON (Architect's decisions) and instants as Phase 1b's text.
4. **`Store.links(task_id) -> list[Link]`**, in the order added (none for an unknown or malformed id), and **`Store.request_key(client, key) -> RequestKey | None`**.
5. **`src/docket/core.py`, codes**: `INVALID_CLIENT = "invalid_client"`, `INVALID_KEY = "invalid_key"`, `KEY_REUSED = "key_reused"`. `LinkOutcome`, a frozen dataclass: `link: Link`, `changed: bool`.
6. **`create_task_once(store, *, client, key, request, title, source, deadline=None, work=None, provider=None, message_id=None, link=None) -> Outcome`** checks, raising the first that fails and with no clock read or store access: the client is `email` or `agent` (`INVALID_CLIENT`); the key is a `str` of 1 to 200 characters (`INVALID_KEY`); then `create_task`'s checks in its order, with the source also required to equal the client (`INVALID_SOURCE`). Then it reads the clock once and, in one transaction:
   - a key of this client that made a task with the same request: returns `Outcome(<that task as stored now>, False)` and writes nothing;
   - any other use of the key: `CoreError(KEY_REUSED)`;
   - otherwise: inserts the task as `create_task` does, with its `create` audit row (the actor follows the source), records the key with the request and the task, and returns `Outcome(task, True)`.
7. **`add_link(store, task_id, *, client, key, request, provider, message_id, link) -> LinkOutcome`** checks, with no clock read or store access: the client is `email` (`INVALID_CLIENT`); the key (`INVALID_KEY`); `provider` is `gmail`, `outlook` or `yahoo` and `message_id` and `link` are non-empty strings (`INVALID_REFERENCE`). Then it reads the clock once and, in one transaction:
   - a key of this client that made a link on this task with the same request: returns `LinkOutcome(<that link>, False)`;
   - any other use of the key: `CoreError(KEY_REUSED)`;
   - otherwise an id naming no task: `CoreError(UNKNOWN_TASK)`; else inserts the link (an ended task included), records the key with the request, the task and the link, and returns `LinkOutcome(link, True)`. No audit row.
8. **One transaction per call**, so a failure anywhere leaves no task, link, audit row or key behind, and two senders of one key at once make one task: the second gets the first's answer or `key_reused`.
9. **Only the core writes**: no other module calls `insert_link` or `insert_request_key` (nor Phase 1b's writes).

10. **Progress entry** for `## Phase 2a: Keyed intake (YYYY-MM-DD)` at the end of `docs/progress.md`.

## Given files

Already committed with this spec; never change them.

| File | What it is |
|---|---|
| `tests/integration/test_store_links.py` | 19 tests from 12 functions (requirements 1 to 4) |
| `tests/integration/test_core_keyed.py` | 38 tests from 14 functions (requirements 5 to 9) |
| `src/docket/schema.py` | Migration 2 (requirement 1) |
| `tests/integration/test_store.py` | Edited: the schema version pins become 2 |
| `tests/e2e/test_cli_tasks_more.py` | Edited: its "newer schema" becomes 99, since 2 is now current |
| `docs/verification/probe-02a.py` | The verifier's probe |

Given test count: **57**.

## Tests to write

The given tests cover every requirement's main cases. To reach full coverage, add behaviour tests in new `*_more.py` files beside them, never by changing a given test.

## Scope

| Path | Change |
|---|---|
| `src/docket/store.py` | edit: `Link`, `RequestKey`, `UNKNOWN_LINK_MESSAGE`, `insert_link`, `links`, `insert_request_key`, `request_key` |
| `src/docket/core.py` | edit: the three codes, `LinkOutcome`, `create_task_once`, `add_link` |
| `docs/progress.md` | append your entry |

## Out of scope

- Checking the email service's JSON, mapping codes to HTTP answers, routes, tokens and `docket serve` (2b, 2c, 2d).
- Pruning links and keys, and any delete in the store (a later job of the service).
- Showing links in `docket tasks show`; MCP tools; reminders and calendar writes for a keyed task.
- Keys for owner commands, edits or state changes.
- A cache of keys, retries around `database is locked`, or a second transaction per call.
- Any change to a given file, `AGENTS.md` or the design docs.

## Rules that bite

- **Nothing without approval**: a keyed task comes only from client `email` (whose own approval came first) or `agent` (after Conductor's), with that source; nothing here approves anything.
- **Everything is retry-safe**: the key check, the write and recording the key are one transaction.
- **Error messages are the codes and the store's constant texts**: never a key, a title or a request.
- **Time through the module**: `clock.now()`, never `datetime.now()`, and never `from docket.clock import now`.
- If you stop before finishing, still write the progress entry with a `Stopped:` first follow-up (`docs/phase-conventions.md`, "When you stop").
- Commands start with `.venv/bin/python`; no bare `python3`, `pytest` or `ruff`.

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_store_links.py --ignore=tests/integration/test_core_keyed.py` (before you start) | `522 passed` |
| `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 579 passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest tests/integration/test_store_links.py tests/integration/test_core_keyed.py --no-cov -q` | `57 passed` |
| `.venv/bin/python -m coverage report --include=src/docket/store.py,src/docket/core.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| `.venv/bin/python docs/verification/probe-02a.py` | last line `FAILURES 0` |
| `grep -c "^## Phase 2a: " docs/progress.md` | `1` |
| `.venv/bin/python scripts/check_reports.py --phase 2a` | `Reports OK.` |
| `git diff HEAD --stat -- tests/integration/test_store_links.py tests/integration/test_core_keyed.py src/docket/schema.py tests/integration/test_store.py tests/e2e/test_cli_tasks_more.py docs/verification/probe-02a.py` | no output |
| `git status --short` | only the Scope paths |

### Searches

Each prints nothing.

```zsh
git grep --untracked -n -E 'import (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)|from (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)' -- src
git grep --untracked -n -E 'print\(|logging|logger|warnings\.warn' -- src ':!src/docket/cli.py'
git grep --untracked -n -E 'datetime\.now|datetime\.utcnow|date\.today|time\.time\(|from docket\.(clock|ids) import' -- src ':!src/docket/clock.py'
git grep --untracked -n -E '\.(insert_task|update_task|append_audit|insert_link|insert_request_key)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'
git grep --untracked -n -E 'ollama|anthropic|openai|langchain' -- src
git grep --untracked -n -E 'pragma: no cover|noqa' -- src/docket/store.py src/docket/core.py
```

## Corrections

Added 2026-11-14, after the first coder run stopped on the probe (its `Stopped:` follow-up).

1. **`docs/verification/probe-02a.py`.** The walk used `t99` as a task that doesn't exist, but it creates up to about 265 tasks, so by step 270 `t99` was real and the code rightly added a link to it while the probe expected `unknown_task`. The probe's fault, not the code's. The unknown id is now `t99999`, beyond any id the walk can create (it asserts that). Against the code the coder already wrote, the corrected probe prints `FAILURES 0`; `check.py --first core`, the coverage command and every search also pass on that code.

Nothing else changes: no requirement, message, given test or count. The coder keeps its code, runs every command under Acceptance again, and updates its existing Phase 2a entry in place, replacing the `Stopped:` follow-up.
