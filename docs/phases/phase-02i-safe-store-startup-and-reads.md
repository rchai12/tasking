# Phase 2i: Safe store startup and reads

## Goal

Make simultaneous store startup safe, release all initialization resources on failure, and refuse invalid task times before they reach rendering or comparisons. Add the owner's private startup gate, recheck schema versions under SQLite write transactions, and give task-read failures the same plain CLI refusal path as startup failures. This addresses the remaining startup work from audit finding 3 and the task-time part of finding 9; it adds no migration, task field or service.

Sections: `core`. The `tooling` section runs in the full check.

Follow `docs/phase-conventions.md`. N is 960, the tests the previous phase left passing.

Start: `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_stored_task_times.py --ignore=tests/integration/test_store_startup.py --ignore=tests/integration/test_store_coordination.py --ignore=tests/e2e/test_stored_time_refusals.py` must show `960 passed`. The ignored files specify this phase's changed startup and read behaviour; they use existing public names.

## Facts

Checked on 2026-11-17 against baseline `c309332`:

- Phase 2h passed with 960 tests, no findings and no deviations. Store initialization reads `user_version` before acquiring a write transaction, then applies migrations using that saved value. The reference rebuild closes its failed connection, but earlier setup failures do not.
- A synthetic SQLite check reproduced WAL-transition contention: 4 of 20 pairs opening a DELETE-mode database concurrently got a locked error; already-WAL pairs did not in that check. Serializing only migration SQL would leave this race.
- A local standard-library `fcntl.flock` check confirmed distinct handles in one process contend, and unlocking releases the gate. The owner's choice therefore covers threads and independent processes without a new package. The given process tests use spawn, temporary databases and pipes/queues, with no service or network connection.
- `Deadline` and `WorkTime` already validate UTC identity and exact zone names. `_task_from` lets their `DeadlineError` escape and lets `datetime.fromisoformat` errors escape; task `created_at`/`updated_at` are parsed without UTC checks. CLI's `_store` currently catches only opening failures, not StoreError raised while using the store.
- Standard-library zoneinfo confirmed the literal fall-back and spring-forward instants in the given round-trip cases. No time rule changes.
- Separate temporary patches validated 55 task-read/CLI cases, nine startup-gate cases, eight failure-cleanup cases, and the later-transaction version recheck. Each probe component passed against its corresponding small patch. They were discarded separately; no combined phase implementation was built. Process-race cases can vary on baseline, so failing-first evidence includes deterministic missing-gate, unlocked-version, cleanup and time-refusal cases.

## Owner's decisions

Decided 2026-11-17:

- **Private startup lock file:** serialize initialization across processes with a standard-library file lock and wait until the initializer finishes. SQLite retains its existing five-second busy timeout. The SQLite-only retry alternative was not chosen.
- Earlier decisions remain: UTC instants plus exact IANA zones, refuse invalid data instead of rewriting it, fixed error text plus identifiers, and plain CLI refusals on stderr with exit 1.

## Architect's decisions

- Derive the gate from the supplied database path: `path.with_name(path.name + ".startup.lock")`. Keep it empty and mode 0600. Acquire an exclusive blocking `fcntl.flock` before opening SQLite, hold it through initialization and any failed-constructor cleanup, then unlock and close its descriptor. Keep the file; never unlink it or treat its age/content as a stale-lock indicator. OS locks release on process exit.
- A gate creation/permission/acquisition OSError becomes `StoreError("store startup unavailable")`, without a library-error chain. SQLite is not opened when acquiring the gate fails. Other initialization failures preserve their original exception after cleanup, without logging it.
- The gate coordinates initialization only. Keep SQLite write transactions authoritative for version decisions and migration application, with a fresh version read for each migration transaction. Do not combine all migrations into one transaction or relax foreign-key enforcement outside migration 3.
- Validate only the task timestamps and zones covered by this phase: deadline instant/zone, work start/zone, created_at and updated_at. Use the existing ISO parser and UTC/zone semantics; do not invent a stricter serialization grammar or normalize non-UTC values.
- A corrupt task read raises exactly `StoreError("invalid stored task time: <task id>")` with no library-error cause/context shown. It changes no stored value and never skips a bad requested row. Do not expose the offending value or add an error code per field.
- Extend the private CLI store context guard to catch StoreError raised during use as well as opening. Existing command, message and clock policies remain unchanged; no core or API change is needed.

## Requirements

