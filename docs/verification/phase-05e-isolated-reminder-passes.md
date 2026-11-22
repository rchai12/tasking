# Verification guide: Phase 5e (Isolated reminder passes)

Spec: `docs/phases/phase-05e-isolated-reminder-passes.md`. Follow `docs/phase-conventions.md` ("For the verifier"). Never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor, never read the Keychain, and never open the real data folder.

## 1. Coder ran

Stop with FAIL ("the coder did not run") if any of these is missing:


- `grep -c "^## Phase 5e: " docs/progress.md` prints `1`

Stop with FAIL ("the coder stopped") if that entry's first `Follow-ups` line starts with `Stopped:`, as "A stopped coder" in `docs/phase-conventions.md` says. With no entry, `git status --short` tells "the coder did not run" (no Scope path changed) from "the coder broke off without reporting" (Scope paths changed; name them under `For the architect`).

Stop with FAIL ("the baseline is not committed") if `git ls-files --error-unmatch docs/phases/phase-05e-isolated-reminder-passes.md tests/integration/test_isolated_passes.py tests/integration/test_reminder_loop.py docs/verification/probe-05e.py` fails: the diff gates can only be judged against a committed spec and given files. If the coder's work is already committed (a commit after the spec's, and a clean tree), judge every `git diff HEAD` gate against the spec's commit instead (`git log --diff-filter=A --format=%h -1 -- docs/phases/phase-05e-isolated-reminder-passes.md`), and the `git status --short` gate with `git diff <that commit> --name-status`.

## 2. Gates

Run each from the repository root, in this order: `.venv/bin/python scripts/accept.py --phase 5e --guide` runs them and the searches, one line each. Given test count: 9.

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_isolated_passes.py` | at least 1936 passed, 0 failed (the coder's `*_more.py` tests add to the count) |
| G2 | `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1945 passed, 0 failed, 0 skipped |
| G3 | `.venv/bin/python -m pytest tests/integration/test_isolated_passes.py --no-cov -q` | `9 passed` |
| G4 | `.venv/bin/python -m coverage report --include=src/docket/reminders.py,src/docket/store.py,src/docket/_store_posts.py,src/docket/_store_reminders.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| G5 | `.venv/bin/python docs/verification/probe-05e.py` | last line `FAILURES 0` |
| G6 | `grep -c "^## Phase 5e: " docs/progress.md` | `1` |
| G7 | `.venv/bin/python scripts/check_reports.py --phase 5e` | `Reports OK.` |
| G8 | `git diff HEAD --stat -- docs/verification/probe-05e.py tests/integration/test_reminder_loop.py tests/loop_cases.py tests/notifier_cases.py tests/support.py tests/conftest.py tests/sections.toml docs/reviews AGENTS.md pyproject.toml scripts/check.py scripts/critical_modules.txt scripts/tooling_modules.txt src/docket/schema.py src/docket/core.py src/docket/notifier.py src/docket/cli.py` | no output |
| G9 | `git diff HEAD --numstat -- tests/integration/test_isolated_passes.py` | `0	8	tests/integration/test_isolated_passes.py` (the markers, nothing else) |
| G10 | `git status --short` | only the Scope paths |
| G11 | `.venv/bin/python -m pip list --format=freeze \| wc -l` | `52` (no package added) |

## 3. Spot checks

For a module under `src/`, write the change as an exact old and new text in the module the coder wrote and run `.venv/bin/python scripts/spot_check.py <module> --old '<old>' --new '<new>' --test '<deciding test>' --row S<n>`; it restores the module and prints one line. For any other file:
1. Copy the module outside the repository.
2. Make the change described in the module the coder wrote.
3. Run the deciding test with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest '<test>' --no-cov -q --tb=line`, and confirm it fails with the "Broken" value; rerun with `-vv` only when it doesn't.
4. Restore the module from your copy, delete `src/docket/__pycache__`, and confirm `git diff` is as before.

A different failure from the "Broken" column is a note, not a finding; a pass is a finding.

