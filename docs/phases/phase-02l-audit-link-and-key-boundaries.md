# Phase 2l: Audit, link and request-key boundaries

## Goal

Extract normal audit-log, link and request-key SQL into three private table modules behind the unchanged Store facade. Keep one connection, one transaction owner, all records and existing validation/serialization policies. This is the first bounded part of audit finding 6; task-table SQL moves in the following phase, before reminder work.

Sections: `core`. The `tooling` section runs in the full check.

Follow `docs/phase-conventions.md`. N is 1170, the tests the previous phase left passing.

Start: `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_store_table_boundaries.py` must show `1170 passed`. The ignored file specifies this refactor; missing private modules are imported inside checks so collection still works.

## Facts

Checked 2026-11-17 against baseline `785b59f`:

- Phase 2k is committed and independently PASS: 1,170 tests, no findings. Its approved deviation writes the unchanged intake replay status as 201 minus 1 to satisfy a numeric-literal structural test. That does not weaken approval or retry behavior; this phase does not edit intake. Future architectural checks must distinguish a value's role from unrelated literals.
- Store currently owns setup, migrations, records/conversion, guards and SQL for four tables. Audit/link/key extraction is about 150–200 implementation lines; moving task SQL and its adapters at the same time risks exceeding the phase limit. The roadmap now separates these two stages; no shipped phase is renumbered.
- Ordinary SQL lives in append_audit/audit, insert_link/links/_link_exists/_read_link, and insert_request_key/request_key. Their task/link existence checks, record construction, JSON/time encoding/decoding and UTC/transaction guards can stay in Store, avoiding circular imports or new shared record classes.
- Migration-3 reference preflight also reads tasks/links. Those startup reads deliberately remain with migration orchestration, outside the ordinary table boundary; all migration strings remain unchanged.
- A standard-library SQLite subclass spike confirmed execute can record the immediate caller module and transaction state without changing Row results. Given instrumentation records ownership only after startup; it stores no request contents in its event log.
- Baseline given run: 18 cases, seven intended failures and eleven behavior guards pass. With names-only private modules, one routing check fails and seventeen guards pass. A discarded four-line request-key delegation patch advances the deciding ownership failure from request_keys to audit_log, proving the recorder reaches the moved query. No complete table extraction was built.
- Six mutations of existing behavior were caught by the new tests: task filtering, link ordering, audit ordering, rollback, canonical snapshots and write-guard order. The probe oracle passes; baseline has missing-module and SQL-owner failures while restart/rollback guards pass. Baseline check.py passes all 1,170 tests.

## Owner's decisions

No new owner choice. Preserve approval, per-client keys, immutable task/audit history, stored-time/refusal behavior, private startup locking and existing SQLite timeout. This internal extraction adds no capability or data policy.

## Architect's decisions

- Create `docket._store_audit`, `docket._store_links` and `docket._store_keys`. They own ordinary SQL for audit_log, links and request_keys respectively. Their entry functions receive the existing sqlite3.Connection as their first positional parameter, named connection, and execute through connection.execute. The coder chooses private function names, remaining signatures and typed Row/scalar return shapes.
- These are private SQL modules, not alternate stores. They do not import docket modules, create/open/close connections, own transactions, configure PRAGMAs, run migrations, validate domain inputs, construct public records, read clocks or encode/decode JSON/timestamps. Store imports each module and calls it through that module so its guard order and dependency are testable.
- Keep Task, AuditEntry, Link, RequestKey, StoreError, UNCHANGED, constants and public signatures in docket.store. Store retains all conversion helpers, ID parsing, validation, ownership checks, transaction state, setup/cleanup and migration preflight. No records module or generic CRUD abstraction.
- Keep ordinary task SQL in Store for the next phase. Migration/preflight task/link SQL also remains in Store, with no table-helper call required during initialization. New helper modules are included in the given critical-module gate.
- This split inserts a new planned task-table phase before tooling cleanup. The roadmap's previously unshipped tooling/test/type-check rows shift forward by one letter; historical specs keep their original forward references, and the current roadmap is authoritative.

## Requirements

