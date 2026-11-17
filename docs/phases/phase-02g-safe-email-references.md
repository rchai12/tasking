# Phase 2g: Safe email references

## Goal

Refuse unsafe or oversized email message IDs and links before they can be stored or printed. Add the shared reference predicate, use it in all three core write paths, and safely apply the given migration that bounds stored reference lengths. An invalid legacy reference blocks the upgrade with only an ID and field in the error. This implements audit finding 2; it adds no repair command or service integration.

Sections: `core`. The `tooling` section runs in the full check.

Follow `docs/phase-conventions.md`. N is 837, the tests the previous phase left passing.

Start: `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_references.py --ignore=tests/integration/test_core_references.py --ignore=tests/integration/test_reference_migration.py --ignore=tests/e2e/test_reference_intake.py` must show `837 passed`. The ignored files specify the new reference and upgrade contracts. The given schema and current-version test pins are already updated; no new test is counted in N.

## Facts

Checked on 2026-11-17 against baseline `261d3e1`:

- Phase 2f passed with 837 tests, no findings and no deviations. Existing references are nonempty strings with allowed providers; only titles currently reject Cc, Cf, Zl and Zp. `views.task_detail` prints the message ID and link verbatim.
- Read-only inspection of `emails/src/mailroom/tasks_app.py`, `emails/tests/fakes.py` (`FakeTasksApp`) and `emails/docs/interfaces.md` found no field-specific message-ID/link cap. Payloads carry these values unchanged, and `task_key` derives a retry key from provider and message ID. This phase preserves the separate 1–200-character retry-key rule; a 512-character message ID is not a promise that its derived email retry key fits.
- SQLite cannot replace existing column CHECKs in place. A scratch parent/child rebuild fails with immediate foreign keys and also with deferred foreign keys. Disabling foreign keys before the rebuild transaction, preserving the original table names and checking foreign keys before commit succeeds. The given migration preserves every existing table row, retry-key JSON, immutable audit row and sequence in the populated synthetic fixture.
- SQLite `length(text)` stops at NUL. The new CHECKs also refuse NUL so a short prefix cannot conceal an overlong suffix from direct SQL.
- Current-version pins appear in the three earlier test files listed under Given files; all five assertions are migrated to version 3. Newer-schema cases stay at 99 and the v1 migration input stays at 1. No earlier probe pins the current version.
- A temporary predicate/core patch of fewer than 30 added source lines passed 55 targeted cases (pure rules, core and HTTP/valid CLI); it was removed. No migration runner or complete feature was built. The given SQL was exercised directly on a populated v2 fixture, and 74 existing store/server tests passed (the loopback case was excluded from that scratch run).

## Owner's decisions

Decided 2026-11-17:

- **Caps:** message IDs are 1–512 characters; links are 1–2,048 characters.
- **Legacy data:** refuse an upgrade containing a reference outside the new length or character rules, without changing data. Report only its task/link ID and field. Any repair is a separate, explicitly authorized action.
- Earlier decisions remain: refuse invalid text rather than rewriting it; preserve tasks and immutable audit history; no real data, accounts or Keychain during development.

## Architect's decisions

- Add `docket.references` as a small pure dependency of core and store, avoiding a core/store import cycle. It exports `MESSAGE_ID_MAX = 512`, `LINK_MAX = 2048`, and `valid_reference(value: object, maximum: int) -> bool`; no exception type or configuration setting is added.
- Count Unicode code points, not UTF-8 bytes. Match the title rule's forbidden Unicode categories, but do not trim whitespace, normalize Unicode, parse URLs or restrict schemes. Providers remain the existing fixed list.
- Bound length and refuse NUL in the schema; enforce the full Unicode character policy in core and during the v2 preflight. Do not attempt to encode every Unicode category into SQLite CHECK text.
- Error text is exactly `invalid stored reference: <id> <field>` for a legacy violation. Scan tasks first, then links, by numeric ID, checking `message_id` before `link`. A failed foreign-key integrity check reports exactly `invalid reference migration`. Do not echo offending values.
- The rebuild requires foreign keys off only around migration 3, restored on success and failure. Closing a failed migration's connection belongs here because this phase introduces a normal upgrade-refusal path. Version-read races and other startup failures remain Phase 2i work.

## Requirements

