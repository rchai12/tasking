# Phase 2f: Authenticated client identity

## Goal

Enforce the authenticated client identity on both email intake routes, so another token can never create or replay an email request. Require explicit identity for direct intake calls and reject non-string identity/reference values in the keyed core with fixed refusal codes. This closes audit finding 1 and the runtime type-narrowing part of finding 8; it adds no client, transport, dependency or migration.

Sections: `core`. The `tooling` section runs in the full check.

Follow `docs/phase-conventions.md`. N is 795, the tests the previous phase left passing.

Start: `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_core_identity.py --ignore=tests/integration/test_intake_identity.py --ignore=tests/integration/test_web_identity.py` must show `795 passed`. The ignored files specify this phase's changed contracts; the existing 795 tests still run unchanged before implementation.

## Facts

Checked on 2026-11-17 against baseline `e16914d`:

- `clients.client_tokens()` already returns token-to-client identities; `CLIENTS` remains `("email",)`. `web._bearer` currently discards the matched identity and returns a bool; both routes then call intake without a client.
- `accept_task` and `accept_link` currently hardcode `client="email"`. The HTTP body shapes are email-only. The existing core supports email and agent keyed creates, but email-only links; MCP remains Stage 6.
- `create_task_once` tests membership before narrowing `client`; `add_link` tests equality before narrowing it. Lists/dicts can raise `TypeError`, and a non-string with the hash/equality of `"email"` reaches the clock instead of a fixed refusal. Source equality and provider membership need the same narrowing.
- Repository call-site search found direct intake callers only in `tests/integration/test_intake.py` and the earlier probe listed under Given files. HTTP callers pass through `web.py`. No other project's wire contract changes.
- On baseline, the 41 new cases give 30 failures and 11 regression guards. All 41 passed against a discarded 24-added-line source patch in a disposable copy. The names-only stubs give 40 failures; the unchanged production-client-list guard alone passes. No library, time policy or external-service spike is required.

## Owner's decisions

Decided 2026-11-17:

- **Require an explicit client:** direct Python callers pass `client="email"`; there is no compatibility default. Migrate the existing tests and earlier probe without weakening their assertions.
- Earlier decisions remain: a token fixes the source it may claim, the email service's approval is final, per-client retry keys, and agent access through stdio MCP.

## Architect's decisions

- Keep HTTP intake email-only. An authenticated identity other than `email` gets the existing core code `invalid_client`, at 422. It is not an authentication failure: missing or unmatched tokens remain 401 `unauthorized` with `WWW-Authenticate: Bearer`.
- Validate the key first, then the explicitly supplied client, then the existing task/body/deadline checks. The new client gate precedes a link's task lookup; the order for email callers stays unchanged.
- Keep `_bearer` private; it may be renamed or replaced by a private helper returning the matched client or `None`. Keep `hmac.compare_digest` for token comparison. No new public names or constants are needed.
- Narrow runtime values with `isinstance(value, str)` before membership or equality; do not coerce them with `str()` or turn unexpected library exceptions into successful answers. A non-string merely comparing equal to an allowed string is invalid.
- Preserve valid agent calls directly to the keyed core. No agent token is issued or read in production; the second and third identities are synthetic fixtures only.

## Requirements