1. **Three private SQL boundaries:** implement the three modules above. Route all normal audit-log, link and request-key SELECT/INSERT SQL through its own module, including link existence and single-link readback. Task SQL, startup PRAGMAs, migrations and reference preflight remain in Store. Use the supplied connection and bound parameters; retain current query semantics, columns and ordering. Given: module shape and instrumented ownership checks.
2. **Unchanged facade:** preserve every Store public method, record class, constant, sentinel identity and error message. Public records and error types remain owned by docket.store. Store keeps domain/UTC/transaction/ID/existence checks, parameter encoding, canonical JSON, row-to-record conversion and safe stored-task time errors. No business decision moves into a table helper. Given: record/sentinel identity, literal snapshots, guard ordering and earlier store/core tests.
3. **One connection and transaction owner:** helpers use exactly the caller's connection, with its row factory and thread check. They never connect, close, commit, roll back, enter a transaction, create a cursor or run executescript/PRAGMA SQL. Existing Store.transaction BEGIN IMMEDIATE, nested refusal, rollback/commit and flag cleanup stay authoritative. An error after audit, link or key insertion rolls the whole operation, including sequences, back together. Given: one-connection ownership test, four post-write failures, nested-transaction guard and probe.
4. **Read and persistence compatibility:** preserve audit and link per-task filters and insertion-number order, missing/malformed-ID results and request-key lookup by both client and key. Keep exact canonical JSON, Unicode, nulls, quote-containing references/titles, per-client key coexistence, UTC microsecond serialization and readback values across reopen. Table helpers return SQLite data for facade conversion; no normalization, repair or stricter audit/link/key timestamp policy. Given: literal raw rows and public records after reopen, task filtering and missing-result test, prior store tests.
5. **Retry and write safety:** core still owns every task change through the Phase 2j shared creation path. Same-body create/link retries write nothing and return the existing record; conflicts remain key_reused. Store refuses a write outside its transaction before invoking any table helper, and retains UTC-before-ID refusal order. Failed writes leave no partial task/audit/link/key or sequence update; a subsequent retry allocates the original ID. Given: normal replays, rollback/guard tests and earlier keyed-core tests; coder adds the cases below.
6. **Storage/startup invariants:** schema.py, migration SQL and schema version 3 remain unchanged. Keep task-delete and audit-update/delete triggers, foreign keys, private permissions, WAL, five-second busy timeout, startup gate, locked version checks and failed-init cleanup. Migration reference preflight remains local to Store. No settings, dependency, network operation, new source, clock read or API/CLI/MCP change. Given: trigger tests and previous startup/migration/read suites.
7. **Coverage and scope:** each new module and store.py must have 100% line and branch coverage, with every existing critical gate retained. No earlier test or given file changes. Do not extract task SQL, records, startup/migration logic or phase tooling in this phase.

8. **Progress entry** for `## Phase 2l: Audit, link and request-key boundaries (YYYY-MM-DD)` at the end of `docs/progress.md`.

## Given files

Already committed with this spec; never change them.

| File | What it is |
|---|---|
| `tests/store_boundary_cases.py` | Given synthetic SQLite recorder, failure injector and snapshots; no test cases |
| `tests/integration/test_store_table_boundaries.py` | 18 tests from 9 functions (requirements 1–6) |
| `scripts/critical_modules.txt` | Given gate additions for the three extracted private modules |
| `docs/verification/probe-02l.py` | The verifier's probe |

Given test count: **18** (9 functions). Baseline gives seven intended extraction/import failures and eleven preservation guards. Names-only module stubs give one SQL-owner failure and seventeen passing shape/behavior guards. Passing guards are expected for an extraction; the owner recorder prevents a no-op from passing.

## Tests to write

Write `tests/integration/test_audit_link_key_contracts.py`:

- A normal link/key write with a non-UTC timestamp is refused before ID lookup and any table entry call; task/link ID errors retain their existing messages and priority inside a valid transaction.
- A quote-containing retry key and nested request JSON round-trip literally and cannot change query selection. Agent/email keys with the same text remain independent; different-body task/link conflicts write nothing.
- Inject a table-helper failure before SQL and prove the caller's transaction still rolls back the task and audit, and is usable afterward. Do not catch the failure inside a table helper or add error mapping.
- Exercise every newly extracted read/write branch: empty audit/links, present/absent keys, link existence/readback, and both task and link key targets. Assert values and guard order rather than merely running branches.
- Confirm a populated legacy reference upgrade still uses the existing preflight and cleanup path, with no new connection or early table-helper dependency. Earlier migration/startup tests remain unchanged.
- Close any remaining line/branch gap with a deciding assertion; no exclusions or changes to given files.

