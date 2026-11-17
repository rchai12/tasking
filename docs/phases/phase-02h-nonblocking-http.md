# Phase 2h: Nonblocking HTTP and bounded reads

## Goal

Keep HTTP intake responsive while SQLite waits for a writer, and reject an oversized body while reading it instead of buffering it first. Both task/link routes retain their current approval, validation and response contracts. This addresses the HTTP parts of audit finding 3; migration concurrency and stored-time validation remain Phase 2i work.

Sections: `core`. The `tooling` section runs in the full check.

Follow `docs/phase-conventions.md`. N is 927, the tests the previous phase left passing.

Start: `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_web_streaming.py --ignore=tests/integration/test_web_workers.py` must show `927 passed`. The ignored files specify this phase's changed streaming and thread-affinity behaviour; they use existing public names.

## Facts

Checked on 2026-11-17 against baseline `7569539`:

- Phase 2g passed with 927 tests, no findings and no deviations. `web._handle` still calls `await request.body()` and then synchronously opens, uses and closes the store inside an async request handler.
- The installed `starlette.requests.Request.stream` yields incoming nonempty HTTP body chunks and an empty terminator, raising on disconnect. It does not impose a size limit. A body chunk can already be larger than the app's cap when delivered; the app can refuse it without copying it into an accumulated body or requesting another chunk.
- The installed `starlette.concurrency.run_in_threadpool` awaits AnyIO's worker-thread call and supports arguments. Both are already dependencies of the installed framework; no package is added. SQLite's default connection thread check remains enabled.
- The installed uvicorn HTTP scope advertises ASGI spec version 2.3. The given in-memory exchange matches that shape. A real `create_app` exchange without authentication sends its error without calling receive; Starlette's middleware response wrapper does not drain the body afterward.
- The store's 5-second busy timeout is existing behaviour. The lock test holds a real synthetic SQLite write lock and releases it only from a coroutine on the request loop, after observing the worker's write attempt. Its two-second limits are failure watchdogs, not scheduling assumptions; it uses events and cooperative yields rather than wall-clock sleeps.
- A discarded 15-added-line patch passed all 30 given cases plus 53 existing HTTP cases, with every line and branch of `web.py` covered, and passed the probe. Eight mutations failed their deciding tests. No runtime code is supplied with this spec.

## Owner's decisions

No new owner choice is required. Existing decisions apply: loopback-only API; 64 KiB maximum body, refused before JSON parsing; authenticated client identity; the established size/key/JSON/intake refusal order; no request logging; SQLite's 5-second timeout. This phase changes where blocking work runs and when the body limit is enforced, not the wire contract.

## Architect's decisions

- Keep async request handling for streaming input. After bounded reading, key checking and JSON decoding, await one synchronous worker operation containing the whole store context and intake call. Use the framework's existing thread-pool API; no dedicated executor, loop, background queue or new setting.
- Count actual incoming bytes. Do not authorize or reject based on `Content-Length`: missing, understated and overstated values do not change the size decision. This preserves the existing actual-body behaviour while bounding accumulation.
- Test through the public `create_app` ASGI interface. No private helper name, signature or buffer representation is prescribed. Keep new private helpers inside `web.py` and keep every public name and signature unchanged.
- Do not map unexpected body/store/intake failures to new success or error codes. Existing exceptions propagate, with the store context closed when intake fails. Do not add logging, retries or a timeout policy.

## Requirements

1. **Public contract:** preserve `create_app(*, open_store: Callable[[], Store], tokens: Mapping[str, str], port: int) -> FastAPI`, the two routes, constants and `MAX_BODY == 65536`. The same injected factory is called with no arguments once per request that reaches intake. Do not alter other production modules, schema, settings or dependencies. Given: the existing HTTP tests and all new cases.
2. **Bounded body read:** consume the request stream instead of `Request.body()`. Before accumulating each chunk, refuse an actual total greater than 65,536 bytes with 413 `{"error":"too_large"}`. Stop at that decisive chunk without requesting a later chunk, parsing JSON, opening a store or writing anything. An exact-cap body is allowed. Empty chunks are harmless, a multibyte UTF-8 character can span chunks, and bytes rather than character count determine size. Do not trust `Content-Length`, and do not copy an oversized chunk into the accumulated body. Given: `test_oversized_stream_stops_before_another_chunk`, `test_exact_limit_uses_actual_bytes_not_content_length`, `test_utf8_character_may_span_body_chunks`, `test_route_never_uses_request_body`.
3. **Refusal order:** host check, known route/method, bearer authentication, bounded body size, idempotency key, UTF-8/JSON document, then intake's existing client/body/deadline/core rules. Wrong host, unknown route and missing/wrong token read no body and open no store. A too-large body beats a missing key; a missing key beats bad JSON; invalid JSON/UTF-8 never opens a store. Keep all current status codes, bodies and headers, including `Cache-Control: no-store` and authentication's `WWW-Authenticate: Bearer`. Given: `test_early_refusals_do_not_read_a_stream`, `test_streaming_preserves_size_key_and_json_order`, existing HTTP tests.
4. **One awaited worker operation:** opening the store, calling the selected intake function, and closing the store all occur on the same worker thread, not the event-loop thread. The worker gets the matched client, checked key, parsed body and optional task ID; never infer identity from the body or hardcode email. Do not open a connection on the loop and pass it across threads, or dispatch separate worker calls for individual store operations. Keep SQLite's thread check enabled. Given: `test_open_intake_and_close_share_one_worker` for both routes and both synthetic identities; existing Phase 2f identity cases.
5. **Event-loop progress and cleanup:** a request waiting on a held SQLite write lock must leave the loop free to run another coroutine, which can release that lock; keep the existing 5-second busy timeout. Await completion before returning the intake answer. Close the store in that same worker on success and when intake raises; preserve the original exception and never leave a detached worker mutating after a response. Given: `test_write_lock_does_not_block_the_event_loop`, `test_intake_failure_closes_the_worker_connection`, the worker-lifetime test. Add the receive/factory failure tests below.
6. **Retry and privacy invariants:** valid repeated task/link requests retain their IDs, change nothing twice and preserve their audit actors. Each request uses its own store context. No new client, source, background service, response field, retry, log or telemetry. Do not persist raw HTTP bytes or chunks; preserve the existing canonical retry request record. Given: `test_retries_get_distinct_connections_and_one_audit_row`, existing task/link retry and privacy tests; add the refusal privacy test below.
7. **Critical coverage:** retain 100% line and branch coverage of `web.py` and every other configured critical module, without exclusions. No existing test or given file is edited.

