# Phase 3b: Durable reminder plans

## Goal

Persist the verified Phase 3a plans and keep them atomic with approved task creation and lifecycle changes. Upgrade existing active tasks once from their stored snapshots, keep reminder history, and preserve existing approval/retry/CLI/HTTP contracts. This is the durable foundation of the reminder engine, with no sender, poll loop or live integration. Claims, delivery keys, fake sending, catch-up coalescing and the digest remain subsequent Stage 3 work.

Sections: `core`. The `tooling` section runs in the full check.

Follow `docs/phase-conventions.md`. N is 1382, the tests the previous phase left passing.

Start: `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_durable_reminders.py --ignore=tests/integration/test_reminder_store_contracts.py --ignore=tests/unit/test_feature_preservation.py` must show `1382 passed`. The ignored files import names you create.

## Facts

Checked 2026-11-18 against independently verified d927fd9:

- Phase 3a is PASS at 1,382 tests, no findings/deviations. Its planner already returns the exact finite UTC schedule, including past slots, with no clock/ID reads. Task and PlannedReminder remain unchanged.
- Existing core reads the clock once per accepted operation at its established position. Both creation paths share _insert_open_task; keyed replays bypass it. change_state and edit_task already own a Store transaction containing the task/audit writes. Adding reminder writes inside those transactions does not require another clock read or nested transaction.
- Store startup is serialized by the existing private flock and rechecks versions under BEGIN IMMEDIATE. _apply_migration runs inside that transaction; version 3 is the insertion point for the new migration/backfill. Migration 3's foreign-key-off reference rebuild remains untouched. A discarded SQL-only spike confirmed that given migration DDL plus an inserted reminder roll back to version 3 and the original rows when a later SQL statement fails.
- Legacy table-specific helpers are deliberately forbidden during parts of startup by earlier tests. Backfill therefore reads tasks through startup-local SQL and _task_from, then uses a new reminder insertion helper on the same connection. It must not call Store.tasks or _require_task during backfill. Normal reminder SQL belongs to the new private _store_reminders module.
- The given schema is append-only migration 4. Existing successful-current-version pins become 4; failed reference-upgrade pins remain 2, migration 3's internal version remains 3, and newer-than-supported pins remain 99. The current startup parameter keeps its node ID while its value changes to 4. Existing case IDs, assertion semantics and prior migration strings remain intact. test_store_safety_coverage.py::test_reference_rebuild_rechecks_the_version_before_its_sql[3] keeps its node ID: a version 3 planted by another opener now skips the rebuild and upgrades to 4, and its final assertion expects (4,) for that case and (99,) for the unsupported one.
- docket.reminders imports Task from docket.store at module level, so store.py cannot import docket.reminders at module level (the import fails on a partly initialized module). The backfill imports it inside the function that calls plan_reminders, as `from docket import reminders`; PlannedReminder hints use TYPE_CHECKING. Ruff's selected rules allow a function-local import.
- Earlier whole-file freezes cannot forbid the feature edits they precede. Only core/store source entries become structural contracts: 38 core and 86 store baseline nodes remain exact; the bodies of core.change_state, edit_task, _insert_open_task and Store._apply_migration may change, with their signatures and old import atoms preserved. New helpers/record/methods may be added. Every other frozen file still uses exact byte hashes. Given reader changes retain the same assertions through tests.preservation_cases; synthetic mutation checks exercise stable bodies, signatures, imports and byte changes.
- The given suite has 83 cases from 22 functions: 60 intended baseline failures and 23 schema/preservation guards. Names-only methods fail the corresponding behavioural contracts; no complete core/store implementation is built. A targeted historical run passed 205 cases after the version/guard migration. No real database, account, Keychain or service is inspected.

## Owner's decisions

Decided 2026-11-18: backfill existing open and in_progress tasks during the upgrade, using each stored last-approved snapshot and updated_at. Preserve past slots for the later single-status catch-up sender. No notification is sent during upgrade. Planning only future task changes was not chosen.

The approved ID rule remains: SQLite-assigned, never-reused internal row IDs (reminders r1, r2, onward); generated outbound retry keys persisted once and reused. This phase allocates row IDs only and never calls ids.new_id(). Sending and its keys are not implemented here.

## Architect's decisions

**Schema and history.** The committed MIGRATION_4 creates the STRICT reminders table with number, task FK, kind, fire_at, planned_at, nullable claimed_at/sent_at/voided_at; task/number and pending-time indexes; positive row numbers; the five decided kinds; and triggers refusing deletion or changes to number/task/kind/fire_at/planned_at. Claimed/sent fields are reserved metadata needed to distinguish pending from already-sent rows, not a claim/send implementation. No title, payload, key or calendar data is stored. Never edit migrations 1–3.