## Scope

| Path | Change |
|---|---|
| `src/docket/_store_audit.py` | create |
| `src/docket/_store_links.py` | create |
| `src/docket/_store_keys.py` | create |
| `tests/integration/test_audit_link_key_contracts.py` | create |
| `src/docket/store.py` | edit: delegate ordinary audit/link/key SQL; retain records, conversion, guards, task SQL and setup/migrations |
| `docs/progress.md` | append your entry |

## Out of scope

- Task-table extraction (next phase), records/common-type extraction, generic repositories, ORM/dependencies, per-table Store objects or new connection owners.
- Schema/version changes, query redesign, new indexes, stricter historic timestamp validation, repair/cleanup/pruning or rewriting stored data.
- Moving core decisions, validation, JSON/time policy, startup gate or migration orchestration into helpers; changing public imports/signatures or IDs.
- Tooling/test consolidation, type-checker work, HTTP/CLI/MCP changes, reminders, calendar/Discord integrations or live services/accounts.
- Any change to a given file, `AGENTS.md` or the design docs.

## Rules that bite

- **Atomicity and retry safety:** one caller-owned transaction covers every affected table. A helper cannot commit, close or replace its connection.
- **Approval/layering:** private SQL helpers are called by Store only in production; all task changes still originate in core. No new task creation path or source capability.
- **Privacy:** bound SQL parameters and canonical JSON; no print, log, model, network or error text derived from titles, requests or library exceptions.
- **Preservation:** row classes, sentinel, UTC checks, safe stored-time errors, migration locks and immutable history stay where the existing callers expect them. Tests and probes use only synthetic temporary databases.
- **Time through the module**: `clock.now()`, never `datetime.now()`, and never `from docket.clock import now`.
- If you stop before finishing, still write the progress entry with a `Stopped:` first follow-up (`docs/phase-conventions.md`, "When you stop").
- Commands start with `.venv/bin/python`; no bare `python3`, `pytest` or `ruff`.

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_store_table_boundaries.py` (before you start) | `1170 passed` |
| `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1188 passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest tests/integration/test_store_table_boundaries.py --no-cov -q` | `18 passed` |
| `.venv/bin/python -m coverage report --include=src/docket/_store_audit.py,src/docket/_store_links.py,src/docket/_store_keys.py,src/docket/store.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| `.venv/bin/python docs/verification/probe-02l.py` | last line `FAILURES 0` |
| `grep -c "^## Phase 2l: " docs/progress.md` | `1` |
| `.venv/bin/python scripts/check_reports.py --phase 2l` | `Reports OK.` |
| `git diff HEAD --stat -- tests/store_boundary_cases.py tests/integration/test_store_table_boundaries.py scripts/critical_modules.txt docs/verification/probe-02l.py` | no output |
| `git status --short` | only the Scope paths |

### Searches

Each prints nothing.

```zsh
git grep --untracked -n -E 'import (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)|from (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)' -- src
git grep --untracked -n -E 'print\(|logging|logger|warnings\.warn' -- src ':!src/docket/cli.py'
git grep --untracked -n -E 'datetime\.now|datetime\.utcnow|date\.today|time\.time\(|from docket\.(clock|ids) import' -- src ':!src/docket/clock.py'
git grep --untracked -n -E '\.(insert_task|update_task|append_audit|insert_link|insert_request_key)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'
git grep --untracked -n -E 'ollama|anthropic|openai|langchain' -- src
git grep --untracked -n -E 'pragma: no cover|noqa' -- src/docket/_store_audit.py src/docket/_store_links.py src/docket/_store_keys.py src/docket/store.py
```

## Test path migration (Phase 2q)

The product continuation paths above now use behaviour names. This is a byte-identical file move; function names, parameter IDs, counts and original implementation history are unchanged. The phase's immutable move inventory records every old/new selector.
