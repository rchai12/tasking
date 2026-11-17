# Codebase audit

Nov 15, 2026. Read-only review of `src/docket`, `tests`, and `scripts`, with a short note on `.claude/skills/phase-architect/phase_tools.py`. The tree is at the end of Phase 2e: tasks, keyed intake, the loopback API, and the phase tools. Reminders, presses, and calendars are not built yet.

About 2,600 lines of application code and 6,500 lines of tests. Nothing here is a single unreadable file. The largest product module is `src/docket/store.py` at 490 lines. The risk is the shape those next phases will extend.

## What is already solid

These are worth keeping as the code grows.

- A task change goes through `docket.core`, in one `BEGIN IMMEDIATE` transaction, with the audit row in the same transaction. Repeats write nothing.
- SQL values are bound parameters. The few f-strings are column lists and placeholders, not user text.
- Refusals are fixed codes. API bodies are `{"id": ...}` or `{"error": <code>}`. Keychain failures name the item, never the secret.
- The API binds to 127.0.0.1, rejects any other `Host`, turns FastAPI telemetry off, and logs no access line.
- Tests stay offline: the network fixture, the failing keyring backend, and synthetic titles.
- Migrations are append-only, and triggers refuse deletes of tasks and edits of audit rows.

## Findings

Do the first three before a second client, a reminder loop, or another stored field. The rest can ride along with the phase that next touches the file.

| | Severity | Where | Issue |
| --- | --- | --- | --- |
| 1 | High | `web.py`, `intake.py` | A bearer token is not tied to the client it was issued for |
| 2 | Medium | `views.py`, `core.py`, `schema.py` | Email reference fields are stored and printed with no character or length rule |
| 3 | Medium | `web.py`, `store.py` | Async routes call SQLite on the event loop, and a lock can block for 5 seconds |
| 4 | Medium | `core.py`, `store.py` | The create path and the JSON form are copied |
| 5 | Medium | `schema.py`, `core.py`, `views.py`, `cli.py` | States, sources, and providers are repeated string lists |
| 6 | Medium | `store.py` | One class owns every table, and the next phases add more tables |
| 7 | Medium | `reports.py`, `tests/` | Phase tooling sits in the product package and has split the tests |
| 8 | Low | `config.py`, `scripts/check.py` | Settings errors fall through to the wrong message, and nothing type-checks the hints |
| 9 | Low | `ids.py`, `store.py` | Id and migration rules in the docs do not match the code a new phase will copy |

### 1. The token does not choose the client

`docket.clients.client_tokens` returns a map from token to client name. `docket.web._bearer` returns a bool and only asks whether the presented token equals some key of that map. `accept_task` then always calls `create_task_once` with `client="email"`.

```python
def _bearer(header: str | None, tokens: Mapping[str, str]) -> bool:
    if header is None or not header.startswith(_BEARER):
        return False
    presented = header[len(_BEARER) :]
    return any(hmac.compare_digest(presented, known) for known in tokens)
```

`docs/decisions.md` says the token fixes the source that request may claim, because any local process can reach 127.0.0.1. With `CLIENTS = ("email",)` that property holds by accident: the only token is the email token, and the body source must equal `"email"`. The function that could enforce it throws the client name away. The first extra entry in `CLIENTS` (the agent token the MCP server will need) authorizes `POST /tasks` as the email client unless this call is changed first.

Pass the matched client into `accept_task` and `accept_link`, and let `create_task_once` keep requiring `source == client`. Add a test with two tokens where the second one is refused for an email body.

### 2. Printed email fields skip the title rule

Titles are refused when they contain a control, format, or line-separator character, or when they are longer than 100 characters. `message_id` and `link` only have to be non-empty strings. The schema checks `length >= 1` and a provider name. `task_detail` prints both fields straight to the terminal:

```python
if task.source == "email":
    source = f"Source: email, {task.provider} {task.message_id}"
else:
    source = f"Source: {task.source}"
# ...
if task.link is not None:
    lines.append(f"Link: {task.link}")
```

A process that holds the email token can store a `message_id` with newlines or terminal escapes. `docket tasks show` will then draw extra lines or escape sequences. The same bytes sit in `tasks` forever: rows are never deleted, and nothing caps these columns except the 64 KiB body limit. Apply `check_title`'s character classes, plus an explicit max length, to every string the CLI or a later card will show. Keep the check in `docket.core`, and add a schema `CHECK` for the length so a direct store write cannot bypass it.

### 3. SQLite runs on the event loop