1. **Startup gate:** implement the private gate described above for every `Store(path)` initialization, including current-schema databases and failures. The exclusive lock is held before `sqlite3.connect` and released after initialization, not for the lifetime of a live Store. Successful or failed initialization closes its gate descriptor. The same persistent inode is reused, with no PID, token, path text or timestamp written into it. No configuration setting, polling, retry loop or extra startup timeout. Given: `test_startup_gate_is_private_held_before_connect_and_persistent`, `test_gate_acquisition_error_is_constant_and_closes_the_descriptor`, `test_failed_constructor_releases_the_gate`, `test_process_exit_releases_a_gate_without_deleting_it`.
2. **Concurrent startup and fresh version decisions:** two independent openers of an empty, v1, populated v2 or current database both complete successfully with the current schema applied once. Every schema-version decision is read under `BEGIN IMMEDIATE`; re-read the current version before applying each migration's SQL and advance it in that same transaction. A version greater than 3 is refused with the existing `unsupported schema version: <version>` message and is never overwritten. The gate also serializes WAL setup. Preserve per-migration commit/rollback boundaries. Given: `test_two_processes_initialize_the_same_database_once`, `test_schema_version_decisions_are_under_an_immediate_transaction`, `test_a_later_transaction_rechecks_the_version_before_applying_sql`, existing version tests.
3. **Failed initialization cleanup:** after a connection has been created, every failure through row-factory setup, permissions, PRAGMAs, version checking and migrations closes that connection exactly once and re-raises the original failure. A failed connect does not close an uncreated connection. Refactor the existing migration-3 cleanup so adding the general guard does not cause a second close. Always release the startup gate, and retain migration rollback and foreign-key restoration before closing. Given: `test_each_failed_initialization_closes_the_connection_once`, `test_connect_failure_does_not_attempt_to_close_an_uncreated_connection`, `test_newer_schema_refusal_closes_once`, existing reference-migration failure tests.
4. **Storage invariants:** keep mode 0600, WAL, busy_timeout 5000, connection thread checks, normal foreign_keys ON, unchanged migration SQL and schema version 3. Migration 3 alone may temporarily turn off foreign keys, before its own rebuild transaction; restore them on all exits. Valid old data, IDs, pruned-link sequences, retry JSON and immutable audit history survive unchanged. No task or migration is applied twice. Given: `test_migration_foreign_keys_remain_scoped_to_the_reference_rebuild`, populated process case, existing migration/store tests.
5. **Validate task reads:** each task returned through `task`, `tasks` or their internal read path has valid UTC deadline/work instants, exact zones and UTC created_at/updated_at. Map expected ISO parsing and time/zone validation failures to the fixed task-ID StoreError above, suppressing library exception chains. Preserve unknown-task None, valid absent deadline/work, date-only flags and existing parser-accepted UTC forms. Do not scan unrelated rows at startup, rewrite corrupt values, normalize offsets or return a partial list. Given: `test_invalid_task_times_refuse_at_the_store_boundary`, `test_valid_task_times_round_trip_without_changing_instants`, `test_no_partial_task_list_or_repair_is_returned`.
6. **Thin CLI refusal path:** catch StoreError from opening and using the private store context and print only its safe text to stderr, exiting 1. `tasks list` with a later corrupt row prints no partial task list; `tasks show` prints no title or bad timestamp. Keep all successful commands, existing refusals and clock reads unchanged. Limit CLI edits to the private context guard and its imports/type hints. Given: `test_cli_reports_only_the_task_id_for_corrupt_stored_time` and the existing CLI suite.
7. **Scope and coverage:** public names/signatures, task states, core logic, title/reference policy, API responses, configuration and dependencies remain unchanged. Cover every line and branch of store.py and cli.py, and retain all existing critical gates. No earlier test or given file is edited.

8. **Progress entry** for `## Phase 2i: Safe store startup and reads (YYYY-MM-DD)` at the end of `docs/progress.md`.

## Given files

Already committed with this spec; never change them.

| File | What it is |
|---|---|
| `tests/startup_cases.py` | Synthetic old databases and spawn-safe process entry points; no test cases |
| `tests/integration/test_stored_task_times.py` | 53 tests from 3 functions (requirement 5) |
| `tests/integration/test_store_startup.py` | 10 tests from 3 functions (requirement 3) |
| `tests/integration/test_store_coordination.py` | 11 tests from 8 functions (requirements 1–4) |
| `tests/e2e/test_stored_time_refusals.py` | 2 cases in one parametrized test function (requirement 6) |
| `docs/verification/probe-02i.py` | The verifier's probe |

Given test count: **76** (15 functions). Nine fixed guards pass on baseline; the three process-race cases may also pass depending on scheduling. All 76 fail or error on a names-only Store constructor stub (27 failures and 49 fixture errors in the planning run).

