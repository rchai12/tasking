# Verification guide: Phase 6c (Core input checks)

Spec: `docs/phases/phase-06c-core-input-checks.md`. Follow `docs/phase-conventions.md` ("For the verifier"). Never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor, never read the Keychain, and never open the real data folder.

## 1. Coder ran

Stop with FAIL ("the coder did not run") if any of these is missing:


- `grep -c "^## Phase 6c: " docs/progress.md` prints `1`

Stop with FAIL ("the coder stopped") if that entry's first `Follow-ups` line starts with `Stopped:`, as "A stopped coder" in `docs/phase-conventions.md` says. With no entry, `git status --short` tells "the coder did not run" (no Scope path changed) from "the coder broke off without reporting" (Scope paths changed; name them under `For the architect`).

Stop with FAIL ("the baseline is not committed") if `git ls-files --error-unmatch docs/phases/phase-06c-core-input-checks.md tests/integration/test_core_value_types.py tests/unit/test_refusal_sentences.py docs/verification/probe-06c.py` fails: the diff gates can only be judged against a committed spec and given files. If the coder's work is already committed (a commit after the spec's, and a clean tree), judge every `git diff HEAD` gate against the spec's commit instead (`git log --diff-filter=A --format=%h -1 -- docs/phases/phase-06c-core-input-checks.md`), and the `git status --short` gate with `git diff <that commit> --name-status`.

## 2. Gates

Run each from the repository root, in this order: `.venv/bin/python scripts/accept.py --phase 6c --guide` runs them and the searches, one line each. Given test count: 53.

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_core_value_types.py --ignore=tests/unit/test_refusal_sentences.py` | at least 1653 passed, 0 failed (the coder's `*_more.py` tests add to the count) |
| G2 | `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1706 passed, 0 failed, 0 skipped |
| G3 | `.venv/bin/python -m pytest tests/integration/test_core_value_types.py tests/unit/test_refusal_sentences.py --no-cov -q` | `53 passed` |
| G4 | `.venv/bin/python -m coverage report --include=src/docket/core.py,src/docket/views.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| G5 | `.venv/bin/python docs/verification/probe-06c.py` | last line `FAILURES 0` |
| G6 | `grep -c "^## Phase 6c: " docs/progress.md` | `1` |
| G7 | `.venv/bin/python scripts/check_reports.py --phase 6c` | `Reports OK.` |
| G8 | `git diff HEAD --stat -- docs/verification/probe-06c.py tests/support.py tests/conftest.py tests/sections.toml docs/reviews AGENTS.md pyproject.toml scripts` | no output |
| G9 | `git diff HEAD --numstat -- tests/integration/test_core_value_types.py tests/unit/test_refusal_sentences.py` | two lines: 0 added, 21 deleted, `tests/integration/test_core_value_types.py`; 0 added, 6 deleted, `tests/unit/test_refusal_sentences.py` (the markers, nothing else) |
| G10 | `git status --short` | only the Scope paths |
| G11 | `.venv/bin/python -m pip list --format=freeze \| wc -l` | `52` (unchanged: this phase adds no package) |

## 3. Spot checks

For a module under `src/`, write the change as an exact old and new text in the module the coder wrote and run `.venv/bin/python scripts/spot_check.py <module> --old '<old>' --new '<new>' --test '<deciding test>' --row S<n>`; it restores the module and prints one line. For any other file:
1. Copy the module outside the repository.
2. Make the change described in the module the coder wrote.
3. Run the deciding test with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest '<test>' --no-cov -q --tb=line`, and confirm it fails with the "Broken" value; rerun with `-vv` only when it doesn't.
4. Restore the module from your copy, delete `src/docket/__pycache__`, and confirm `git diff` is as before.

A different failure from the "Broken" column is a note, not a finding; a pass is a finding.

