# Phase 5f: Visible loop status

## Goal

Make the reminder loop's failures visible (the rest of audit finding 4). Today `run_loop` throws each `PassResult` away, and the product has no logging, so a half that fails every 30 seconds leaves no trace anywhere. After this phase `run_loop` records each pass in a one-row `loop_status` table: when it ran, what it sent, which tasks it skipped, and each half's count of consecutive failing passes, carried on across restarts. `docket status`, run in another process, prints that row and says when the loop has stopped running. The service itself (`docket run`, launchd, alerts) is Phase 5g.

Sections: `core`. The `tooling` section runs in the full check.

Follow `docs/phase-conventions.md`. N is 1946, the tests the previous phase left passing.

Start: `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_loop_status.py --ignore=tests/e2e/test_cli_status.py` must show `1946 passed`. The ignored files are this phase's new given test files.

## Facts

- `reminders.run_loop(store, notifier, *, zone, at, stop) -> int` (line 160) calls `run_pass` and discards its answer. `run_pass` returns `PassResult(sent, digest, failed, skipped)`; `failed` holds `"reminders"` and/or `"digest"` for a half that raised, and `skipped` the tasks whose rows raised `StoreError` (Phase 5e).
- A bare pass reads `clock.now()` twice (once per half). `tests/integration/test_reminder_loop.py::test_the_loop_waits_thirty_seconds_after_each_pass_until_stopped` pinned 6 reads for 3 loop passes; the given edit removes that pin, and the new file pins the loop's reads.
- `Store.transaction` refuses to nest. Writes check `_require_write(at)`: `StoreError("a write needs a transaction")` outside one, `StoreError("an instant must be in UTC")` for a time that is not UTC. Instants are stored with `_instant` (`isoformat(timespec="microseconds")`).
- Each table's SQL lives in its own `_store_*.py` module; `Store` keeps the records, checks and encoding. `scripts/critical_modules.txt` lists every store module.
- `tests/integration/test_shared_creation.py` refuses `json.dumps` in `core` and `store`: `serialization.canonical_json(value: dict[str, object]) -> str` is the one JSON writer, compact and key-sorted.
- `views.when(at, zone, now)` writes an instant as `Fri Nov 20 11:00 EST`, adding the year only when it differs from `now`'s.
- The CLI reads settings through `_home()` (settings and home zone) and opens the store through `_store(settings)`, which prints a `StoreError`'s text to stderr and exits 1. There is no `docket status` today.
- Migration 7 (given) moved every current schema-version pin from 6 to 7 in ten earlier test files, and added one `(6, 1)` entry to the foreign-key observation in `test_store_coordination.py`. Historical pins stay (2, 3, 99), as does `tests/startup_cases.py`'s `version == 6` label for a current store. Probes are frozen with their phase and not rerun.
- A throwaway draft added 151 lines and deleted 5 (a 22-line `_store_loop.py`; `store` 64, `reminders` 28 and 2, `views` 23 and 2, `cli` 11, `domain`, `serialization` and `critical_modules.txt` 1 each). With it, the full suite passed (1994) and every `docket` module was covered at 100% with branches.

## Owner's decisions

- **Status store (2026-11-22):** a one-row `loop_status` table written by `run_loop`, in one migration.
- **A skipped task counts (2026-11-22):** a pass that skips any task is a failing pass for the reminders half, and the skipped ids are recorded.
- **`docket status` (2026-11-22):** 5f adds a small `docket status` that prints the loop row; 5g extends it.
- **Restarts (2026-11-22):** each half's count carries on from the stored row when `run_loop` starts again, so a crash-and-restart cycle cannot hide a lasting failure.
- **Stale loop (2026-11-22):** `docket status` says the loop is not running when its last pass is more than 5 minutes old.

## Architect's decisions

