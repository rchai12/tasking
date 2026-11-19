# Verification guide: Phase 3e (Reminder loop)

Spec: `docs/phases/phase-03e-reminder-loop.md`. Follow `docs/phase-conventions.md` ("For the verifier"). Never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor, never read the Keychain, and never open the real data folder.

## 1. Coder ran

Stop with FAIL ("the coder did not run") if any of these is missing:

- `tests/integration/test_reminder_loop_edges.py`
- `grep -c "^## Phase 3e: " docs/progress.md` prints `1`

Stop with FAIL ("the coder stopped") if that entry's first `Follow-ups` line starts with `Stopped:`, as "A stopped coder" in `docs/phase-conventions.md` says. With no entry, `git status --short` tells "the coder did not run" (no Scope path changed) from "the coder broke off without reporting" (Scope paths changed; name them under `For the architect`).

Stop with FAIL ("the baseline is not committed") if `git ls-files --error-unmatch docs/phases/phase-03e-reminder-loop.md tests/loop_cases.py tests/integration/test_reminder_loop.py tests/integration/test_reminder_engine_stage.py docs/verification/probe-03e.py` fails: the diff gates can only be judged against a committed spec and given files.

## 2. Gates

Run each from the repository root, in this order: `.venv/bin/python scripts/accept.py --phase 3e --guide` runs them and the searches, one line each. Given test count: 17.

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_reminder_loop.py --ignore=tests/integration/test_reminder_engine_stage.py` | at least 1650 passed, 0 failed (the coder's `*_more.py` tests add to the count) |
| G2 | `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1667 passed, 0 failed, 0 skipped |
| G3 | `.venv/bin/python -m pytest tests/integration/test_reminder_loop.py tests/integration/test_reminder_engine_stage.py --no-cov -q` | `17 passed` |
| G4 | `.venv/bin/python -m coverage report --include=src/docket/reminders.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| G5 | `.venv/bin/python docs/verification/probe-03e.py` | last line `FAILURES 0` |
| G6 | `grep -c "^## Phase 3e: " docs/progress.md` | `1` |
| G7 | `.venv/bin/python scripts/check_reports.py --phase 3e` | `Reports OK.` |
| G8 | `git diff HEAD --stat -- tests/loop_cases.py tests/integration/test_reminder_loop.py tests/integration/test_reminder_engine_stage.py docs/verification/probe-03e.py` | no output |
| G9 | `git status --short` | only the Scope paths |
| G10 | `.venv/bin/python -m pip list --format=freeze \| wc -l` | `39` (unchanged; no dependency added) |

## 3. Spot checks

For a module under `src/`, write the change as an exact old and new text in the module the coder wrote and run `.venv/bin/python scripts/spot_check.py <module> --old '<old>' --new '<new>' --test '<deciding test>' --row S<n>`; it restores the module and prints one line. For any other file:
1. Copy the module outside the repository.
2. Make the change described in the module the coder wrote.
3. Run the deciding test with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest '<test>' --no-cov -q --tb=line`, and confirm it fails with the "Broken" value; rerun with `-vv` only when it doesn't.
4. Restore the module from your copy, delete `src/docket/__pycache__`, and confirm `git diff` is as before.

A different failure from the "Broken" column is a note, not a finding; a pass is a finding.

| # | Module | Change | Deciding test | Correct | Broken |
|---|---|---|---|---|---|
| S1 | `reminders.py`, run_pass | catch `BaseException` instead of `Exception` around the reminders half | `tests/integration/test_reminder_loop.py::test_a_crash_is_not_caught_by_the_loop` | raises Killed | DID NOT RAISE Killed |
| S2 | `reminders.py`, run_pass | return the result right after a failed reminders half, skipping the digest | `tests/integration/test_reminder_loop.py::test_each_half_of_a_pass_fails_alone[reminders-bug]` | PassResult(0, True, ('reminders',)) | PassResult(0, False, ('reminders',)) |
| S3 | `reminders.py`, run_pass | call send_digest with no try around it | `tests/integration/test_reminder_loop.py::test_each_half_of_a_pass_fails_alone[digest-bug]` | PassResult(2, False, ('digest',)) | SyntheticBug raised |
| S4 | `reminders.py`, run_loop | end the loop after a pass whose result has a failed half | `tests/integration/test_reminder_loop.py::test_the_loop_keeps_going_after_a_failed_pass_and_resends_after_five_minutes` | 12 passes | 1 pass |
| S5 | `reminders.py`, run_loop | wait `2 * LOOP_SECONDS` after each pass | `tests/integration/test_reminder_loop.py::test_the_loop_waits_thirty_seconds_after_each_pass_until_stopped` | waits [30, 30, 30] | waits [60, 60, 60] |
| S6 | `reminders.py`, run_loop | drop the stop check before each pass (`while True:`) | `tests/integration/test_reminder_loop.py::test_a_loop_already_stopped_runs_no_pass[threading-event-already-set]` | 0 passes | 1 pass |
| S7 | `reminders.py`, run_pass | send the digest before the due reminders | `tests/integration/test_reminder_loop.py::test_a_pass_sends_due_reminders_then_the_digest_and_says_what_it_sent` | k1 t1 due soon, k2 t2 late, k3 digest | k1 digest first |
| S8 | `reminders.py`, run_pass | return `digest=False` whatever send_digest answered | `tests/integration/test_reminder_loop.py::test_a_pass_sends_due_reminders_then_the_digest_and_says_what_it_sent` | PassResult(2, True, ()) | PassResult(2, False, ()) |
| S9 | `reminders.py`, run_pass | record the reminders half as `send_due` instead of `reminders` | `tests/integration/test_reminder_loop.py::test_each_half_of_a_pass_fails_alone[both-halves]` | failed ('reminders', 'digest') | failed ('send_due', 'digest') |

