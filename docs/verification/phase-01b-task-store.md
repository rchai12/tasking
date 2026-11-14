# Verification guide: Phase 1b (Task store)

Spec: `docs/phases/phase-01b-task-store.md`. Follow `docs/phase-conventions.md` ("For the verifier"). Never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor, never read the Keychain, and never open the real data folder.

## 1. Coder ran

Stop with FAIL ("the coder did not run") if any of these is missing:

- `src/docket/store.py`
- `grep -c "^## Phase 1b: " docs/progress.md` prints `1`

Stop with FAIL ("the baseline is not committed") if `git ls-files --error-unmatch docs/phases/phase-01b-task-store.md src/docket/schema.py tests/integration/test_store.py scripts/critical_modules.txt docs/verification/probe-01b.py` fails: the diff gates can only be judged against a committed spec and given files.

## 2. Gates

Run each from the repository root, in this order. Given test count: 50.

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_store.py` | at least 152 passed, 0 failed (the coder's `*_more.py` tests add to the count) |
| G2 | `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 202 passed, 0 failed, 0 skipped |
| G3 | `.venv/bin/python -m pytest tests/integration/test_store.py --no-cov -q` | `50 passed` |
| G4 | `.venv/bin/python -m coverage report --include=src/docket/schema.py,src/docket/store.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| G5 | `.venv/bin/python docs/verification/probe-01b.py` | last line `FAILURES 0` |
| G6 | `grep -c "^## Phase 1b: " docs/progress.md` | `1` |
| G7 | `.venv/bin/python scripts/check_reports.py --phase 1b` | `Reports OK.` |
| G8 | `git diff HEAD --stat -- src/docket/schema.py tests/integration/test_store.py scripts/critical_modules.txt docs/verification/probe-01b.py` | no output |
| G9 | `git status --short` | only the Scope paths |
| G10 | `.venv/bin/python -m pip list --format=freeze` | the same packages as before this phase: no new dependency |

## 3. Spot checks

For each row:
1. Copy the module outside the repository.
2. Make the change described in the module the coder wrote.
3. Run the deciding test with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest '<test>' --no-cov -vv`, and confirm it fails with the "Broken" value.
4. Restore the module from your copy, delete `src/docket/__pycache__`, and confirm `git diff` is as before.

A different failure from the "Broken" column is a note, not a finding; a pass is a finding.