- **The row holds the counts, not `failed`.** A half failed in the last pass exactly when its count is above 0; the row stores `pass_at`, `sent`, `digest`, both counts and `skipped`.
- **`run_pass` records nothing.** Only `run_loop` records, after each pass, reading the clock once more for `pass_at`. A bare pass's clock reads are unchanged.
- **The counts are read from the row each pass**, inside the same transaction that writes it, so a restart carries on and two loops never lose a count. A stored row that fails to decode counts as no row: the counts start again from this pass, and the write replaces it.
- **A failed status write never stops the loop.** Any `Exception` while recording is dropped; the next pass tries again, and `docket status` shows the stale time. A crash (a `BaseException` that is not an `Exception`) is not caught, as for the passes.
- **One JSON writer.** `skipped` is written with `serialization.canonical_json`, widened to take a list of strings, so the stored text is `["t2","t5"]`.
- **Messages.** A bad value to save is `StoreError("invalid loop status")`; any stored row that fails to decode is `StoreError("invalid stored loop status")`. The row has one fixed number, so neither names an id.
- **The 5-minute bound is `domain.LOOP_STALE_MINUTES`**, beside the other shared bounds. More than 5 minutes is stale; exactly 5 is still running.
- **Exit code.** `docket status` exits 0 whatever the loop's state; only a store or settings error exits 1.

## Requirements

1. **Migration 7** (given, in `schema.py`): table `loop_status` (`number` fixed at 1, `pass_at`, `sent`, `digest` 0 or 1, `reminders_failures`, `digest_failures`, `skipped` a JSON array), STRICT, with CHECKs refusing a second row, negative counts and a `skipped` that is not an array; a trigger refuses deleting the row. Migrations 1 to 6 are unchanged.
2. **Record.** `store.LoopStatus` is a frozen dataclass with fields, in order, `pass_at: datetime`, `sent: int`, `digest: bool`, `reminders_failures: int`, `digest_failures: int`, `skipped: tuple[str, ...]`.
3. **Save.** `Store.save_loop_status(self, status: LoopStatus) -> None` needs a transaction and a UTC `pass_at` (the existing messages). It refuses, with `StoreError("invalid loop status")` and before any write, a count or `sent` that is not a non-negative `int` (a `bool` included), a `digest` that is not a `bool`, and a `skipped` that is not a tuple of task ids. Otherwise it writes the one row, replacing any earlier one, with `pass_at` as `_instant` text and `skipped` as `serialization.canonical_json(list(skipped))`. Its SQL is in a new `src/docket/_store_loop.py`, listed in `scripts/critical_modules.txt`.
4. **Read.** `Store.loop_status(self) -> LoopStatus | None` answers `None` before any row, and otherwise the stored row. A `pass_at` that is not a UTC instant, or a `skipped` that is not a JSON array of task ids, raises `StoreError("invalid stored loop status")`.
5. **Counting.** `reminders.next_status(previous: LoopStatus | None, result: PassResult, at: datetime) -> LoopStatus` answers `pass_at=at` and `result`'s `sent`, `digest` and `skipped`. `reminders_failures` is the previous count plus 1 when `"reminders"` is in `result.failed` or `result.skipped` is not empty, else 0; `digest_failures` is the previous count plus 1 when `"digest"` is in `result.failed`, else 0. No previous status counts as 0 and 0.
6. **The loop records.** After each pass, `run_loop` opens one transaction, reads `store.loop_status()` (a `StoreError` there counts as `None`), and saves `next_status(previous, result, clock.now())`. Any `Exception` while recording is dropped and the loop goes on; any other `BaseException` propagates. `run_loop`'s signature and answer are unchanged.
7. **Lines.** `views.loop_status_lines(status: LoopStatus | None, home: str, now: datetime) -> list[str]`:
   - `None`: `["Reminder loop: no pass recorded yet"]`.
   - Otherwise `Reminder loop: running, last pass <when>`, or `not running` instead of `running` when `now - pass_at` is more than `domain.LOOP_STALE_MINUTES` (5) minutes, with `<when>` from `views.when(pass_at, home, now)`;
   - then `Reminders: <health>, <sent> sent`;
   - then `Digest: <health>`, followed by `, sent` when `digest` is true;
   - then, only when `skipped` is not empty, `Skipped tasks: ` and the ids joined by `, `.
   - `<health>` is `ok` for a count of 0, `failing for 1 pass`, or `failing for <n> passes`.
