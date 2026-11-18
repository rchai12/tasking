# Phase 2m: Task table boundary

## Goal

Complete audit finding 6 by moving ordinary task SQL into its private table module on the same Store connection. Keep public records, guards, ID parsing, serialization, safe time conversion, transaction ownership and all startup/migration work in Store. This completes the table split begun in Phase 2l without a product, schema or policy change.

Sections: `core`. The `tooling` section runs in the full check.

Follow `docs/phase-conventions.md`. N is 1193, the tests the previous phase left passing.

Start: `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_task_table_boundary.py` must show `1193 passed`. The ignored file specifies the extraction; new-module imports occur inside checks, so it collects on baseline.

## Facts

Checked 2026-11-17 against baseline `360d387`:

- Phase 2l is committed and independently PASS: 1,193 tests, zero findings/follow-ups. Its approved private helper names are insert_audit/select_audit, insert_link/select_links/select_existence/select_link and insert_request_key/select_request_key. They take the existing connection and return SQLite cursors/rows. No approval or retry exception was introduced.
- Remaining ordinary task SQL is in insert_task, update_task, task, tasks, _exists and _read_task, plus the private column-list constant. SQL update assembly currently mixes fixed column assignments with facade value conversion. Reference-migration preflight also reads tasks and deliberately stays in Store.
- Store owns the public records, UNCHANGED defaults, _require_write/ID guards and _task_from UTC/zone conversion. No new records module, time parser or transaction type is needed. The new module is a small SQL-only extraction, estimated below 200 implementation lines including facade changes.
- The given recorder extends the existing three-table instrumentation to all four normal tables, preserving the original execute caller through its wrapper. It captures frames only while recording and releases them immediately; holding a frame/cursor during startup can keep a PRAGMA statement active and prevent a migration commit. Startup is intentionally unrecorded.
- Baseline given run: 26 cases from seven functions, 13 intended extraction/import failures and 13 preservation guards. Names-only module stubs give six SQL-owner failures and 20 shape/behavior guards. A discarded small task-read delegation patch passed the get-task ownership case and all three corrupt-time cases; no full task extraction was built.
- Six confirmed mutations break filtering, ordering, deadline clearing, created/updated timestamp ownership, rollback and corrupt-task refusal. The probe oracle passes; baseline reports missing module/wrong owner while restart/rollback guards pass.
- Standard-library zoneinfo independently confirmed the given fall/spring New York deadline/work instants (17:00/16:00 become 22:00/21:00 UTC on 2026-11-01 and 21:00/20:00 UTC on 2027-03-14). Time policy does not change. Baseline check.py passed all 1,193 tests.

## Owner's decisions

No new owner decision. Keep approved-source creation, per-client retries, row-number IDs, immutable history, explicit UTC/zone semantics, reference policy and the private startup gate unchanged.

## Architect's decisions

- Add `docket._store_tasks`, following the SQL-only boundary from 2l. Entry functions receive the existing sqlite3.Connection as the first positional parameter named connection, execute through connection.execute and return SQLite rows/cursors/scalars. The coder chooses private function names and remaining signatures.
- Move task SELECT/INSERT/UPDATE, existence/readback queries, the normal task column list and UPDATE SQL construction into that module. Store converts validated inputs to database values and supplies a fixed internal field map for updates; its keys are known column identifiers, never request-provided identifiers or SQL fragments. Values and filter states remain bound parameters.
- Store retains public records/constants/errors/sentinel, all checks, _deadline_values/_work_values, UTC timestamp encoding, _task_from and the transaction/setup/migration owner. Both None clearing and UNCHANGED omission remain facade decisions; the SQL helper does not interpret domain objects or sentinel values.
- Keep task/reference migration preflight and migration execution in Store. Do not route startup through ordinary task helpers or edit the three already-extracted modules. Store calls the new module through its module binding, making guards and SQL ownership testable.
- Add _store_tasks.py to the given critical-module list. This phase completes the ordinary four-table SQL boundary; phase tooling separation remains the next roadmap row.

## Requirements