**Kind ownership.** The given domain.REMINDER_KINDS tuple is (start, before, due_soon, due, late), matching the existing PlannedReminder type. Store validation uses this shared tuple, not a copied runtime list. The schema retains its given matching CHECK.

**Store public additions.** Add a frozen Reminder record with fields in this order: id: str, task_id: str, kind: str, fire_at: datetime, planned_at: datetime, claimed_at: datetime | None, sent_at: datetime | None, voided_at: datetime | None. Public hints may use postponed annotations and TYPE_CHECKING for PlannedReminder to avoid the store/planner import cycle.

- Store.insert_reminders(task_id: str, plans: tuple[PlannedReminder, ...], *, at: datetime) -> list[Reminder]. Require the existing write/UTC guard first, then an existing task; validate every kind and fire_at before inserting any row. Kinds must be strings in domain.REMINDER_KINDS, otherwise StoreError("invalid reminder kind"). Noncanonical fire_at uses the existing StoreError("an instant must be in UTC"). Preserve input order and canonical microsecond timestamp encoding; at is planned_at. Return only newly inserted rows, including [] for an empty plan. Each new row has r<number> and null claimed/sent/void times. No hidden transaction, deduplication or clock/ID read.
- Store.void_reminders(task_id: str, *, at: datetime, kinds: Collection[str] | None = None) -> None. Same write/UTC/task order; validate all supplied kinds before any reminder UPDATE. None means all five; an empty collection changes nothing. Set voided_at only where sent_at and voided_at are both NULL, optionally restricted to kinds. Claimed but unsent rows are still pending. Never overwrite an earlier void timestamp or modify sent rows; retries are harmless.
- Store.reminders(task_id: str) -> list[Reminder]. Return all historical rows ordered by number, with no write/clock read. Malformed/unknown task IDs return []. All present timestamps must parse to canonical UTC; refuse malformed/naive/non-UTC values with StoreError("invalid stored reminder time: r<number>"), no chained library text, no normalization or partial result. Existing unknown-task/write errors and Task records are unchanged.

**Private SQL boundary.** _store_reminders imports no product modules and uses only its supplied connection; it owns ordinary INSERT/SELECT/UPDATE for reminders, with bound values and fixed identifiers. It neither opens/closes connections, manages transactions/configuration, reads time/IDs nor encodes/decodes records. Provide insert_reminder(connection: sqlite3.Connection, task: int, kind: str, fire_at: str, planned_at: str) -> sqlite3.Cursor; select_reminders(connection: sqlite3.Connection, task: int) -> list[sqlite3.Row] with all eight columns ordered by number; void_reminders(connection: sqlite3.Connection, task: int, at: str, kinds: tuple[str, ...]) -> None. The last receives a nonempty validated tuple; build only placeholder SQL for its IN list. Store owns validation, encoding, IDs and row conversion. New helpers remain private.

**Core integration.** Only actual changes schedule or void. _insert_open_task obtains the complete plan at its existing at and persists it inside the caller's transaction, covering owner/agent/email/proposal and keyed creation. A keyed replay leaves rows/IDs/timestamps untouched. Done/Cancel void all pending kinds; Reopen creates a complete fresh plan at the existing operation instant, retaining old history. Start/in_progress changes do not replan. edit_task compares actual changed fields: a deadline change voids/replaces only before/due_soon/due/late; a work change only start; both change both groups, with no duplicates. Clearing a field voids that group and inserts no replacement for it. Title-only, no-op, same-value edits and follow-up links leave reminders exact. Do not recompute plans on read, replay or restart. All task, audit, request-key and reminder effects share one transaction.

**Upgrade/backfill.** While applying migration 4, after its DDL but before committing version 4, read active tasks using domain.OPEN_STATES bound to startup-local SQL, ordered by number. Decode using existing _task_from; call reminders.plan_reminders(task, task.updated_at) through the module and insert on the same connection, planned_at=updated_at. Share a private validated row writer with the normal facade without ordinary task-helper lookups. Inactive/undated plans may be empty. No clock/settings/IDs/network/extra connection, task update or new audit row. At version 4, reopen does not backfill again. Two independent upgraders must produce one copy of every plan. Foreign keys stay on for migration 4 and all backfill work; the existing reference rebuild exception stays scoped to version 2.