8. **Command.** `docket status` reads the settings and home zone, opens the store, reads the clock once and the status, and prints each line of requirement 7; it exits 0. A store or settings error prints its message to stderr and exits 1, as other commands do.
9. **Same answers.** No notice, key, digest, reminder, post or task row changes. Every existing test passes, with the given edits named below.
10. **Given markers**: `tests/integration/test_loop_status.py` carries 14 strict `xfail` markers and `tests/e2e/test_cli_status.py` 3, each with a reason starting `Phase 5f given test: remove this marker`, one line each. Delete all 17 once requirements 2 to 9 are done, and nothing else in either file. A strict marker on a passing test fails the run, so `check.py` tells you when. Then append the progress entry for `## Phase 5f: Visible loop status (YYYY-MM-DD)` at the end of `docs/progress.md`.

## Given files

Already committed with this spec; never change them, except the markers of requirement 10.

| File | What it is |
|---|---|
| `src/docket/schema.py` | Given append-only `MIGRATION_7` (`loop_status`); migrations 1 to 6 unchanged |
| `tests/integration/test_loop_status.py` | Tests for the table, the store, the counting rule, the loop and the lines (list below) |
| `tests/e2e/test_cli_status.py` | Tests for `docket status` |
| `tests/integration/test_reminder_loop.py` | Edited: the loop test no longer pins 6 clock reads |
| `tests/integration/test_audit_link_key_contracts.py`, `test_reference_coverage.py`, `test_reference_migration.py`, `test_reminder_storage_edges.py`, `test_server.py`, `test_store.py`, `test_store_links.py`, `test_store_migrate.py`, `test_store_safety_coverage.py` (all in `tests/integration/`) | Edited: the current schema version 6 becomes 7 only |
| `tests/integration/test_store_coordination.py` | Edited: version 6 becomes 7, and the foreign-key observation gains `(6, 1)` |
| `docs/verification/probe-05f.py` | The verifier's probe |

The given tests check that:

- the table refuses a second row, a negative or text count, a `digest` of 2 and a `skipped` that is not an array, and refuses deleting the row (guards that pass with the given migration);
- a saved status reads back, a second save replaces the one row, and the stored text is exact;
- saving needs a transaction and a UTC time, and each bad value is refused before any write;
- each kind of bad stored row raises the constant error;
- `next_status` counts each half, resets on success, and counts a skip against the reminders half;
- the loop records each pass after it runs, reads the clock once more per pass, carries the counts on across a restart, starts again after a bad stored row, and keeps going when a status write fails, but not on a crash;
- a bare pass records nothing and reads the clock twice (a guard that passes today);
- `LOOP_STALE_MINUTES` is 5, and `loop_status_lines` answers each case, with 5 minutes still running and 5 minutes and 1 second not;
- `docket status` prints the no-pass line, the stored row running and stale, and refuses a bad stored row.

Given test count: **48** new (`test_loop_status.py`: 17 functions, 44 tests; `test_cli_status.py`: 3 functions, 4 tests). Before you start, they show 38 xfailed and 10 passed: the 8 table refusals, `test_the_status_row_is_never_removed` and `test_a_bare_pass_records_nothing_and_reads_the_clock_twice`. The edits to earlier files add no test.

## Tests to write

None are required: the given tests, the existing loop and CLI tests, and the probe cover requirements 1 to 9 and every line and branch of the draft. If a helper you add has a branch they miss, cover it in a new `tests/integration/test_loop_status_more.py`, never by changing a given test.

## Scope

| Path | Change |
|---|---|
| `src/docket/_store_loop.py` | create: requirement 3's SQL |
| `src/docket/store.py` | edit: requirements 2 to 4 |
| `src/docket/serialization.py` | edit: `canonical_json` also takes a list of strings |
| `src/docket/reminders.py` | edit: requirements 5 and 6 |
| `src/docket/domain.py` | edit: `LOOP_STALE_MINUTES = 5` |
| `src/docket/views.py` | edit: requirement 7 |
| `src/docket/cli.py` | edit: requirement 8 |
| `scripts/critical_modules.txt` | edit: add `_store_loop.py` |
| `tests/integration/test_loop_status.py` | delete the 14 markers only |
| `tests/e2e/test_cli_status.py` | delete the 3 markers only |
| `tests/integration/test_loop_status_more.py` | create, only if you need it |
| `docs/progress.md` | append your entry |