1. **Explicit intake signatures:** `accept_task(store: Store, *, client: object, key: str | None, body: object) -> Answer` and `accept_link(store: Store, task_id: str, *, client: object, key: str | None, body: object) -> Answer`. `client` is keyword-only with no default. Keep `Answer`, current constants and all other public signatures unchanged. Given: `test_client_is_a_required_keyword`.
2. **Client gate in both functions:** after the existing key check (400 `missing_key`), reject any client that is not a string equal to `email` with `Answer(422, {"error": "invalid_client"})`. This precedes body parsing, link task lookup, core calls, clock reads and writes. Preserve the existing validation order for an email caller: task shape, deadline, core; link task lookup, shape, source, core. Given: `test_only_email_identity_can_enter_intake`, `test_key_then_client_then_existing_body_order`.
3. **Keep identity and retry history separate from body text:** pass the checked `client` into `create_task_once` and `add_link`. The body source cannot choose the client. An email identity claiming source `agent` is still 422 `invalid_source`. New requests, repeats, conflicts, audit actors and the canonical stored body retain their established behaviour. An agent core request using a key does not reserve that key for email, and a refused HTTP identity cannot read, replay or replace an email key. Given: `test_identity_is_not_taken_from_the_body`, `test_email_identity_keeps_retries_links_and_key_conflicts`, `test_an_agent_core_key_does_not_reserve_the_email_key`.
4. **HTTP carries the matched identity:** authenticate against the token-to-client mapping using `hmac.compare_digest`; pass the matching value into both intake functions. Never infer it from token order, body source or a hardcoded email identity. Missing/malformed/unmatched bearer tokens keep the existing 401 answer and header, before reading/parsing the body or opening a store. A matched non-email identity reaches the intake gate and returns 422 `invalid_client`, without a `WWW-Authenticate` header. All replies keep `Cache-Control: no-store`. Given: `test_http_passes_the_matched_identity_to_intake`, `test_another_token_cannot_act_as_email`, `test_unknown_token_still_fails_before_body_or_store`.
5. **Keyed core runtime narrowing:** `create_task_once` rejects non-string `client` as `invalid_client`, non-string `source` as `invalid_source`, and non-string email `provider` as `invalid_reference`. `add_link` rejects non-string `client` as `invalid_client` and non-string `provider` as `invalid_reference`. Retain the existing refusal order: create client, key, title, source, reference, work; link client, key, reference. All these refusals happen before the clock or transaction. Lists, dictionaries and equal/hash-compatible non-strings never leak `TypeError` or reach SQLite. Existing valid strings and non-email tasks with absent references still work. Given: `test_keyed_create_refuses_non_string_identity_fields`, `test_links_refuse_non_string_identity_fields_before_the_clock`, `test_valid_agent_core_create_remains_available`.
6. **Preserve boundaries:** no new production client, source, route, token issuance rule, schema, dependency, retry-key format or audit action. Do not broaden the email JSON shapes to accept an agent body. Each processed routed request still opens and closes its own store. Retain the host check, 64 KiB rule, refusal text, response shapes and telemetry settings. Given: `test_no_new_production_client_is_enabled`, `test_two_token_map_keeps_email_retries_and_refuses_source_spoofing`, existing web/core tests; add the privacy test below.
7. **Migrate existing Python test callers:** in `tests/integration/test_intake.py`, add only `client="email"` to every `accept_task` and `accept_link` call. Keep every existing assertion, case, helper and test name. This is an explicit exception to the earlier given-file protection for those call-site edits only. The earlier probe's three calls are already migrated in this phase's given baseline; do not edit it. No other existing test changes are allowed. Existing 55 intake tests remain part of the full acceptance run.

8. **Progress entry** for `## Phase 2f: Authenticated client identity (YYYY-MM-DD)` at the end of `docs/progress.md`.

## Given files

Already committed with this spec; never change them.

| File | What it is |
|---|---|
| `tests/integration/test_core_identity.py` | 14 tests from 3 functions (requirement 5) |
| `tests/integration/test_intake_identity.py` | 11 tests from 6 functions (requirements 1–3) |
| `tests/integration/test_web_identity.py` | 16 tests from 5 functions (requirements 4 and 6) |
| `docs/verification/probe-02b.py` | Earlier probe: only its three direct intake calls now pass an explicit email identity |
| `docs/verification/probe-02f.py` | The verifier's probe |

Given test count: **41** (14 functions). Eleven cases already pass on baseline as regression guards; 30 must fail until this phase is built.

## Tests to write