**Overflow and refusal.** New core constant INVALID_REMINDER_PLAN = "invalid_reminder_plan". Convert only planner OverflowError to CoreError(INVALID_REMINDER_PLAN), from None, inside the transaction; propagate unrelated failures so rollback remains visible. The given views mapping renders it as "That time cannot be scheduled for reminders." Existing intake maps the core code to 422 with {"error":"invalid_reminder_plan"}; no route/CLI decision change is needed. During backfill, an unrepresentable active task plan raises StoreError("invalid reminder plan: t<number>"), from None. Invalid stored task times retain their existing safe StoreError. Any backfill failure rolls back the table, rows and version to 3, closes the connection and releases the startup gate. Never repair stored data or silently omit a task.

**Given guard migration.** Byte pins are retained for unrelated files. The two changed source entries use stable_nodes, mutable_signatures and imports, with the exact baseline nodes/signatures/import atoms captured above; new helper definitions are permitted but existing import meaning cannot be removed. The four dependent manifests, two older readers and the one frozen-loop test receive literal planning-time changes, including version-only test hashes and the earlier server AST/moved-file pins. product_organization.manifest.after_sha256 follows the newly committed Phase 2p manifest, while before_sha256 remains historical. All case maps, seeds, public-state rules, selector/document contracts, counts and unrelated hashes remain exact. These given edits are not permission for the coder to refresh guards from its implementation.

## Requirements

1. **Durable rows and Store API:** implement the exact Reminder record and three Store methods above on the existing connection/transaction. Validate whole batches before reminder mutations, retain history and pending-only void semantics, use SQLite row IDs and preserve all UTC/refusal contracts. Given: low-level round-trip, ten guard cases, fifteen corrupt-time cases and thirteen schema/trigger guards.
2. **SQL ownership:** create _store_reminders with the exact supplied-connection functions; keep normal reminder SQL there, validation/conversion in Store and startup orchestration unchanged. No connection/transaction/model/time/config policy in SQL helpers. Given: observed callers/transaction ownership and one connection plus AST checks.
3. **Approved creation and keyed replay:** integrate the shared creation helper inside its existing transaction. Cover all existing approved sources, keyed retries and no outbound ID generation. Unknown/invalid/unapproved inputs retain their old refusal order and no writes. Given: five creation paths, old approval/refusal cases, literal nine-row plan and fresh-store restart.
4. **Atomic lifecycle and selective replanning:** implement exact Done/Cancel/Reopen and deadline/work rules above; preserve sent rows, old void instants and unrelated groups. No task-state change from time passing. Given: end/repeat/reopen, five edit cases, five unchanged/unrelated cases and five post-reminder-SQL interruptions with full table/sequence snapshots. Coder writes combined replacement and ended-overflow edges below.
5. **Populated upgrade:** apply migration 4 and backfill as one startup write transaction under the existing lock/version recheck. Preserve old tables/audits/IDs, use updated_at rather than creation/wall time, retain past slots and never duplicate on reopen or concurrent upgrade. Given: populated/last-approved/past-plan cases, two spawned upgraders and a later overflowing task after earlier valid work. Coder writes constructor cleanup/injected SQL edges below.
6. **Safe range failures and UTC persistence:** provide the constant refusals and mapping above with transaction rollback and no library/title/body text. Persist both verified DST plans without moving instants. Given: three core overflow cases, HTTP/CLI refusal test, fifteen stored-time refusals and two DST round trips.
7. **Preserve boundaries and coverage:** no change to Task, Phase 3a planner, existing create/state/edit signatures, ordinary four-table SQL helpers, approval policy, clock counts, fake-service guards or section/dependency configuration. The new SQL module joins the product 100% line/branch gate; retain the independent tooling 100% and overall 90% gates. Given: current schema/version-only edits, structural/byte guard tests, full checker and immutable planning artifacts.
8. **No sending:** implement no claim acquisition, lease release, sender, key allocation, poll/service command, catch-up message, digest, snooze, Discord or calendar connection. Persisted historical slots are input to the later sender; they are not sent individually here. A real double-loop/same-key delivery proof belongs to that sender phase; this phase proves durable restart and repeated/concurrent plan safety without pretending a send occurred.

9. **Progress entry** for `## Phase 3b: Durable reminder plans (YYYY-MM-DD)` at the end of `docs/progress.md`.

## Given files

Already committed with this spec; never change them.