| # | Module | Change | Deciding test | Correct | Broken |
|---|---|---|---|---|---|
| S1 | `reminders.py`, the per-task catch | catch `KeyError` instead of `StoreError` | `tests/integration/test_isolated_passes.py::test_a_bad_reminder_row_silences_only_its_task` | `PassResult(2, False, (), ('t2',))` | `assert PassResult(se...), skipped=()) == PassResult(se...ipped=('t2',))` |
| S2 | `reminders.py`, the per-task catch | catch `Exception` instead of `StoreError` | `tests/integration/test_isolated_passes.py::test_an_unexpected_error_still_fails_the_whole_half` | `PassResult(0, False, ('reminders',), ())` | `assert PassResult(se...ipped=('t1',)) == PassResult(se...), skipped=())` |
| S3 | `reminders.py`, `send_due` | send the claimed posts in the order the tasks were visited (drop the sort by post number) | `tests/integration/test_isolated_passes.py::test_the_send_order_stays_by_post_number` | `k1` to `t2`, then `k2` to `t1` | `assert [('k2', 't1',...ng on this?')] == [('k1', 't2',...ng on this?')]` |
| S4 | `reminders.py`, `send_digest` | skip the empty-digest branch (send even when no line is left) | `tests/integration/test_isolated_passes.py::test_an_emptied_digest_is_marked_sent_without_a_send` | `False`, no attempt | `assert True is False` |
| S5 | `_store_posts.py` (or wherever `pending_task_ids` reads) | leave out the tasks that have only a claimable post | `tests/integration/test_isolated_passes.py::test_pending_task_ids_read_no_row_times` | `['t1', 't3']` | `assert ['t1'] == ['t1', 't3']` |
| S6 | `store.py`, `due_reminders` | ignore `task_id` (read every task's due rows) | `tests/integration/test_isolated_passes.py::test_due_reminders_and_claims_narrow_to_one_task` | `[('r10', 't2', 'before')]` | `assert [('r1', 't1',...2', 'before')] == [('r10', 't2', 'before')]` |
| S7 | `store.py`, `claim_posts` | ignore `task_id` (claim every task's posts) | `tests/integration/test_isolated_passes.py::test_due_reminders_and_claims_narrow_to_one_task` | `[('p2', 't2')]` | `assert [('p1', 't1'), ('p2', 't2')] == [('p2', 't2')]` |
| S8 | `reminders.py`, `run_pass` | build the result without the skipped ids | `tests/integration/test_isolated_passes.py::test_a_bad_reminder_row_silences_only_its_task` | `PassResult(2, False, (), ('t2',))` | `assert PassResult(se...), skipped=()) == PassResult(se...ipped=('t2',))` |

## 4. Probe

Run `.venv/bin/python docs/verification/probe-05e.py` from the repository root. It is a given file: do not edit it. Every line must end in `ok`; the last line must be `FAILURES 0`. A stop at the probe's own `assert` lines, before its self-check prints `ok`, is the probe's fault: report it under "For the architect", not as a finding. It touches no network, Keychain or real data folder.

The probe runs three seeded walks of 25 passes over six tasks, with a notifier that fails some sends and digests, under the spec commit's code and the coder's: with sound rows every pass result's first three fields, notice, key, digest and reminder, post and digest row must match. Then it plants one undecodable reminder row on one task per walk: every other task's notices and every digest must be exactly the clean run's, every pass must name that task alone in `skipped` with nothing in `failed`, and no post may be queued for it.

## 5. Searches

Each prints nothing. A match is a finding against the rule it names.

| # | Rule | Command |
|---|---|---|
| Q1 | no network code | `git grep --untracked -n -E 'import (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)\|from (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)' -- src` |
| Q2 | no output outside the CLI | `git grep --untracked -n -E 'print\(\|logging\|logger\|warnings\.warn' -- src ':!src/docket/cli.py'` |
| Q3 | time read only in clock.py, through the module | `git grep --untracked -n -E 'datetime\.now\|datetime\.utcnow\|date\.today\|time\.time\(\|from docket\.(clock\|ids) import' -- src ':!src/docket/clock.py'` |
| Q4 | no coverage or lint exclusions in this phase's modules | `git grep --untracked -n -E 'pragma: no cover\|noqa' -- src/docket/reminders.py src/docket/store.py src/docket/_store_posts.py src/docket/_store_reminders.py` |
| Q5 | each task gets its own transaction, not a savepoint | `git grep --untracked -n -i -E 'savepoint\|release savepoint' -- src` |
| Q6 | only StoreError skips a task: no narrower or library exception is caught in reminders | `git grep --untracked -n -E 'except (KeyError\|ValueError\|LookupError\|sqlite3\.)' -- src/docket/reminders.py` |

(In the table, `\|` is a `|` in the command.)

## 6. Reasonable variations

These are correct even though the spec does not spell them out:

- Gathering the claimed posts and their tasks in any structure, as long as they are sent in post-number order.
- Answering `pending_task_ids` with one SQL query or two merged in Python, and naming the private store helpers freely.
- `run_pass` reading the skipped ids through any private helper, or `send_due` delegating to one; `send_due`'s signature and `int` answer stay.
- Private helpers inside the Scope modules, and extra behaviour tests in `*_more.py` files.

## 7. Verdict

Write `docs/reviews/phase-05e-isolated-reminder-passes.md` in the form `docs/phase-conventions.md` gives (`# Review: Phase 5e`), then run `.venv/bin/python scripts/check_reports.py --phase 5e`; it must print `Reports OK.`