## 4. Probe

Run `.venv/bin/python docs/verification/probe-03e.py` from the repository root. It is a given file: do not edit it. Every line must end in `ok`; the last line must be `FAILURES 0`. A stop at the probe's own `assert` lines, before its self-check prints `ok`, is the probe's fault: report it under "For the architect", not as a finding. It touches no network, Keychain or real data folder.

The oracle pins schema version 6 and the 30-second step before touching a candidate. A scripted walk then drives the loop from a fake clock and stop through reminder bugs before and after delivery, refusals, two crashes, two restarts, a task done and reopened mid-run, a task created long overdue, and jumps of hours, so the digest is queued by the loop on two days. A seeded random walk mixes the same events. Each run checks that `run_loop` returns the passes asked for, or raises only the crash, that every pause is 30 seconds, and that the clock is read twice a pass (once or twice more in a crashed pass), which only happens when the digest half ran after a failed reminders half. Every notice attempt is checked to be for a task still open. At the end, after a healthy stretch past every claim's expiry, the probe checks that no due reminder of an open task is left unsent, that no key was delivered twice, and that nothing is marked sent that was never delivered.

## 5. Searches

Each prints nothing. A match is a finding against the rule it names.

| # | Rule | Command |
|---|---|---|
| Q1 | no network code | `git grep --untracked -n -E 'import (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)\|from (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)' -- src` |
| Q2 | no output outside the CLI | `git grep --untracked -n -E 'print\(\|logging\|logger\|warnings\.warn' -- src ':!src/docket/cli.py'` |
| Q3 | time read only in clock.py, through the module | `git grep --untracked -n -E 'datetime\.now\|datetime\.utcnow\|date\.today\|time\.time\(\|from docket\.(clock\|ids) import' -- src ':!src/docket/clock.py'` |
| Q4 | no model client | `git grep --untracked -n -E 'ollama\|anthropic\|openai\|langchain' -- src` |
| Q5 | no coverage or lint exclusions in this phase's modules | `git grep --untracked -n -E 'pragma: no cover\|noqa' -- src/docket/reminders.py` |
| Q6 | the loop catches Exception only, once per half | `git grep --untracked -n -E 'except BaseException\|except:\|except \(' -- src/docket/reminders.py` |
| Q7 | only the stop's wait pauses the loop; it reads no settings and starts no thread or timer | `git grep --untracked -n -E 'time\.sleep\(\|asyncio\|threading\|signal\|get_settings\|DIGEST_TIME' -- src/docket/reminders.py` |
| Q8 | nothing in this phase starts the loop or a pass | `git grep --untracked -n -E '(run_loop\|run_pass)\(' -- src ':!src/docket/reminders.py'` |
| Q9 | retry keys are made only by the engine's sending halves | `git grep --untracked -n -E 'ids\.new_id\(' -- src ':!src/docket/reminders.py'` |

(In the table, `\|` is a `|` in the command.)

## 6. Reasonable variations

These are correct even though the spec does not spell them out:

- Writing `run_loop` as a `while` loop or a `for` loop over `itertools.count()`, as long as the stop is checked before each pass and the wait's answer after it.
- Defining `Stop` with `typing.Protocol` with or without `runtime_checkable`.
- A private helper that runs one half and records its failure, as long as each half has its own `except Exception`.
- Extra behaviour tests in `tests/integration/test_reminder_loop_edges.py`. Logging, printing, counting failures in a row, a backoff, a command, a thread or a settings read is not a variation.
- Private helpers inside the Scope modules, and extra behaviour tests in `*_more.py` files.

## 7. Verdict

Write `docs/reviews/phase-03e-reminder-loop.md` in the form `docs/phase-conventions.md` gives (`# Review: Phase 3e`), then run `.venv/bin/python scripts/check_reports.py --phase 3e`; it must print `Reports OK.`