| File | What it is |
|---|---|
| `tests/reminder_storage_cases.py` | Synthetic v3 inputs, literal plan projections, snapshot and spawned opener |
| `tests/preservation_cases.py` | Given byte or named-AST/signature/import preservation reader |
| `tests/integration/test_durable_reminders.py` | 33 tests from 12 functions: durable/core/upgrade/adapter/DST cases |
| `tests/integration/test_reminder_store_contracts.py` | 41 tests from 7 functions: facade/SQL/record/refusal/schema cases |
| `tests/unit/test_feature_preservation.py` | 9 tests from 3 functions: scoped structural and exact-byte guard contracts |
| `docs/verification/probe-02g.py` | Earlier given: current-version assertion/helper changes only; preserve historical-failure pins and node IDs |
| `docs/verification/probe-02i.py` | Earlier given: current-version assertion/helper changes only; preserve historical-failure pins and node IDs |
| `scripts/critical_modules.txt` | Given append of _store_reminders.py |
| `src/docket/schema.py` | Given append-only migration 4; migrations 1–3 byte-identical |
| `src/docket/views.py` | Given single invalid_reminder_plan refusal mapping |
| `src/docket/domain.py` | Given REMINDER_KINDS tuple; all earlier policy remains exact |
| `tests/integration/test_audit_link_key_contracts.py` | Earlier given: current-version assertion/helper changes only; preserve historical-failure pins and node IDs |
| `tests/integration/test_reference_coverage.py` | Earlier given: current-version assertion/helper changes only; preserve historical-failure pins and node IDs |
| `tests/integration/test_reference_migration.py` | Earlier given: current-version assertion/helper changes only; preserve historical-failure pins and node IDs |
| `tests/integration/test_server.py` | Earlier given: current-version assertion/helper changes only; preserve historical-failure pins and node IDs |
| `tests/integration/test_store.py` | Earlier given: current-version assertion/helper changes only; preserve historical-failure pins and node IDs |
| `tests/integration/test_store_coordination.py` | Earlier given: current-version assertion/helper changes only; preserve historical-failure pins and node IDs |
| `tests/integration/test_store_links.py` | Earlier given: current-version assertion/helper changes only; preserve historical-failure pins and node IDs |
| `tests/integration/test_store_safety_coverage.py` | Earlier given: one final-version assertion for the planted-version-3 case; node IDs preserved |
| `tests/product_consolidation_cases.py` | Given frozen-loop delegation to the shared preservation reader only |
| `tests/product_consolidation_manifest.json` | Given exact version/registry/dependent-hash and scoped source-freeze migration; no case loss |
| `tests/product_organization_cases.py` | Given frozen-loop delegation to the shared preservation reader only |
| `tests/product_organization_manifest.json` | Given exact version/registry/dependent-hash and scoped source-freeze migration; no case loss |
| `tests/product_support_manifest.json` | Given exact version/registry/dependent-hash and scoped source-freeze migration; no case loss |
| `tests/startup_cases.py` | Earlier given: current-version assertion/helper changes only; preserve historical-failure pins and node IDs |
| `tests/tooling_boundary_manifest.json` | Given exact version/registry/dependent-hash and scoped source-freeze migration; no case loss |
| `tests/unit/test_product_test_support.py` | Given frozen-loop delegation to the shared preservation reader only |
| `docs/verification/probe-03b.py` | The verifier's probe |

Given test count: **83** (22 functions): durable_reminders 33 cases/12 functions, reminder_store_contracts 41 cases/7 functions, feature_preservation 9 cases/3 functions. Confirm the exact collected counts below; baseline has 60 intended failures and 23 schema/guard passes.

## Tests to write

Write tests/integration/test_reminder_storage_edges.py with synthetic inputs and literal outcomes:

- A combined nonempty deadline/work replacement produces exactly ten fresh rows, with both old groups voided and unchanged audit semantics; a work-only task persists/ends/reopens its one start row.
- Reopening an ended legacy task with a representable deadline but overflowing reminder offsets safely refuses and leaves it ended; terminal tasks were not backfilled during upgrade.
- A malformed legacy active task time uses the existing safe task-time error and leaves version 3/data unchanged. No-active and empty-plan legacy upgrades still reach version 4 without clock/ID reads.
- Inject a reminder SQL failure after at least one legacy task was inserted: all DDL/backfill/version changes roll back, the failed constructor closes its connection once, and another independent opener can acquire the existing startup lock. Use events/IPC, not elapsed-time assertions or sleeps.
- Exercise exact canonical UTC on public writer arguments, including ZoneInfo("UTC") refusal, non-string kind refusals, and any legitimate missing line/branch of the three new SQL helpers or Store methods. Keep normal SQL ownership and one transaction/connection.