1. **Pure reference policy:** implement the three names in Architect's decisions. `valid_reference` returns true exactly for a string of 1 through `maximum` code points containing no character whose Unicode category is Cc, Cf, Zl or Zp. It returns false for non-strings, empty strings, overlong strings and forbidden characters. Valid text is never rewritten. Given: `test_reference_limits`, `test_reference_boundaries`, `test_reference_character_categories`.
2. **All core entry points:** apply that policy to both email reference fields in `create_task`, `create_task_once` and `add_link`. Keep provider checks, non-email null-reference rules and existing validation order. Refuse with `CoreError("invalid_reference")`, before any clock read or write, without allocating task/link IDs, audit rows or retry keys. The same previously refused key can be used by a corrected valid request; valid repeats remain no-ops. Share a private check or predicate calls rather than three new copies of the policy. Remove `_nonempty` only if it has no remaining callers. Given: `test_invalid_references_never_write`, `test_boundaries_round_trip_without_rewriting`, `test_rejected_key_can_be_used_by_a_corrected_request`.
3. **Existing adapters:** HTTP still maps these core refusals to 422 `{"error":"invalid_reference"}` and preserves `no-store`, validation precedence and response shapes. A bad JSON type remains `invalid_body`. Valid references print exactly as stored; a CLI command opening an invalid legacy database fails before printing any reference or reading the clock. No production changes to intake, web, views or CLI are required. Given: `test_http_refuses_unsafe_reference_without_consuming_key`, `test_cli_prints_valid_reference_text_without_rewriting`, `test_cli_refuses_unsafe_legacy_data_before_printing_it`.
4. **Given migration 3:** the append-only schema now bounds both fields in tasks and links and prevents NUL length bypasses. It rebuilds only tasks and links, preserves their IDs and original columns, recreates the task-delete trigger and links index, and restores the saved AUTOINCREMENT sequences, including IDs of pruned links. Migrations 1 and 2 remain byte-identical. Do not edit the given schema. Given: `test_migration_preserves_rows_ids_sequences_and_invariants`, `test_sql_update_cannot_bypass_reference_length_checks`.
5. **Legacy preflight:** before running migration 3's SQL and while holding its write transaction, validate all email task references (all states) and every follow-up link through the shared predicate. On the first violation, raise `StoreError` with the exact ID/field error above. Do not read or rewrite audit snapshots or canonical request JSON for this validation. Refuse without changing rows, sequences or the schema version; do not truncate, escape, delete or repair data. Given: `test_invalid_legacy_reference_refuses_without_data_changes`, CLI refusal test.
6. **Safe rebuild transaction:** disable connection foreign-key enforcement before entering migration 3's transaction, perform the preflight and given SQL, and require an empty `PRAGMA foreign_key_check` before advancing the version to 3 and committing. Restore `PRAGMA foreign_keys = ON` in every exit path. A preflight or SQL failure rolls the migration back and closes the failed constructor's connection; unexpected SQL errors may propagate, without logging their text. Do not disable foreign keys for ordinary operations or other migrations. Given: `test_failed_migration_rolls_back_closes_and_restores_foreign_keys`, `test_foreign_key_check_failure_refuses_the_upgrade`, valid populated upgrade test. Add the successful-connection and preflight-failure closure tests below.
7. **Preserve storage contracts:** valid populated upgrades preserve every task, link, audit row, request-key body and task/link sequence; repeated task/link requests still return the same IDs without writes. Task-delete and audit-update/delete triggers, file modes, WAL, the 5-second timeout and normal foreign-key enforcement remain in force. No schema version beyond the given 3, new stored field, dependency or repair command. Earlier given tests have only current-version pins changed; the coder must not change them. Given: migration tests and the existing suite.
8. **Critical coverage:** `references.py` is already added to the given critical list. Cover every line and branch of it, core and store, and retain every other configured gate. The policy must not move into an uncovered helper.

9. **Progress entry** for `## Phase 2g: Safe email references (YYYY-MM-DD)` at the end of `docs/progress.md`.

## Given files

Already committed with this spec; never change them.

| File | What it is |
|---|---|
| `src/docket/schema.py` | Append-only migration 3, with original migrations unchanged |
| `scripts/critical_modules.txt` | Adds references.py; every earlier critical module stays listed |
| `tests/reference_cases.py` | Synthetic v2 input and database snapshot helpers; no test cases |
| `tests/unit/test_references.py` | 18 tests from 3 functions (requirement 1) |
| `tests/integration/test_core_references.py` | 28 tests from 3 functions (requirement 2) |
| `tests/integration/test_reference_migration.py` | 28 tests from 5 functions (requirements 4–7) |
| `tests/e2e/test_reference_intake.py` | 10 tests from 3 functions (requirement 3) |
| `tests/integration/test_store.py` | Earlier given file: only current-version assertions 2 to 3 |
| `tests/integration/test_store_links.py` | Earlier given file: only migration count/current-version assertions 2 to 3 |
| `tests/integration/test_server.py` | Earlier given file: only current-version assertion 2 to 3 |
| `docs/verification/probe-02g.py` | The verifier's probe |

Given test count: **84** (14 functions). Earlier test edits add no cases. Thirteen new cases already pass with the given schema as SQL/boundary/display guards; the other contracts require implementation.

