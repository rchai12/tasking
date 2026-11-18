# Verification guide: Phase 2m (Task table boundary)

Spec: `docs/phases/phase-02m-task-table-boundary.md`. Follow `docs/phase-conventions.md` ("For the verifier"). Never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor, never read the Keychain, and never open the real data folder.

## 1. Coder ran

Stop with FAIL ("the coder did not run") if any of these is missing:

- `src/docket/_store_tasks.py`
- `tests/integration/test_task_boundary_more.py`
- `grep -c "^## Phase 2m: " docs/progress.md` prints `1`

Stop with FAIL ("the coder stopped") if that entry's first `Follow-ups` line starts with `Stopped:`, as "A stopped coder" in `docs/phase-conventions.md` says. With no entry, `git status --short` tells "the coder did not run" (no Scope path changed) from "the coder broke off without reporting" (Scope paths changed; name them under `For the architect`).

Stop with FAIL ("the baseline is not committed") if `git ls-files --error-unmatch docs/phases/phase-02m-task-table-boundary.md tests/task_boundary_cases.py tests/integration/test_task_table_boundary.py scripts/critical_modules.txt docs/verification/probe-02m.py` fails: the diff gates can only be judged against a committed spec and given files.

## 2. Gates

Run each from the repository root, in this order: `.venv/bin/python scripts/accept.py --phase 2m --guide` runs them and the searches, one line each. Given test count: 26.

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_task_table_boundary.py` | at least 1193 passed, 0 failed (the coder's `*_more.py` tests add to the count) |
| G2 | `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1219 passed, 0 failed, 0 skipped |
| G3 | `.venv/bin/python -m pytest tests/integration/test_task_table_boundary.py --no-cov -q` | `26 passed` |
| G4 | `.venv/bin/python -m coverage report --include=src/docket/_store_tasks.py,src/docket/store.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| G5 | `.venv/bin/python docs/verification/probe-02m.py` | last line `FAILURES 0` |
| G6 | `grep -c "^## Phase 2m: " docs/progress.md` | `1` |
| G7 | `.venv/bin/python scripts/check_reports.py --phase 2m` | `Reports OK.` |
| G8 | `git diff HEAD --stat -- tests/task_boundary_cases.py tests/integration/test_task_table_boundary.py scripts/critical_modules.txt docs/verification/probe-02m.py` | no output |
| G9 | `git status --short` | only the Scope paths |
| G10 | `.venv/bin/python -m pip list --format=freeze \| wc -l` | `39` (unchanged; no dependency is added) |

## 3. Spot checks

Inspect the whole extraction first: task columns and ordinary SQL construction move; fixed field selection/expansion and encoded values stay with Store. The update map uses internal column identifiers, never external keys/fragments. Public records/sentinel/errors, time validation, transaction state, connection/thread ownership and setup/migration/preflight remain in Store. The three 2l modules and all earlier tests are unchanged. No new capability, query redesign, schema or API drift is allowed.

Run mutations in a clean disposable checkout containing the committed planning baseline and implementation, with PYTHONPATH=src:. directed at that checkout. Never mutate the owner's live checkout. All six mutations were confirmed against the old facade bodies before extraction; translate each policy/query mutation to its final owner. The architect validated a small SELECT delegation only and did not build a full reference extraction.

For a module under `src/`, write the change as an exact old and new text in the module the coder wrote and run `.venv/bin/python scripts/spot_check.py <module> --old '<old>' --new '<new>' --test '<deciding test>' --row S<n>`; it restores the module and prints one line. For any other file:
1. Copy the module outside the repository.
2. Make the change described in the module the coder wrote.
3. Run the deciding test with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest '<test>' --no-cov -q --tb=line`, and confirm it fails with the "Broken" value; rerun with `-vv` only when it doesn't.
4. Restore the module from your copy, delete `src/docket/__pycache__`, and confirm `git diff` is as before.

A different failure from the "Broken" column is a note, not a finding; a pass is a finding.