Use this behaviour filename, not another generic continuation. Do not repair a given test or widen a source freeze to obtain a pass.

## Scope

| Path | Change |
|---|---|
| `src/docket/_store_reminders.py` | create |
| `tests/integration/test_reminder_storage_edges.py` | create |
| `src/docket/core.py` | edit: only this phase’s reminder integration, preserving pinned nodes/signatures/import meaning |
| `src/docket/store.py` | edit: only this phase’s reminder integration, preserving pinned nodes/signatures/import meaning |
| `docs/progress.md` | append your entry |

## Out of scope

- Sender/claim/lease logic or retry-key generation; live/fake notifier APIs; polling/service commands; catch-up/digest/snooze/proposals; calendar/Discord work; a new repository framework; further test cleanup; dependencies/type checking; repairs to a real database; changes to shipped migration strings or unrelated core/store methods.
- Any change to a given file, `AGENTS.md` or the design docs.

## Rules that bite

- Only approved core paths change tasks; startup backfills reminder rows without changing any task. All reminder writes and audit/task changes share one transaction, all new internal IDs are SQLite numbers, all instants are canonical UTC and the existing operation clock is reused. Synthetic inputs only; no real data, accounts, Keychain, services or network. Errors are fixed codes/text plus task/reminder IDs, never exception/title/body text.
- **Time through the module**: `clock.now()`, never `datetime.now()`, and never `from docket.clock import now`.
- If you stop before finishing, still write the progress entry with a `Stopped:` first follow-up (`docs/phase-conventions.md`, "When you stop").
- Commands start with `.venv/bin/python`; no bare `python3`, `pytest` or `ruff`.

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_durable_reminders.py --ignore=tests/integration/test_reminder_store_contracts.py --ignore=tests/unit/test_feature_preservation.py` (before you start) | `1382 passed` |
| `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1465 passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest tests/integration/test_durable_reminders.py tests/integration/test_reminder_store_contracts.py tests/unit/test_feature_preservation.py --no-cov -q` | `83 passed` |
| `.venv/bin/python -m coverage report --include=src/docket/_store_reminders.py,src/docket/core.py,src/docket/store.py,src/docket/reminders.py,src/docket/schema.py,docket_tools/reports.py,docket_tools/acceptance.py,docket_tools/spotcheck.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| `.venv/bin/python docs/verification/probe-03b.py` | last line `FAILURES 0` |
| `grep -c "^## Phase 3b: " docs/progress.md` | `1` |
| `.venv/bin/python scripts/check_reports.py --phase 3b` | `Reports OK.` |
| `git diff HEAD --stat -- tests/reminder_storage_cases.py tests/preservation_cases.py tests/integration/test_durable_reminders.py tests/integration/test_reminder_store_contracts.py tests/unit/test_feature_preservation.py docs/verification/probe-02g.py docs/verification/probe-02i.py scripts/critical_modules.txt src/docket/schema.py src/docket/views.py tests/integration/test_audit_link_key_contracts.py tests/integration/test_reference_coverage.py tests/integration/test_reference_migration.py tests/integration/test_server.py tests/integration/test_store.py tests/integration/test_store_coordination.py tests/integration/test_store_links.py tests/integration/test_store_safety_coverage.py tests/product_consolidation_cases.py tests/product_consolidation_manifest.json tests/product_organization_cases.py tests/product_organization_manifest.json tests/product_support_manifest.json tests/startup_cases.py tests/tooling_boundary_manifest.json tests/unit/test_product_test_support.py src/docket/domain.py docs/verification/probe-03b.py` | no output |
| `git status --short` | only the Scope paths |

### Searches

Each prints nothing.

```zsh
git grep --untracked -n -E 'import (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)|from (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)' -- src
git grep --untracked -n -E 'print\(|logging|logger|warnings\.warn' -- src ':!src/docket/cli.py'
git grep --untracked -n -E 'datetime\.now|datetime\.utcnow|date\.today|time\.time\(|from docket\.(clock|ids) import' -- src ':!src/docket/clock.py'
git grep --untracked -n -E '\.(insert_task|update_task|append_audit|insert_link|insert_request_key)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'
git grep --untracked -n -E 'ollama|anthropic|openai|langchain' -- src
git grep --untracked -n -E 'pragma: no cover|noqa' -- src/docket/_store_reminders.py src/docket/core.py src/docket/store.py
git grep --untracked -n -E 'ids\.new_id\(' -- src/docket/core.py src/docket/store.py src/docket/_store_reminders.py
git grep --untracked -n -E '\.(insert_reminders|void_reminders)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'
```