| # | Module | Change | Deciding test | Correct | Broken |
|---|---|---|---|---|---|
| S1 | `store.py` | read an id with `t(\d+)` and `int()` of the digits | `tests/integration/test_store.py::test_a_lookup_by_an_unknown_or_malformed_id_finds_nothing[arabic-indic-digit]` | `None` | the `Task` `t1` |
| S2 | `store.py` | open a transaction with `BEGIN` instead of `BEGIN IMMEDIATE` | `tests/integration/test_store.py::test_a_transaction_holds_the_write_lock_until_it_ends` | `database is locked` raised | DID NOT RAISE |
| S3 | `store.py` | commit instead of rolling back when the block raises | `tests/integration/test_store.py::test_a_failed_transaction_leaves_nothing_and_no_lock` | `tasks() == []` | `[Task t1]` |
| S4 | `store.py` | drop `insert_task`'s transaction check | `tests/integration/test_store.py::test_a_write_needs_a_transaction[insert]` | `StoreError` (`TRANSACTION_MESSAGE`) | DID NOT RAISE |
| S5 | `store.py` | set `busy_timeout` to 0 | `tests/integration/test_store.py::test_a_second_writer_waits_for_the_first` | `found == ['t2']` | `found == []` (the thread's insert raised `database is locked`) |
| S6 | `store.py` | set the mode only when the file is new | `tests/integration/test_store.py::test_an_existing_file_is_made_private` | `0o600` (384) | `0o644` (420) |
| S7 | `store.py` | write instants with `isoformat()` without `timespec` | `tests/integration/test_store.py::test_the_stored_text_is_fixed` | `'2026-11-20T22:00:00.000000+00:00'` | `'2026-11-20T22:00:00+00:00'` |
| S8 | `store.py` | write audit JSON without `separators` | `tests/integration/test_store.py::test_the_stored_text_is_fixed` | `'{"state":"open"}'` | `'{"state": "open"}'` |
| S9 | `store.py` | treat `None` like `UNCHANGED` in `update_task` | `tests/integration/test_store.py::test_an_update_can_set_and_clear_every_field` | `(None, None)` | the old deadline and work time |
| S10 | `store.py` | drop the check for a newer `user_version` | `tests/integration/test_store.py::test_a_newer_schema_is_refused` | `StoreError` | DID NOT RAISE |
| S11 | `store.py` | drop the UTC check on `at` | `tests/integration/test_store.py::test_a_written_instant_must_be_utc[new-york]` | `StoreError` (`INSTANT_MESSAGE`) | DID NOT RAISE |
| S12 | `store.py` | in `tasks`, treat an empty collection like `None` | `tests/integration/test_store.py::test_tasks_are_listed_in_order_and_filtered_by_state` | `[]` for `set()` | all four tasks |
| S13 | `store.py` | drop the nested-transaction check | `tests/integration/test_store.py::test_a_transaction_cannot_be_nested` | `StoreError` (`NESTED_MESSAGE`) | `sqlite3.OperationalError` |
| S14 | `store.py` | in `open_store`, skip `prepare_data_dir` | `tests/integration/test_store.py::test_open_store_uses_the_private_data_folder` | the folder made `0o700` | `sqlite3.OperationalError` (unable to open database file) |

## 4. Probe

Run `.venv/bin/python docs/verification/probe-01b.py` from the repository root. It is a given file: do not edit it. Every line must end in `ok`; the last line must be `FAILURES 0`. A stop at the probe's own `assert` lines, before its self-check prints `ok`, is the probe's fault: report it under "For the architect", not as a finding. The probe uses temporary folders for `HOME` and the data folder and touches no network or Keychain.

It checks what the given tests do not reach: 600 random steps through two `Store` objects on one file (inserts with deadlines, work times and email references, partial updates, audit rows with nested JSON, a quarter of them failing inside their transaction, and restarts), compared with the probe's own model after every step, with the write lock checked free after every step and a fresh store compared at the end. Each kind of step is reached at least 20 times.

## 5. Searches

Each prints nothing. A match is a finding against the rule it names.

| # | Rule | Command |
|---|---|---|
| Q1 | no network code | `git grep --untracked -n -E 'import (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)\|from (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)' -- src` |
| Q2 | no output or logging outside the CLI | `git grep --untracked -n -E 'print\(\|logging\|logger\|warnings\.warn' -- src ':!src/docket/cli.py'` |
| Q3 | time read only in `clock.py`, through the module | `git grep --untracked -n -E 'datetime\.now\|datetime\.utcnow\|date\.today\|time\.time\(\|from docket\.(clock\|ids) import' -- src ':!src/docket/clock.py'` |
| Q4 | the store reads no clock and no settings of its own | `git grep --untracked -n -E 'clock\.now\|import clock\|get_settings\(' -- src/docket/store.py` |
| Q5 | no value formatted into SQL | `git grep --untracked -n -E 'execute(script\|many)?\([^)]*(%\|\.format\()' -- src` |
| Q6 | the store never deletes, rewrites the audit log, drops a table, or opens implicit transactions | `git grep --untracked -n -E 'DELETE FROM\|UPDATE audit_log\|DROP \|isolation_level=(""\|.DEFERRED.)' -- src/docket/store.py` |
| Q7 | no model client | `git grep --untracked -n -E 'ollama\|anthropic\|openai\|langchain' -- src` |
| Q8 | no coverage or lint exclusions in the critical modules | `git grep --untracked -n -E 'pragma: no cover\|noqa' -- src/docket/store.py src/docket/schema.py` |

(In the table, `\|` is a `|` in the command.)

## 6. Reasonable variations

These are correct even though the spec does not spell them out:

- Creating a new file with `os.open(..., 0o600)` before connecting, or connecting and then `chmod(0o600)`; either way the mode is checked after opening.
- Setting `journal_mode = WAL` on every open (it is stored in the file anyway).
- An UPDATE whose SET clause is built from a fixed list of column names in the code, one statement per call.
- The transaction check by `connection.in_transaction` or a private flag.
- Reading ids with `re.fullmatch` on an ASCII pattern (`t[1-9][0-9]*`), or with string methods and `isascii()`; a malformed id answered without a query.
- Rebuilding `Deadline` and `WorkTime` through their constructors on read, so their own checks run again.
- `update_task` with no fields given only setting `updated_at`.
- The checks of `update_task` and `append_audit` in the order transaction, instant, unknown task.
- A pytest warning about the thread in `test_a_second_writer_waits_for_the_first` under spot check S5 only: it is the broken run's own exception.
- Private helpers inside the Scope modules, and extra behaviour tests in `*_more.py` files.

## 7. Verdict

Write `docs/reviews/phase-01b-task-store.md` in the form `docs/phase-conventions.md` gives (`# Review: Phase 1b`), then run `.venv/bin/python scripts/check_reports.py --phase 1b`; it must print `Reports OK.`