1. **Task SQL owner:** implement the new module and route every ordinary task query/write through it: create, update, single-task read, list/filter, existence and post-write readback. Move the private task column list and SQL construction there. Keep only migration execution and reference preflight task SQL in Store. Existing audit/link/key ownership stays intact. Given: module-shape check, six ownership cases and four-owner probe.
2. **Same facade and safe inputs:** keep public Store signatures, records, errors, messages, UNCHANGED and ID formats/identity unchanged. Store performs transaction/UTC/ID checks before delegation and owns conversion. Private SQL code imports no docket module and performs no model/domain decisions, time or JSON parsing, connection creation/closing, transaction, cursor creation, PRAGMA or migration work. Only Store calls it in production. No generic query/fragments interface or request-supplied column name. Given: shape, six guard-order cases and all earlier store/public-identity tests.
3. **Exact create/update values:** preserve every column and source/reference field, created_at and updated_at microsecond UTC serialization, None groups and deadline time_given. Omitted update fields remain unchanged; None clears the full deadline/work group. An update with no field changes still changes updated_at as the existing low-level Store API does; created_at stays fixed. Core no-op behavior stays unchanged. Given: seven literal update cases, previous source/create snapshots and probe.
4. **Read/filter semantics:** keep single-task None for missing/malformed IDs, empty state collection returning [], None meaning all tasks, selected states filtered with bound parameters and numeric task order regardless of input filter order. Preserve quote-containing title/filter data and never interpolate it into SQL. No state-policy validation is added to the low-level read API. Given: filter/missing and literal-title tests; coder adds the deciding cases below.
5. **One connection, atomic writes:** helpers use exactly the Store connection with its existing row factory and thread checks, never commit/rollback/open/close/configure it. Preserve Store.transaction, nested refusal, clock counts, core's shared creation path, audit/key atomicity and retry behavior. A failure immediately after task INSERT or UPDATE leaves tasks, audit, links, keys and sequences unchanged; the next operation remains usable. Given: two post-SQL failures, ownership checks, prior transaction/key tests and restart/interruption probe.
6. **Safe time/read boundary:** _task_from remains in Store with the existing UTC/exact-zone validation, safe identifier-only StoreError and suppressed library chain. Do not normalize, repair, skip bad rows or return partial requested lists. Preserve parser-accepted stored UTC forms, date-only/DST flags and work-time conversion; user-input parsing stays separate. Given: three corruption cases, seven time-value cases and all previous stored-time/CLI tests.
7. **Startup/schema/coverage:** keep schema.py, migration SQL/version 3, startup gate/permissions/cleanup, locked version decisions, foreign-key handling, preflight, WAL, timeout and task/audit triggers unchanged. No dependency, setting, network, feature or source capability. _store_tasks.py and store.py must have 100% line and branch coverage with all earlier critical gates retained. Do not edit earlier tests or extracted modules.

8. **Progress entry** for `## Phase 2m: Task table boundary (YYYY-MM-DD)` at the end of `docs/progress.md`.

## Given files

Already committed with this spec; never change them.

| File | What it is |
|---|---|
| `tests/task_boundary_cases.py` | Given four-table SQL recorder and task-write interruption fixture; no test cases |
| `tests/integration/test_task_table_boundary.py` | 26 tests from 7 functions (requirements 1–6) |
| `scripts/critical_modules.txt` | Given critical gate addition for _store_tasks.py |
| `docs/verification/probe-02m.py` | The verifier's probe |

Given test count: **26** (7 functions). Baseline has 13 intended extraction/import failures and 13 preservation guards; names-only modules have six SQL-owner failures and 20 passing shape/behavior guards. The six ownership cases prevent a no-op from passing this refactor.

## Tests to write

Write `tests/integration/test_task_boundary_more.py`:

- Combine title/state/deadline/work changes in one low-level update and verify exact readback and timestamps; combine None clears with unchanged fields. Include a quote-containing title and a filtered lookup for an unknown valid state.
- Inside a valid transaction, unknown well-formed task ID vs malformed ID retain their existing refusal, with helper call counts showing that only the valid integer reaches existence SQL. Outside/non-UTC checks still precede lookup.
- Inject a new table-helper failure before SQL, verify no audit/key/task change and a usable subsequent transaction; keep exception identity and existing error mapping.
- Populate a v2 synthetic database and replace every task helper entry with a forbidden stub while opening/upgrading. Startup/preflight succeeds through the original local migration path; restoring helpers gives the original IDs, rows, audit and keys. Existing startup/process tests remain unchanged.
- Cover all newly extracted read/update branches with deciding assertions, including absent/existing single reads, all/filtered/empty lists and post-write readback. No exclusions or edits to given files.

## Scope

| Path | Change |
|---|---|
| `src/docket/_store_tasks.py` | create |
| `tests/integration/test_task_boundary_more.py` | create |
| `src/docket/store.py` | edit: delegate normal task SQL and SQL assembly; retain conversion, guards, records and setup/migrations |
| `docs/progress.md` | append your entry |

## Out of scope

- Editing _store_audit.py, _store_links.py or _store_keys.py; moving records, sentinels, errors, domain/conversion policy or startup/migrations.
- Generic repositories/ORMs, new connections, query redesign, indexes, schema/version changes, repair, normalization, pruning or historic data rewrites.
- Changing IDs, approval/retry semantics, low-level timestamp policy, settings, dependencies or public core/store/HTTP/CLI/MCP contracts.
- Phase-tooling separation, test consolidation, type-checker installation, reminders or service/calendar/Discord integrations and real accounts.
- Any change to a given file, `AGENTS.md` or the design docs.

## Rules that bite

- **Approval/atomicity:** core remains the only task mutation path in product flows; private SQL helpers cannot decide policy or commit a partial operation.
- **Privacy:** bound values and fixed safe refusals; no request-derived identifier interpolation, output, logging, model or network.
- **Determinism:** no new clock read, ID source or implicit zone. Store encodes values and validates loaded task times before returning public records.
- **Preservation:** one connection and transaction owner, existing startup/migration/preflight, immutable task/audit history and all earlier contracts remain intact. Tests use synthetic temporary databases only.
- **Time through the module**: `clock.now()`, never `datetime.now()`, and never `from docket.clock import now`.
- If you stop before finishing, still write the progress entry with a `Stopped:` first follow-up (`docs/phase-conventions.md`, "When you stop").
- Commands start with `.venv/bin/python`; no bare `python3`, `pytest` or `ruff`.

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_task_table_boundary.py` (before you start) | `1193 passed` |
| `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1219 passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest tests/integration/test_task_table_boundary.py --no-cov -q` | `26 passed` |
| `.venv/bin/python -m coverage report --include=src/docket/_store_tasks.py,src/docket/store.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| `.venv/bin/python docs/verification/probe-02m.py` | last line `FAILURES 0` |
| `grep -c "^## Phase 2m: " docs/progress.md` | `1` |
| `.venv/bin/python scripts/check_reports.py --phase 2m` | `Reports OK.` |
| `git diff HEAD --stat -- tests/task_boundary_cases.py tests/integration/test_task_table_boundary.py scripts/critical_modules.txt docs/verification/probe-02m.py` | no output |
| `git status --short` | only the Scope paths |

### Searches

Each prints nothing.

```zsh
git grep --untracked -n -E 'import (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)|from (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)' -- src
git grep --untracked -n -E 'print\(|logging|logger|warnings\.warn' -- src ':!src/docket/cli.py'
git grep --untracked -n -E 'datetime\.now|datetime\.utcnow|date\.today|time\.time\(|from docket\.(clock|ids) import' -- src ':!src/docket/clock.py'
git grep --untracked -n -E '\.(insert_task|update_task|append_audit|insert_link|insert_request_key)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'
git grep --untracked -n -E 'ollama|anthropic|openai|langchain' -- src
git grep --untracked -n -E 'pragma: no cover|noqa' -- src/docket/_store_tasks.py src/docket/store.py
```