| # | Module | Change | Deciding test | Correct | Broken |
|---|---|---|---|---|---|
| S1 | _store_tasks.py, filtered list SQL | Replace state IN with state NOT IN, retaining bound placeholders | `tests/integration/test_task_table_boundary.py::test_filters_empty_and_missing_keep_their_exact_results` | t1,t3 | t2 |
| S2 | _store_tasks.py, all-task list SQL | Change ORDER BY number to ORDER BY number DESC | `tests/integration/test_task_table_boundary.py::test_filters_empty_and_missing_keep_their_exact_results` | t1,t2,t3 | t3,t2,t1 |
| S3 | store.py, update deadline field selection | Add a deadline is not None condition to the existing UNCHANGED guard | `tests/integration/test_task_table_boundary.py::test_update_keeps_unchanged_clear_and_replacement_values_literal[clear-deadline]` | three deadline columns NULL | old deadline retained |
| S4 | store.py, mandatory update timestamp field | Replace its updated_at column identifier with created_at | `tests/integration/test_task_table_boundary.py::test_update_keeps_unchanged_clear_and_replacement_values_literal[unchanged]` | created 14:00, updated 15:00 | created 15:00, updated 14:00 |
| S5 | store.py, Store.transaction exception branch | Change ROLLBACK to COMMIT | `tests/integration/test_task_table_boundary.py::test_failure_after_task_sql_rolls_back_rows_audit_keys_and_sequences[update]` | snapshot unchanged after interruption | partial task update persists |
| S6 | store.py, _task_from | Remove created_at UTC validation while retaining updated_at validation | `tests/integration/test_task_table_boundary.py::test_corrupt_task_refusals_stay_at_the_facade_without_repair[created-naive]` | safe StoreError with task id | expected StoreError not raised |

## 4. Probe

Run `.venv/bin/python docs/verification/probe-02m.py` from the repository root. It is a given file: do not edit it. Every line must end in `ok`; the last line must be `FAILURES 0`. A stop at the probe's own `assert` lines, before its self-check prints `ok`, is the probe's fault: report it under "For the architect", not as a finding. It touches no network, Keychain or real data folder.

The probe checks the four-table owner map and standard-library DST literals, records real SQL callers for creation/update/read/filter/audit/link/key paths on one connection, repeats an ended task/link request five times after reopen without changing any row/sequence, and forces post-task-insert/update interruptions followed by reopening. Each check has a fresh synthetic folder. `--oracle-only` must show FAILURES 0. Baseline prints missing-module and wrong-task-owner failures while restart/interruption guards pass; missing imports never crash the run. Run the published command without an extra PYTHONPATH to verify repository-root helper loading.

## 5. Searches

Each prints nothing. A match is a finding against the rule it names.

| # | Rule | Command |
|---|---|---|
| Q1 | no network code | `git grep --untracked -n -E 'import (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)\|from (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)' -- src` |
| Q2 | no output outside the CLI | `git grep --untracked -n -E 'print\(\|logging\|logger\|warnings\.warn' -- src ':!src/docket/cli.py'` |
| Q3 | time read only in clock.py, through the module | `git grep --untracked -n -E 'datetime\.now\|datetime\.utcnow\|date\.today\|time\.time\(\|from docket\.(clock\|ids) import' -- src ':!src/docket/clock.py'` |
| Q4 | only the core writes tasks, audit rows, links and keys | `git grep --untracked -n -E '\.(insert_task\|update_task\|append_audit\|insert_link\|insert_request_key)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'` |
| Q5 | no model client | `git grep --untracked -n -E 'ollama\|anthropic\|openai\|langchain' -- src` |
| Q6 | no coverage or lint exclusions in this phase's modules | `git grep --untracked -n -E 'pragma: no cover\|noqa' -- src/docket/_store_tasks.py src/docket/store.py` |

(In the table, `\|` is a `|` in the command.)

## 6. Reasonable variations

These are correct even though the spec does not spell them out:

- Private function names, typed row/cursor/scalar returns and signatures after the first connection parameter. Store calls through the module and retains all domain/conversion policy.
- Store handles an empty state collection without entering SQL, or the new helper handles it without executing a query; result stays [] and no unfiltered query is substituted.
- SQL whitespace and bound-placeholder construction preserving the existing columns, values, filters/order and row factory. Internal update-map iteration order can differ if values remain paired with the correct column.
- Existing facade private helpers can become delegators; task record conversion and the migration/preflight exception stay in Store.
- Private helpers inside the Scope modules, and extra behaviour tests in `*_more.py` files.

## 7. Verdict

Write `docs/reviews/phase-02m-task-table-boundary.md` in the form `docs/phase-conventions.md` gives (`# Review: Phase 2m`), then run `.venv/bin/python scripts/check_reports.py --phase 2m`; it must print `Reports OK.`