Write `tests/integration/test_identity_coverage.py` for remaining behaviour branches in the three touched critical modules. Include a privacy regression with synthetic token, title and reference markers: the refused non-email request returns only the constant error body, stdout/stderr and captured logs contain none of those markers, and the database is unchanged. Keep expectation values literal. Do not change given tests or add exclusions to obtain full coverage.

## Scope

| Path | Change |
|---|---|
| `tests/integration/test_identity_coverage.py` | create |
| `src/docket/core.py` | edit: narrow keyed client/source/provider checks; shared reference helper may gain the provider type guard |
| `src/docket/intake.py` | edit: required client, email gate, forward checked identity |
| `src/docket/web.py` | edit: return and forward matched bearer identity |
| `tests/integration/test_intake.py` | edit: only explicit email keyword at existing intake call sites |
| `docs/progress.md` | append your entry |

## Out of scope

- Reference length/character policy, streaming body limits, worker threads, migration locking, stored-time validation, shared creation/JSON helpers, domain constants, store splitting, tools moves or static typing (later audit phases).
- New HTTP clients, agent token provisioning, MCP, reminders, Discord or calendars.
- Changes to `create_task`, `change_state` or `edit_task` beyond the shared reference helper's provider type guard; no new coercion, broad exception swallowing or source conversion.
- Reading external projects, real accounts, Keychain entries or data; no package installation.
- Any change to a given file, `AGENTS.md` or the design docs.

## Rules that bite

- **Approval and identity:** the authenticated token chooses the client; the request body never authorizes itself. All writes still go through core.
- **Retry safety:** do not move a request into another client's namespace, and never consume a key for a refused identity.
- **Privacy:** fixed refusal codes only; no token, title, request body or library exception text is logged or returned.
- The scope explicitly permits the earlier intake tests' call-site migration; no assertion or test case may change. All other given files remain immutable.
- **Time through the module**: `clock.now()`, never `datetime.now()`, and never `from docket.clock import now`.
- If you stop before finishing, still write the progress entry with a `Stopped:` first follow-up (`docs/phase-conventions.md`, "When you stop").
- Commands start with `.venv/bin/python`; no bare `python3`, `pytest` or `ruff`.

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_core_identity.py --ignore=tests/integration/test_intake_identity.py --ignore=tests/integration/test_web_identity.py` (before you start) | `795 passed` |
| `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 836 passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest tests/integration/test_core_identity.py tests/integration/test_intake_identity.py tests/integration/test_web_identity.py --no-cov -q` | `41 passed` |
| `.venv/bin/python -m coverage report --include=src/docket/core.py,src/docket/intake.py,src/docket/web.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| `.venv/bin/python docs/verification/probe-02f.py` | last line `FAILURES 0` |
| `grep -c "^## Phase 2f: " docs/progress.md` | `1` |
| `.venv/bin/python scripts/check_reports.py --phase 2f` | `Reports OK.` |
| `git diff HEAD --stat -- tests/integration/test_core_identity.py tests/integration/test_intake_identity.py tests/integration/test_web_identity.py docs/verification/probe-02b.py docs/verification/probe-02f.py` | no output |
| `git status --short` | only the Scope paths |

### Searches

Each prints nothing.

```zsh
git grep --untracked -n -E 'import (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)|from (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)' -- src
git grep --untracked -n -E 'print\(|logging|logger|warnings\.warn' -- src ':!src/docket/cli.py'
git grep --untracked -n -E 'datetime\.now|datetime\.utcnow|date\.today|time\.time\(|from docket\.(clock|ids) import' -- src ':!src/docket/clock.py'
git grep --untracked -n -E '\.(insert_task|update_task|append_audit|insert_link|insert_request_key)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'
git grep --untracked -n -E 'ollama|anthropic|openai|langchain' -- src
git grep --untracked -n -E 'pragma: no cover|noqa' -- src/docket/core.py src/docket/intake.py src/docket/web.py
git grep --untracked -n -E 'os\.environ|getenv\(|strftime\(|import locale' -- src/docket/core.py src/docket/intake.py src/docket/web.py
```