| # | Module | Change | Deciding test | Correct | Broken |
|---|---|---|---|---|---|
| S1 | `core.py`, the deadline check | accept a `WorkTime` as a deadline too: `isinstance(deadline, (Deadline, WorkTime))` | `tests/integration/test_core_value_types.py::test_edit_task_refuses_a_deadline_that_is_not_one[work-time]` | `CoreError` `invalid_deadline` | `StopIteration` (the clock is read) |
| S2 | `core.py`, `edit_task` | move the check to just after `at = clock.now()` | `tests/integration/test_core_value_types.py::test_edit_task_refuses_a_deadline_that_is_not_one[string]` | `CoreError` `invalid_deadline` | `StopIteration` |
| S3 | `core.py`, the check | test the work time before the deadline | `tests/integration/test_core_value_types.py::test_edit_task_checks_the_deadline_before_the_work_time` | `invalid_deadline` | `invalid_work` |
| S4 | `core.py`, `create_task_once` | delete its call to the check | `tests/integration/test_core_value_types.py::test_create_task_once_refuses_a_value_and_keeps_the_key_free[deadline-string]` | `CoreError` `invalid_deadline` | `AttributeError: 'str' object has no attribute 'at'` |
| S5 | `views.py`, `_REFUSALS` | delete the `key_reused` sentence | `tests/unit/test_refusal_sentences.py::test_every_core_code_has_a_sentence` | `missing == []` | `['key_reused'] == []` |
| S6 | `core.py`, the check | refuse `None` as a deadline too (drop the `is not None` test) | `tests/integration/test_core_value_types.py::test_real_values_and_none_are_still_accepted` | the task is created | `CoreError: invalid_deadline` |

## 4. Probe

Run `.venv/bin/python docs/verification/probe-06c.py` from the repository root. It is a given file: do not edit it. Every line must end in `ok`; the last line must be `FAILURES 0`. A stop at the probe's own `assert` lines, before its self-check prints `ok`, is the probe's fault: report it under "For the architect", not as a finding. It touches no network, Keychain or real data folder.

It runs each of the three functions with 23 kinds of wrong value in each field (empty and date strings, numbers, `nan`, booleans, bytes, lists, tuples, dicts, a `date`, a bare `datetime`, a `timedelta`, plain objects), plus the other type and, for the creates, `UNCHANGED`: 148 calls, each with a clock that raises if read, and expects exactly the oracle's code and an unchanged database dump. It then creates and edits tasks with every mix of real values and `None`, and asks `refusal_text` for every public code of `docket.core`, with and without a task id.

## 5. Searches

Each prints nothing. A match is a finding against the rule it names.

| # | Rule | Command |
|---|---|---|
| Q1 | no network code | `git grep --untracked -n -E 'import (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)\|from (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)' -- src` |
| Q2 | no model client | `git grep --untracked -n -E 'ollama\|anthropic\|openai\|langchain' -- src` |
| Q3 | time read only in clock.py, through the module | `git grep --untracked -n -E 'datetime\.now\|datetime\.utcnow\|date\.today\|time\.time\(\|from docket\.(clock\|ids) import' -- src ':!src/docket/clock.py'` |
| Q4 | no coverage or lint exclusions in this phase's modules | `git grep --untracked -n -E 'pragma: no cover\|noqa' -- src/docket/core.py src/docket/views.py` |

(In the table, `\|` is a `|` in the command.)

## 6. Reasonable variations

These are correct even though the spec does not spell them out:

- One private helper for both checks, or two, or the `isinstance` tests written inline in each function, as long as the order and the place match requirements 2 to 4.
- In `edit_task`, turning `UNCHANGED` into `None` before the check, or skipping the check for `UNCHANGED`.
- The new sentences anywhere in `_REFUSALS`, in any order.
- Private helpers inside the Scope modules, and extra behaviour tests in `*_more.py` files.

## 7. Verdict

Write `docs/reviews/phase-06c-core-input-checks.md` in the form `docs/phase-conventions.md` gives (`# Review: Phase 6c`), then run `.venv/bin/python scripts/check_reports.py --phase 6c`; it must print `Reports OK.`