8. **Progress entry** for `## Phase 2h: Nonblocking HTTP and bounded reads (YYYY-MM-DD)` at the end of `docs/progress.md`.

## Given files

Already committed with this spec; never change them.

| File | What it is |
|---|---|
| `tests/http_cases.py` | Synthetic ASGI 2.3 exchange, wire inputs and store lifetime recorder; no test cases |
| `tests/integration/test_web_streaming.py` | 22 tests from 6 functions (requirements 2–3) |
| `tests/integration/test_web_workers.py` | 8 tests from 4 functions (requirements 4–6) |
| `docs/verification/probe-02h.py` | The verifier's probe |

Given test count: **30** (10 functions). On baseline, 15 fail for the missing behaviour and 15 pass as boundary/precedence/UTF-8 guards. On a names-only `create_app` stub, all 30 fail.

## Tests to write

Write `tests/integration/test_http_coverage.py` for remaining behaviour and privacy assertions:

- A synthetic receive failure propagates before a store is opened; no request is partly processed.
- If the injected store factory raises, propagate that original exception; do not invoke intake or report a successful response. The factory owns cleanup of an unsuccessfully constructed store.
- An oversized request containing synthetic token/title/reference markers returns only the fixed error body, does not open a store, and leaves those markers absent from stdout, stderr and captured application logs.
- Cover any remaining branch with its deciding behaviour. Do not change given files, add exclusions, or move code to another module to obtain coverage.

## Scope

| Path | Change |
|---|---|
| `tests/integration/test_http_coverage.py` | create |
| `src/docket/web.py` | edit: bounded streaming and the complete awaited worker operation; private helpers only |
| `docs/progress.md` | append your entry |

## Out of scope

- SQLite migration/version locking or decoding stored times (2i); shared core/JSON rules, store extraction and tooling work (later audit phases).
- New dependencies, settings, executors, timeouts, body formats, response codes, retry rules or error mapping.
- New clients, routes, reminders, queues, Discord, MCP or calendar work.
- Disabling SQLite thread affinity, caching a connection across requests, reading real data or Keychain entries, or contacting any real service.
- Any change to a given file, `AGENTS.md` or the design docs.

## Rules that bite

- **Approval:** preserve the matched identity and core-only writes; offloading work must not bypass a client/source check.
- **Privacy:** cap accumulation before parsing, preserve fixed refusal bodies and emit no request/token/title logging.
- **Retry safety:** the existing core transaction still owns the task, key and audit row; no background work or second write path.
- **Offline determinism:** synthetic ASGI messages and temporary SQLite only; clock calls stay in core and are replaced by tests. Test watchdogs are not reminder/deadline logic.
- **Time through the module**: `clock.now()`, never `datetime.now()`, and never `from docket.clock import now`.
- If you stop before finishing, still write the progress entry with a `Stopped:` first follow-up (`docs/phase-conventions.md`, "When you stop").
- Commands start with `.venv/bin/python`; no bare `python3`, `pytest` or `ruff`.

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_web_streaming.py --ignore=tests/integration/test_web_workers.py` (before you start) | `927 passed` |
| `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 957 passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest tests/integration/test_web_streaming.py tests/integration/test_web_workers.py --no-cov -q` | `30 passed` |
| `.venv/bin/python -m coverage report --include=src/docket/web.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| `.venv/bin/python docs/verification/probe-02h.py` | last line `FAILURES 0` |
| `grep -c "^## Phase 2h: " docs/progress.md` | `1` |
| `.venv/bin/python scripts/check_reports.py --phase 2h` | `Reports OK.` |
| `git diff HEAD --stat -- tests/http_cases.py tests/integration/test_web_streaming.py tests/integration/test_web_workers.py docs/verification/probe-02h.py` | no output |
| `git status --short` | only the Scope paths |

### Searches

Each prints nothing.

```zsh
git grep --untracked -n -E 'import (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)|from (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)' -- src
git grep --untracked -n -E 'print\(|logging|logger|warnings\.warn' -- src ':!src/docket/cli.py'
git grep --untracked -n -E 'datetime\.now|datetime\.utcnow|date\.today|time\.time\(|from docket\.(clock|ids) import' -- src ':!src/docket/clock.py'
git grep --untracked -n -E '\.(insert_task|update_task|append_audit|insert_link|insert_request_key)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'
git grep --untracked -n -E 'ollama|anthropic|openai|langchain' -- src
git grep --untracked -n -E 'pragma: no cover|noqa' -- src/docket/web.py
git grep --untracked -n -E 'os\.environ|getenv\(|strftime\(|import locale' -- src/docket/web.py
```