## Tests to write

Write `tests/integration/test_store_safety_coverage.py` for remaining behaviour:

- Correct an existing startup gate's permissions to 0600 without replacing its inode; keep it empty.
- A failure while opening or setting permissions on the gate gives the constant startup refusal and closes any acquired descriptor before SQLite is opened.
- Initialization failures and library-error messages containing synthetic private markers produce no application output or logs; do not report those messages through a new StoreError.
- Confirm a filtered task query that excludes a corrupt row returns its normal result, with no global scan or repair. Existing UTC ISO forms such as a Z suffix still read as UTC.
- Exercise any remaining startup, rollback or task-read validation branch with a deciding assertion, without exclusions or changes to given files.

## Scope

| Path | Change |
|---|---|
| `tests/integration/test_store_safety_coverage.py` | create |
| `src/docket/store.py` | edit: private startup gate, fresh locked version reads, centralized failed-init cleanup and task-time validation |
| `src/docket/cli.py` | edit: private store context guard and imports/type hints only |
| `docs/progress.md` | append your entry |

## Out of scope

- New migrations, schema/version changes, repair commands, automatic data correction, stale-lock deletion, new settings or dependencies.
- Auditing every table's timestamp fields: this phase validates task times only; it does not decode or rewrite audit snapshots or retry JSON.
- New work/deadline consistency policies or reinterpreting time zones, offsets and date-only semantics.
- Creation/JSON deduplication, domain-list centralization, table-module extraction, tooling redesign, reminders, API/MCP changes or new service integrations (later phases).
- Reading real databases, accounts, Keychain entries or calendars.
- Any change to a given file, `AGENTS.md` or the design docs.

## Rules that bite

- **Retry safety:** serialization must prevent duplicate migrations while preserving existing task/link IDs, sequences and retry records.
- **Privacy:** only fixed StoreError text plus task/schema identifiers; no library-error chain, corrupt value, title, token or path in a new refusal.
- **No automatic edits:** invalid task data is refused on read, never repaired or hidden; migration preflight retains its existing refusal policy.
- **Resources:** keep the empty gate file, release its descriptor/OS lock, and close a failed SQLite connection once. Existing live stores still coordinate writes through SQLite.
- **Synthetic data and clocks:** temporary fixtures and local processes only. Startup/read code adds no clock read; test watchdogs are failure bounds, not application time policy.
- **Time through the module**: `clock.now()`, never `datetime.now()`, and never `from docket.clock import now`.
- If you stop before finishing, still write the progress entry with a `Stopped:` first follow-up (`docs/phase-conventions.md`, "When you stop").
- Commands start with `.venv/bin/python`; no bare `python3`, `pytest` or `ruff`.

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_stored_task_times.py --ignore=tests/integration/test_store_startup.py --ignore=tests/integration/test_store_coordination.py --ignore=tests/e2e/test_stored_time_refusals.py` (before you start) | `960 passed` |
| `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1036 passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest tests/integration/test_stored_task_times.py tests/integration/test_store_startup.py tests/integration/test_store_coordination.py tests/e2e/test_stored_time_refusals.py --no-cov -q` | `76 passed` |
| `.venv/bin/python -m coverage report --include=src/docket/store.py,src/docket/cli.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| `.venv/bin/python docs/verification/probe-02i.py` | last line `FAILURES 0` |
| `grep -c "^## Phase 2i: " docs/progress.md` | `1` |
| `.venv/bin/python scripts/check_reports.py --phase 2i` | `Reports OK.` |
| `git diff HEAD --stat -- tests/startup_cases.py tests/integration/test_stored_task_times.py tests/integration/test_store_startup.py tests/integration/test_store_coordination.py tests/e2e/test_stored_time_refusals.py docs/verification/probe-02i.py` | no output |
| `git status --short` | only the Scope paths |

### Searches

Each prints nothing.

```zsh
git grep --untracked -n -E 'import (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)|from (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)' -- src
git grep --untracked -n -E 'print\(|logging|logger|warnings\.warn' -- src ':!src/docket/cli.py'
git grep --untracked -n -E 'datetime\.now|datetime\.utcnow|date\.today|time\.time\(|from docket\.(clock|ids) import' -- src ':!src/docket/clock.py'
git grep --untracked -n -E '\.(insert_task|update_task|append_audit|insert_link|insert_request_key)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'
git grep --untracked -n -E 'ollama|anthropic|openai|langchain' -- src
git grep --untracked -n -E 'pragma: no cover|noqa' -- src/docket/store.py src/docket/cli.py
```