`_handle` is `async` and opens the store inline. Starlette only moves a route to a thread when the route is a plain function. `PRAGMA busy_timeout = 5000`, so a write lock held by the CLI makes that request block the loop for up to five seconds. Today the process serves one person and has no other loop. Phase 3 puts the reminder loop in this same process. A blocked loop delays reminders, which is the failure the architecture is built to avoid.

Two smaller cousins of the same gap:

- The 64 KiB limit runs after `await request.body()`. The decision refuses an oversized body before parsing, and the code does that, but the bytes are already in memory. Cap the read itself.
- `Store.__init__` reads `user_version`, then migrates. Two processes opening an old file can both apply the same migration. `build_app` opens the store once at startup, which covers a single server. It does not cover the server and the CLI during an upgrade. If migration raises, `__init__` does not close the connection (the newer-schema path does).

Make the routes plain `def` endpoints, or run store calls in a worker thread, before the reminder loop shares the process. Keep the busy timeout.

### 4. Two create paths and two JSON writers

`create_task` and `create_task_once` each check the title, source, reference, and work time, then insert the same row and append the same audit snapshot (`core.py` around lines 78 and 222). The keyed path adds the request-key row, which is the real difference. A later field (a reminder plan, a calendar id) has to be added in both snapshots or the audit log silently disagrees with the row.

The canonical JSON form is also written twice, with the same arguments:

- `store._json` (`store.py` lines 102-103), used when a request key is saved
- `core._canonical` (`core.py` lines 314-316), used when a retry is compared

Idempotency depends on those two staying identical. One private helper for "insert a new open task and its create audit row", and one shared `canonical_json`, remove that trap without merging the keyed and unkeyed public functions.

`cli.py` and `intake.py` each compile the same date and time patterns and each call `fromisoformat`. A third parser will appear with the Discord deadline form. One function that turns a `YYYY-MM-DD` and an `HH:MM` into a `date` and a `time`, raising a typed error, is enough.

### 5. The closed lists are copied

The same facts live in more than one place, and a new phase edits them by hand:

| Fact | Copies |
| --- | --- |
| States `open`, `in_progress`, `done`, `cancelled` | `schema.py` CHECK, `core._OPEN` and `_next_state`, `views._LABELS`, `cli.list_tasks` |
| Sources and actors | `schema.py` CHECK, `core._SOURCES`, `_ACTORS`, `_ACTOR_FOR_SOURCE` |
| Providers `gmail`, `outlook`, `yahoo` | two CHECKs in `schema.py`, `core._PROVIDERS` |
| Key length 1 to 200 | `schema.py`, `core._check_key`, `intake._valid_key`, and `web._handle` (`range(1, 201)`) |
| Work length 5 to 720 | `schema.py`, `deadlines.py`, `config.Settings`, the CLI message |
| Zone names | `config.Settings` calls `available_timezones()` on every load; `deadlines.py` caches its own set |

The schema cannot import a Python tuple, so the SQL text will stay a second copy. Put the lists in one module and add one test that the `CHECK` text contains those same tokens. `get_settings` needs the same treatment for its messages: an unrecognized validation error is reported as `DOCKET_WEB_PORT must be 1024 to 65535` (`config.py` lines 61-68). The next setting will lie about why it failed until someone extends that chain.

### 6. `Store` is the file every phase will touch

`Store` is one class of about 360 lines: connection, migration, tasks, audit, links, and request keys. The roadmap still adds reminders, posts, proposals, a calendar queue, and calendar links. Following the current pattern puts all of them on this class. `update_task` already builds a dynamic `SET` clause by hand. More optional columns will make that method the risky one.

Split by table (`tasks`, `audit`, `links`, `request_keys`, and later `reminders`) behind the same `Store` type and the same `transaction()` method, before Phase 3 adds the reminder table. Keep plain SQL. The public methods the core calls can stay stable.

`store.py` is not too big to read today. It is the one product file that will become the one everyone is afraid to edit.

### 7. Phase tooling is inside the product, and the tests are split by arrival

`reports.py` (433 lines), `acceptance.py`, and `spotcheck.py` live in `docket` next to tasks. `parse_review` is 63 lines of "read the next line or return an error". `_one_entry` is 56 lines of the same shape. Every new progress field adds another copy of that block. `scripts/critical_modules.txt` requires every branch of those parsers to be covered. `docs/testing.md` defines a critical module as one where a bug loses a reminder, creates a task without approval, or leaks a secret, and it still says intake lives in `intake/`. The file and the doc have drifted: the file also lists `reports.py`, `acceptance.py`, `spotcheck.py`, `clients.py`, `web.py`, and `server.py`.