## Tests to write

Write `tests/integration/test_reference_coverage.py` for remaining behaviour branches. Include:

- On a successful populated upgrade, the live connection has foreign keys enabled: inserting a link for a nonexistent task through direct SQL raises `IntegrityError` and leaves no row.
- On a preflight refusal, a tracked connection records one close and foreign keys restored to 1; no clock is read and the snapshot/version stay unchanged.
- Exact-cap non-ASCII legacy references pass preflight unchanged, and a version-1 database upgrades through all three migrations without losing its rows.
- Valid direct-store inserts pass and overlong direct-store task and link inserts fail inside their transactions. No partial audit or retry row is left.
- Any uncovered validation/rollback behaviour gets a deciding assertion, without changing a given file or excluding a branch.

## Scope

| Path | Change |
|---|---|
| `src/docket/references.py` | create |
| `tests/integration/test_reference_coverage.py` | create |
| `src/docket/core.py` | edit: use reference policy in the three write paths; remove unused private helper |
| `src/docket/store.py` | edit: migration-3 preflight, scoped rebuild transaction and migration-failure closure |
| `docs/progress.md` | append your entry |

## Out of scope

- Repairs or grandfathering of legacy data; reading real databases, Keychain entries or external services.
- URL parsing, trimming, Unicode normalization, URL-scheme rules, escaping valid references or changing the title rule.
- Changes to retry-key length, client identities, API shapes, response precedence, shared creation/JSON code or table-module boundaries.
- General migration-race remediation, stored-time validation, body streaming, worker threads, reminders, calendars, MCP, tooling moves or new dependencies (later phases).
- Any change to a given file, `AGENTS.md` or the design docs.

## Rules that bite

- **Approval:** this changes validation and upgrades, not task approval or state. Writes still go through core; migration never invents or repairs a task.
- **Privacy:** refusals contain constant text plus IDs/field names only; neither a legacy value nor a library exception is logged or shown.
- **Atomicity:** rows, retry keys, immutable audit history and AUTOINCREMENT sequences survive the rebuild. Only the given new migration is applied.
- **Synthetic data:** every test database comes from the given temporary fixture; never inspect the owner's data folder.
- The given earlier tests' version pins are already updated. No existing test or given schema file may be changed by the coder.
- **Time through the module**: `clock.now()`, never `datetime.now()`, and never `from docket.clock import now`.
- If you stop before finishing, still write the progress entry with a `Stopped:` first follow-up (`docs/phase-conventions.md`, "When you stop").
- Commands start with `.venv/bin/python`; no bare `python3`, `pytest` or `ruff`.

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_references.py --ignore=tests/integration/test_core_references.py --ignore=tests/integration/test_reference_migration.py --ignore=tests/e2e/test_reference_intake.py` (before you start) | `837 passed` |
| `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 921 passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest tests/unit/test_references.py tests/integration/test_core_references.py tests/integration/test_reference_migration.py tests/e2e/test_reference_intake.py --no-cov -q` | `84 passed` |
| `.venv/bin/python -m coverage report --include=src/docket/references.py,src/docket/core.py,src/docket/store.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| `.venv/bin/python docs/verification/probe-02g.py` | last line `FAILURES 0` |
| `grep -c "^## Phase 2g: " docs/progress.md` | `1` |
| `.venv/bin/python scripts/check_reports.py --phase 2g` | `Reports OK.` |
| `git diff HEAD --stat -- src/docket/schema.py scripts/critical_modules.txt tests/reference_cases.py tests/unit/test_references.py tests/integration/test_core_references.py tests/integration/test_reference_migration.py tests/e2e/test_reference_intake.py tests/integration/test_store.py tests/integration/test_store_links.py tests/integration/test_server.py docs/verification/probe-02g.py` | no output |
| `git status --short` | only the Scope paths |

### Searches

Each prints nothing.

```zsh
git grep --untracked -n -E 'import (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)|from (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)' -- src
git grep --untracked -n -E 'print\(|logging|logger|warnings\.warn' -- src ':!src/docket/cli.py'
git grep --untracked -n -E 'datetime\.now|datetime\.utcnow|date\.today|time\.time\(|from docket\.(clock|ids) import' -- src ':!src/docket/clock.py'
git grep --untracked -n -E '\.(insert_task|update_task|append_audit|insert_link|insert_request_key)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'
git grep --untracked -n -E 'ollama|anthropic|openai|langchain' -- src
git grep --untracked -n -E 'pragma: no cover|noqa' -- src/docket/references.py src/docket/core.py src/docket/store.py
git grep --untracked -n -E 'os\.environ|getenv\(|strftime\(|import locale' -- src/docket/references.py src/docket/core.py src/docket/store.py
```