## Out of scope

- `docket run`, launchd, alerts, queue counts in `docket status`, and the pruning job (Phase 5g).
- Any logging, and any status written by `run_pass` alone.
- Any change to `PassResult`, `run_pass`, `send_due`, `send_digest`, `Store.transaction` or a reminder rule.
- Any change to a given file beyond the markers, `AGENTS.md` or the design docs.

## Rules that bite

- **Time from one place**: `pass_at` comes from `clock.now()`, called through the module, once per recorded pass; `docket status` reads it once.
- **Error messages are constant text**: the two loop-status messages name no value; `docket status` prints no stored text but task ids.
- **No telemetry**: the row stays in the local database; nothing is sent anywhere.
- **Secrets**: none are read or printed.
- **Critical modules**: every Scope module but `views.py` and `cli.py` is critical (`_store_loop.py` once listed); every line and branch is covered, with no `pragma: no cover`.
- If you stop before finishing, still write the progress entry with a `Stopped:` first follow-up (`docs/phase-conventions.md`, "When you stop").
- Commands start with `.venv/bin/python`; no bare `python3`, `pytest` or `ruff`.

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_loop_status.py --ignore=tests/e2e/test_cli_status.py` (before you start) | `1946 passed` |
| `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1994 passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest tests/integration/test_loop_status.py tests/e2e/test_cli_status.py --no-cov -q` | `48 passed` |
| `.venv/bin/python -m coverage report --include=src/docket/_store_loop.py,src/docket/store.py,src/docket/serialization.py,src/docket/reminders.py,src/docket/domain.py,src/docket/views.py,src/docket/cli.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| `.venv/bin/python docs/verification/probe-05f.py` | last line `FAILURES 0` |
| `grep -c "^## Phase 5f: " docs/progress.md` | `1` |
| `.venv/bin/python scripts/check_reports.py --phase 5f` | `Reports OK.` |
| `git diff HEAD --stat -- src/docket/schema.py docs/verification/probe-05f.py tests/integration/test_reminder_loop.py tests/integration/test_audit_link_key_contracts.py tests/integration/test_reference_coverage.py tests/integration/test_reference_migration.py tests/integration/test_reminder_storage_edges.py tests/integration/test_server.py tests/integration/test_store.py tests/integration/test_store_coordination.py tests/integration/test_store_links.py tests/integration/test_store_migrate.py tests/integration/test_store_safety_coverage.py tests/loop_cases.py tests/notifier_cases.py tests/support.py tests/conftest.py tests/sections.toml docs/reviews AGENTS.md pyproject.toml scripts/check.py scripts/tooling_modules.txt src/docket/core.py src/docket/notifier.py` | no output |
| `git diff HEAD --numstat -- tests/integration/test_loop_status.py tests/e2e/test_cli_status.py` | `0	14	tests/integration/test_loop_status.py` and `0	3	tests/e2e/test_cli_status.py` (the markers, nothing else) |
| `git status --short` | only the Scope paths |

### Searches

Each prints nothing.

```zsh
git grep --untracked -n -E 'import (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)|from (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)' -- src
git grep --untracked -n -E 'print\(|logging|logger|warnings\.warn' -- src ':!src/docket/cli.py'
git grep --untracked -n -E 'datetime\.now|datetime\.utcnow|date\.today|time\.time\(|from docket\.(clock|ids) import' -- src ':!src/docket/clock.py'
git grep --untracked -n -E 'pragma: no cover|noqa' -- src/docket/_store_loop.py src/docket/store.py src/docket/serialization.py src/docket/reminders.py src/docket/domain.py src/docket/views.py src/docket/cli.py
git grep --untracked -n -E 'json\.dumps' -- src ':!src/docket/serialization.py'
git grep --untracked -n -E 'loop_status' -- src ':!src/docket/_store_loop.py' ':!src/docket/schema.py' ':!src/docket/store.py' ':!src/docket/reminders.py' ':!src/docket/views.py' ':!src/docket/cli.py'
git grep --untracked -n -E 'minutes=5\)|LOOP_STALE_MINUTES = ' -- src ':!src/docket/domain.py'
```
