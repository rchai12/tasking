# Verification guide: Phase 2i (Safe store startup and reads)

Spec: `docs/phases/phase-02i-safe-store-startup-and-reads.md`. Follow `docs/phase-conventions.md` ("For the verifier"). Never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor, never read the Keychain, and never open the real data folder.

## 1. Coder ran

Stop with FAIL ("the coder did not run") if any of these is missing:

- `tests/integration/test_store_safety_coverage.py`
- `grep -c "^## Phase 2i: " docs/progress.md` prints `1`

Stop with FAIL ("the coder stopped") if that entry's first `Follow-ups` line starts with `Stopped:`, as "A stopped coder" in `docs/phase-conventions.md` says. With no entry, `git status --short` tells "the coder did not run" (no Scope path changed) from "the coder broke off without reporting" (Scope paths changed; name them under `For the architect`).

Stop with FAIL ("the baseline is not committed") if `git ls-files --error-unmatch docs/phases/phase-02i-safe-store-startup-and-reads.md tests/startup_cases.py tests/integration/test_stored_task_times.py tests/integration/test_store_startup.py tests/integration/test_store_coordination.py tests/e2e/test_stored_time_refusals.py docs/verification/probe-02i.py` fails: the diff gates can only be judged against a committed spec and given files.

## 2. Gates

Run each from the repository root, in this order: `.venv/bin/python scripts/accept.py --phase 2i --guide` runs them and the searches, one line each. Given test count: 76.

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_stored_task_times.py --ignore=tests/integration/test_store_startup.py --ignore=tests/integration/test_store_coordination.py --ignore=tests/e2e/test_stored_time_refusals.py` | at least 960 passed, 0 failed (the coder's `*_more.py` tests add to the count) |
| G2 | `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1036 passed, 0 failed, 0 skipped |
| G3 | `.venv/bin/python -m pytest tests/integration/test_stored_task_times.py tests/integration/test_store_startup.py tests/integration/test_store_coordination.py tests/e2e/test_stored_time_refusals.py --no-cov -q` | `76 passed` |
| G4 | `.venv/bin/python -m coverage report --include=src/docket/store.py,src/docket/cli.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| G5 | `.venv/bin/python docs/verification/probe-02i.py` | last line `FAILURES 0` |
| G6 | `grep -c "^## Phase 2i: " docs/progress.md` | `1` |
| G7 | `.venv/bin/python scripts/check_reports.py --phase 2i` | `Reports OK.` |
| G8 | `git diff HEAD --stat -- tests/startup_cases.py tests/integration/test_stored_task_times.py tests/integration/test_store_startup.py tests/integration/test_store_coordination.py tests/e2e/test_stored_time_refusals.py docs/verification/probe-02i.py` | no output |
| G9 | `git status --short` | only the Scope paths |
| G10 | `.venv/bin/python -m pip list --format=freeze \| wc -l` | `39` (unchanged; no package is added) |

## 3. Spot checks

Inspect the code before mutations: gate acquired before connect and held through initialization cleanup, descriptor released on every exit, inode never unlinked, and all version decisions/fresh eligibility reads inside immediate transactions. Per-migration atomicity and migration-3-only foreign-key relaxation remain. Confirm the only new persistent artifact is the empty private sidecar, and that task conversion suppresses library-error chains without repairing or skipping data.

Run mutations in a clean disposable checkout containing the planning baseline and implementation under review, with imports directed at that checkout. Do not mutate the user's live checkout: process termination can bypass restoration. Translate these one-line behavioural changes to the private helper names actually written. They are paper checks for the combined implementation; the architect validated the input cases using separate small patches rather than building a reference phase.

For a module under `src/`, write the change as an exact old and new text in the module the coder wrote and run `.venv/bin/python scripts/spot_check.py <module> --old '<old>' --new '<new>' --test '<deciding test>' --row S<n>`; it restores the module and prints one line. For any other file:
1. Copy the module outside the repository.
2. Make the change described in the module the coder wrote.
3. Run the deciding test with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest '<test>' --no-cov -q --tb=line`, and confirm it fails with the "Broken" value; rerun with `-vv` only when it doesn't.
4. Restore the module from your copy, delete `src/docket/__pycache__`, and confirm `git diff` is as before.

A different failure from the "Broken" column is a note, not a finding; a pass is a finding.

