# Verification guide: Phase 1c (Task rules)

Spec: `docs/phases/phase-01c-task-rules.md`. Follow `docs/phase-conventions.md` ("For the verifier"). Never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor, never read the Keychain, and never open the real data folder.

## 1. Coder ran

Stop with FAIL ("the coder did not run") if any of these is missing:

- `src/docket/core.py`
- `grep -c "^## Phase 1c: " docs/progress.md` prints `1`

Stop with FAIL ("the baseline is not committed") if `git ls-files --error-unmatch docs/phases/phase-01c-task-rules.md tests/integration/test_core.py scripts/critical_modules.txt docs/verification/probe-01c.py` fails: the diff gates can only be judged against a committed spec and given files.

## 2. Gates

Run each from the repository root, in this order. Given test count: 89.

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_core.py` | at least 202 passed, 0 failed (the coder's `*_more.py` tests add to the count) |
| G2 | `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 291 passed, 0 failed, 0 skipped |
| G3 | `.venv/bin/python -m pytest tests/integration/test_core.py --no-cov -q` | `89 passed` |
| G4 | `.venv/bin/python -m coverage report --include=src/docket/core.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| G5 | `.venv/bin/python docs/verification/probe-01c.py` | last line `FAILURES 0` |
| G6 | `grep -c "^## Phase 1c: " docs/progress.md` | `1` |
| G7 | `.venv/bin/python scripts/check_reports.py --phase 1c` | `Reports OK.` |
| G8 | `git diff HEAD --stat -- tests/integration/test_core.py scripts/critical_modules.txt docs/verification/probe-01c.py` | no output |
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
| S1 | `core.py` | let Start move a done task to in progress | `tests/integration/test_core.py::test_every_state_change[done-start]` | `task_ended` | state `in_progress` |
| S2 | `core.py` | treat Reopen on an open task as a change | `tests/integration/test_core.py::test_every_state_change[open-reopen]` | `changed` False, no audit row | `changed` True |
| S3 | `core.py` | let Done apply to a cancelled task | `tests/integration/test_core.py::test_every_state_change[cancelled-done]` | `task_ended` | state `done` |
| S4 | `core.py` | use the source itself as the actor of a creation | `tests/integration/test_core.py::test_the_audit_actor_follows_the_source[proposal]` | actor `'owner'` | `sqlite3.IntegrityError` (the schema's actor CHECK) |
| S5 | `core.py` | drop the category check from `check_title` | `tests/integration/test_core.py::test_an_invalid_title_is_refused_never_rewritten[zero-width-space]` | `CoreError` (`invalid_title`) | DID NOT RAISE |
| S6 | `core.py` | drop the strip comparison from `check_title` | `tests/integration/test_core.py::test_an_invalid_title_is_refused_never_rewritten[leading-space]` | `CoreError` (`invalid_title`) | DID NOT RAISE |
| S7 | `core.py` | in `edit_task`, check the conflict only when a deadline is given | `tests/integration/test_core.py::test_an_edit_that_puts_work_past_the_deadline_is_refused[later-work]` | `work_after_deadline` | the edit is accepted |
| S8 | `core.py` | in `edit_task`, write a row for every field given, changed or not | `tests/integration/test_core.py::test_an_edit_can_clear_and_only_changed_fields_are_recorded` | one `work_time` row | `retitle`, `deadline` and `work_time` rows |
| S9 | `core.py` | in `edit_task`, return no change for an ended task when nothing is given | `tests/integration/test_core.py::test_an_ended_task_must_be_reopened_before_an_edit[nothing-done]` | `task_ended` | `Outcome(changed=False)` |
| S10 | `core.py` | read the clock before the argument checks | `tests/integration/test_core.py::test_a_refused_task_is_never_written[title]` | `CoreError` (`invalid_title`) | `StopIteration` |
| S11 | `core.py` | write the change and its audit row in two transactions | `tests/integration/test_core.py::test_a_change_and_its_audit_row_commit_together` | `tasks() == [made]` | the edit raises `CoreError` (`task_ended`): the first two calls left `t2` and a done `t1` behind |
| S12 | `core.py` | skip the reference check for sources other than email | `tests/integration/test_core.py::test_a_refused_task_is_never_written[reference-on-owner]` | `CoreError` (`invalid_reference`) | `StopIteration` (the clock is read with no moments given) |
| S13 | `core.py` | write snapshot instants with `isoformat()` without `timespec` | `tests/integration/test_core.py::test_a_new_task_records_its_deadline_and_work_time` | `'2026-11-20T22:00:00.000000+00:00'` | `'2026-11-20T22:00:00+00:00'` |
| S14 | `core.py` | append the `work_time` row before the `deadline` row | `tests/integration/test_core.py::test_an_edit_writes_one_row_per_field_in_a_fixed_order` | `retitle`, `deadline`, `work_time` | `retitle`, `work_time`, `deadline` |

## 4. Probe

Run `.venv/bin/python docs/verification/probe-01c.py` from the repository root. It is a given file: do not edit it. Every line must end in `ok`; the last line must be `FAILURES 0`. A stop at the probe's own `assert` lines, before its self-check prints `ok`, is the probe's fault: report it under "For the architect", not as a finding. The probe uses temporary folders for `HOME` and the data folder and touches no network or Keychain.

It checks what the given tests do not reach: 800 random creations, state changes and edits against the probe's own transition table, with no work time ever past its deadline and every task's audit rows replaying, from the create row on, to the task as stored; 50 trials of two threads, each with its own `Store`, pressing Done on one task at once, where exactly one press may change it and the audit holds one `done` row; and 5000 fuzzed titles judged by the probe's own rule. Each kind of walk step is reached at least 10 times.

## 5. Searches

Each prints nothing. A match is a finding against the rule it names.

| # | Rule | Command |
|---|---|---|
| Q1 | no network code | `git grep --untracked -n -E 'import (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)\|from (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)' -- src` |
| Q2 | no output or logging outside the CLI | `git grep --untracked -n -E 'print\(\|logging\|logger\|warnings\.warn' -- src ':!src/docket/cli.py'` |
| Q3 | time read only in `clock.py`, through the module | `git grep --untracked -n -E 'datetime\.now\|datetime\.utcnow\|date\.today\|time\.time\(\|from docket\.(clock\|ids) import' -- src ':!src/docket/clock.py'` |
| Q4 | only the core writes tasks and audit rows | `git grep --untracked -n -E '\.(insert_task\|update_task\|append_audit)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'` |
| Q5 | the core uses the store's methods, never SQL | `git grep --untracked -n -E 'sqlite3\|execute\(\|_connection' -- src/docket/core.py` |
| Q6 | no model client | `git grep --untracked -n -E 'ollama\|anthropic\|openai\|langchain' -- src` |
| Q7 | no coverage or lint exclusions in the critical module | `git grep --untracked -n -E 'pragma: no cover\|noqa' -- src/docket/core.py` |

(In the table, `\|` is a `|` in the command.)

## 6. Reasonable variations

These are correct even though the spec does not spell them out:

- The transition table as a dict, a `match` statement or `if` branches.
- `check_title` with a loop or `any(...)` over `unicodedata.category`; `isinstance` first.
- `CoreError` setting `code` in `__init__` and passing it to `Exception`; a `__str__` returning the code.
- A private helper per snapshot, or one for both; the snapshots built inside or outside the transaction.
- `edit_task` comparing old and new values with `!=` on `Deadline` and `WorkTime` (their dataclass equality).
- `create_task` checking the work-time conflict after the reference, before the clock, as the spec orders it.
- A no-change result returning the task as read inside the transaction.
- Private helpers inside the Scope modules, and extra behaviour tests in `*_more.py` files.

## 7. Verdict

Write `docs/reviews/phase-01c-task-rules.md` in the form `docs/phase-conventions.md` gives (`# Review: Phase 1c`), then run `.venv/bin/python scripts/check_reports.py --phase 1c`; it must print `Reports OK.`