The coverage rule is why the tests shattered. Reports alone are six modules: `test_reports.py`, `test_reports_more.py`, `test_reports_put.py`, `test_reports_put_more.py`, `test_reports_phase.py`, `test_reports_phase_more.py`. The same `*_more.py` split exists for serve, the server, the port setting, CLI tasks, acceptance, and spot checks. `sections.toml` hides it with globs. `tests/support.py` says new tests should import shared helpers, and the store fixture plus `refused()` are still copied in `test_core.py`, `test_core_keyed.py`, `test_intake.py`, `test_store.py`, and `test_store_links.py`.

`test_core.py` (585) and `test_store.py` (513) are long because they cover one module each. Those two can stay. The `*_more.py` files are the ones that make a behavior hard to find.

When the next phase touches this area: move the parsers and `accept.py` / `spot_check.py` to a tools package, or take them off the product critical list and keep a separate gate. Fold each `*_more.py` back into the module it continues. Point the critical-module paragraph in `docs/testing.md` at the file that is actually read.

`.claude/skills/phase-architect/phase_tools.py` is 888 lines, the largest Python file in the repo. `spec_skeleton` and `guide_from_spec` are about 109 lines each of template text mixed with the linter (`lint` is 77). A template change and a lint change land in the same functions. This file is not on the request path. Split the template strings from the checks the next time the spec form changes.

`scripts/accept.py` runs acceptance rows with `/bin/zsh -c`. Those rows come from the phase specs in this repo. `spotcheck.py` writes a mutation into a source file and restores it in `finally`. A killed process leaves the mutation on disk. Both are verifier tools. Treat a spec edit as code, and run spot checks on a clean tree.

### 8. Types are declared and not checked

`scripts/check.py` runs ruff and pytest. Ruff's selected rules are `E`, `F`, `I`, `B`, and `UP`. Nothing in the check runs a type checker. The code already works around that: `core.py` uses `cast` after membership tests, and several tests splat a `dict[str, object]` into `insert_task` under `# type: ignore[arg-type]`. `AGENTS.md` requires hints on public functions. A wrong hint still passes `scripts/check.py`.

Add a type check to `scripts/check.py` when the next phase is allowed a tooling change. Until then, narrow with `isinstance` in `create_task_once` and `add_link` the way `_check_key` already does, so a value that merely compares equal to `"email"` cannot be stored.

### 9. Two rules the next phase can apply to the wrong thing

`docket.ids.new_id` returns a random UUID hex and is only called from `tests/unit/test_clock_ids.py`. Task and link ids are the SQLite row number (`t1`, `l1`). `AGENTS.md` says new ids come only from `docket.ids.new_id()`. Both statements are in force. A reminder id or an event id needs an explicit choice: row numbers, like tasks, or `new_id()`. Write that choice into `docs/architecture.md` before Phase 3 invents a third scheme.

On the way out of the store, `datetime.fromisoformat` and `Deadline(...)` trust the text in the file. A hand-edited or half-migrated row can load a naive instant or a zone name that is no longer in the zone list, and the failure shows up later in `views` or in a comparison. Re-run the UTC and zone checks in `_task_from` and fail with `StoreError` and the task id.

## What this review did not treat as a problem

- File length on its own. `cli.py` at 276 lines and `core.py` at 380 are still one idea per file. Splitting them now would only move the duplicated lists around.
- Printing a new client token once. That is the decision in `docs/decisions.md`.
- The duplicate key-length check on the HTTP path and again in `intake`. The route must answer 400 before it parses JSON, and the core must refuse a bad key when MCP calls it with no HTTP. Keep both. Finding 5 is about those limits drifting apart, not about deleting either check.
- Test volume. The product tests are specific and offline. The problem is the `*_more.py` layout, not the number of assertions.

## Suggested order

1. With the next HTTP or client change: return the client from the bearer check and thread it into intake (finding 1). Cover it with a second token.
2. With the next core change: cap and character-check `message_id` and `link` (finding 2), and extract the shared create snapshot plus `canonical_json` (finding 4).
3. Before Phase 3 starts: move SQLite off the event loop (finding 3) and split `Store` by table (finding 6). Decide where new ids come from (finding 9).
4. Whenever a phase is allowed to touch tooling: fix `docs/testing.md` against `scripts/critical_modules.txt`, and fold the `*_more.py` modules back together (finding 7).