| # | Module | Change | Deciding test | Correct | Broken |
|---|---|---|---|---|---|
| S1 | `store.py`, startup gate | Omit the exclusive flock acquisition, keeping the file/descriptor handling | `tests/integration/test_store_coordination.py::test_startup_gate_is_private_held_before_connect_and_persistent` | second handle is blocked before SQLite opens | expected BlockingIOError not raised |
| S2 | `store.py`, gate release | Unlink the gate after releasing it | `tests/integration/test_store_coordination.py::test_startup_gate_is_private_held_before_connect_and_persistent` | persistent inode | missing-file failure after first open |
| S3 | `store.py`, gate acquisition error | Construct the StoreError from the caught OSError's text instead of the constant message | `tests/integration/test_store_coordination.py::test_gate_acquisition_error_is_constant_and_closes_the_descriptor` | `store startup unavailable` | library marker in error text |
| S4 | `store.py`, constructor failure cleanup | Omit the failed SQLite connection's close | `tests/integration/test_store_startup.py::test_each_failed_initialization_closes_the_connection_once[row_factory]` | one close | no recorded close |
| S5 | `store.py`, transaction start | Change `BEGIN IMMEDIATE` to `BEGIN` | `tests/integration/test_store_coordination.py::test_schema_version_decisions_are_under_an_immediate_transaction` | immediate write transaction for version reads | transaction-kind assertion fails |
| S6 | `store.py`, task created_at conversion | Keep ISO parsing but omit UTC validation for created_at | `tests/integration/test_stored_task_times.py::test_invalid_task_times_refuse_at_the_store_boundary[created-naive-task]` | StoreError with task ID | bad task returned; expected StoreError not raised |
| S7 | `store.py`, task conversion error mapping | Re-raise the original parsing error instead of the fixed StoreError | `tests/integration/test_stored_task_times.py::test_invalid_task_times_refuse_at_the_store_boundary[deadline-text-task]` | StoreError with task ID | ValueError |
| S8 | `store.py`, deadline zone passed to Deadline | Replace the raw deadline-zone value with its `.title()` result | `tests/integration/test_stored_task_times.py::test_invalid_task_times_refuse_at_the_store_boundary[deadline-case-task]` | StoreError with task ID | normalized task returned; expected StoreError not raised |
| S9 | `store.py`, corrupt-time StoreError | Chain the original parsing exception as its cause instead of suppressing it | `tests/integration/test_stored_task_times.py::test_invalid_task_times_refuse_at_the_store_boundary[created-text-task]` | no visible cause/context | non-None cause |
| S10 | `cli.py`, private store guard | Re-raise a StoreError from the context body instead of reporting it through the plain refusal handler | `tests/e2e/test_stored_time_refusals.py::test_cli_reports_only_the_task_id_for_corrupt_stored_time[show]` | constant stderr, exit 1 | empty stderr with uncaught exception |

## 4. Probe

Run `.venv/bin/python docs/verification/probe-02i.py` from the repository root. It is a given file: do not edit it. Every line must end in `ok`; the last line must be `FAILURES 0`. A stop at the probe's own `assert` lines, before its self-check prints `ok`, is the probe's fault: report it under "For the architect", not as a finding. It touches no network, Keychain or real data folder.

The probe combines two spawn-mode openers of a populated v2 database with row preservation and private gate checks, six corrupt task time/zone cases across reopen, and an early-setup failure that must close once. It has a main guard so child processes do not recursively execute it; run the published command without PYTHONPATH overrides. Its oracle-only mode checks the literal field matrix.

## 5. Searches

Each prints nothing. A match is a finding against the rule it names.

| # | Rule | Command |
|---|---|---|
| Q1 | no network code | `git grep --untracked -n -E 'import (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)\|from (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)' -- src` |
| Q2 | no output outside the CLI | `git grep --untracked -n -E 'print\(\|logging\|logger\|warnings\.warn' -- src ':!src/docket/cli.py'` |
| Q3 | time read only in clock.py, through the module | `git grep --untracked -n -E 'datetime\.now\|datetime\.utcnow\|date\.today\|time\.time\(\|from docket\.(clock\|ids) import' -- src ':!src/docket/clock.py'` |
| Q4 | only the core writes tasks, audit rows, links and keys | `git grep --untracked -n -E '\.(insert_task\|update_task\|append_audit\|insert_link\|insert_request_key)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'` |
| Q5 | no model client | `git grep --untracked -n -E 'ollama\|anthropic\|openai\|langchain' -- src` |
| Q6 | no coverage or lint exclusions in this phase's modules | `git grep --untracked -n -E 'pragma: no cover\|noqa' -- src/docket/store.py src/docket/cli.py` |

(In the table, `\|` is a `|` in the command.)

## 6. Reasonable variations

These are correct even though the spec does not spell them out:

- Private context-manager/helper names and how locked version reads are factored. All version decisions still happen under BEGIN IMMEDIATE with a fresh read before applying each migration.
- Cleanup via a context manager or a common failure guard, with the same once-only close, foreign-key restoration and original-error behaviour. Gate acquisition OSError normalization does not wrap errors from the yielded initialization body.
- Existing UTC parser forms remain valid. Error text carries the task ID only, without field-specific codes or data normalization.
- Private helpers stay inside store.py or the private CLI guard; extra tests stay in the Scope test file.

## 7. Verdict

Write `docs/reviews/phase-02i-safe-store-startup-and-reads.md` in the form `docs/phase-conventions.md` gives (`# Review: Phase 2i`), then run `.venv/bin/python scripts/check_reports.py --phase 2i`; it must print `Reports OK.`
