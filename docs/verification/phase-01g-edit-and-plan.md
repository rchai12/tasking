# Verification guide: Phase 1g (Edit and plan)

Spec: `docs/phases/phase-01g-edit-and-plan.md`. Follow `docs/phase-conventions.md` ("For the verifier"). Never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor, never read the Keychain, and never open the real data folder.

## 1. Coder ran

Stop with FAIL ("the coder did not run") if any of these is missing:


- `grep -c "^## Phase 1g: " docs/progress.md` prints `1`

Stop with FAIL ("the coder stopped") if that entry's first `Follow-ups` line starts with `Stopped:`, as "A stopped coder" in `docs/phase-conventions.md` says. With no entry, `git status --short` tells "the coder did not run" (no Scope path changed) from "the coder broke off without reporting" (Scope paths changed; name them under `For the architect`).

Stop with FAIL ("the baseline is not committed") if `git ls-files --error-unmatch docs/phases/phase-01g-edit-and-plan.md tests/unit/test_views_edits.py tests/e2e/test_cli_edits.py docs/verification/probe-01g.py` fails: the diff gates can only be judged against a committed spec and given files.

## 2. Gates

Run each from the repository root, in this order. Given test count: 56.

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_views_edits.py --ignore=tests/e2e/test_cli_edits.py` | at least 466 passed, 0 failed (the coder's `*_more.py` tests add to the count) |
| G2 | `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 522 passed, 0 failed, 0 skipped |
| G3 | `.venv/bin/python -m pytest tests/unit/test_views_edits.py tests/e2e/test_cli_edits.py --no-cov -q` | `56 passed` |
| G4 | `.venv/bin/python -m coverage report --include=src/docket/views.py,src/docket/cli.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| G5 | `.venv/bin/python docs/verification/probe-01g.py` | last line `FAILURES 0` |
| G6 | `grep -c "^## Phase 1g: " docs/progress.md` | `1` |
| G7 | `.venv/bin/python scripts/check_reports.py --phase 1g` | `Reports OK.` |
| G8 | `git diff HEAD --stat -- tests/unit/test_views_edits.py tests/e2e/test_cli_edits.py docs/verification/probe-01g.py` | no output |
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
| S1 | `views.py` | drop `, no deadline` from `edited_text` | `tests/unit/test_views_edits.py::test_an_edit_reads_as_the_task_after_it[no-deadline]` | `'Updated t3: Pay rent, no deadline'` | `'Updated t3: Pay rent'` |
| S2 | `views.py` | show `planned_text` against `created_at` instead of `updated_at` | `tests/unit/test_views_edits.py::test_the_texts_use_the_change_time_not_the_clock` | `'Planned t3: Sun Mar 14 03:30 to 04:30 EDT'` | `'Planned t3: Sun Mar 14 2027 03:30 to 04:30 EDT'` |
| S3 | `cli.py` | treat an empty `--title ""` as not given | `tests/e2e/test_cli_edits.py::test_a_refused_edit_changes_nothing[empty-title]` | the title sentence | `'Give --title, --due or --no-due.'` |
| S4 | `cli.py` | drop the `--due` with `--no-due` check | `tests/e2e/test_cli_edits.py::test_a_refused_edit_changes_nothing[due-and-no-due]` | exit 1, `BOTH_DUES_MESSAGE` | exit 0, an `Updated t1: ...` line (the one clock moment reaches the core) |
| S5 | `cli.py` | let `--clear` take `--minutes` | `tests/e2e/test_cli_edits.py::test_a_refused_plan_changes_nothing[clear-with-minutes]` | exit 1, `CLEAR_ALONE_MESSAGE` | exit 0, `'Nothing changed for t1.'` |
| S6 | `cli.py` | build the work time with `WorkTime(...)` instead of `make_work_time`, skipping the midnight check | `tests/e2e/test_cli_edits.py::test_a_refused_plan_changes_nothing[past-midnight]` | exit 1, `MIDNIGHT_MESSAGE` | exit 0, `'Planned t1: Fri Nov 20 23:30 EST to Sat Nov 21 00:30 EST'` |
| S7 | `cli.py` | default the length to 60 instead of `settings.work_minutes` | `tests/e2e/test_cli_edits.py::test_planning_a_work_time[length-setting]` | `'... 14:00 to 14:45 EST'` | `'... 14:00 to 15:00 EST'` |
| S8 | `cli.py` | read `clock.now()` in `edit` before calling the core | `tests/e2e/test_cli_edits.py::test_edit_and_plan_read_only_the_cores_clock[edit]` | exit 0 | exit 1 (the core's read raises `StopIteration`) |
| S9 | `cli.py` | check the start time before the date | `tests/e2e/test_cli_edits.py::test_a_refused_plan_changes_nothing[date-checked-before-time]` | `PLAN_DATE_MESSAGE` | `PLAN_TIME_MESSAGE` |
| S10 | `cli.py` | pass `actor="agent"` in `edit` | `tests/e2e/test_cli_edits.py::test_editing_a_task[title]` | last audit row `('retitle', 'owner')` | `('retitle', 'agent')` |
| S11 | `cli.py` | print `MIDNIGHT_MESSAGE` for the length refusal too | `tests/e2e/test_cli_edits.py::test_a_refused_plan_changes_nothing[too-short]` | `MINUTES_MESSAGE` | `MIDNIGHT_MESSAGE` |
| S12 | `cli.py` | call `refusal_text(code)` without the id | `tests/e2e/test_cli_edits.py::test_the_core_refuses_and_nothing_changes[edit-ended]` | `'Task t1 has ended; reopen it first.'` | `'That task has ended; reopen it first.'` |

Each row was traced with its test's clock list as a layer: S4, S5 and S6 reach the core because their tests give one clock moment; S8's test gives exactly one, so a second read stops at `StopIteration`.

## 4. Probe

Run `.venv/bin/python docs/verification/probe-01g.py` from the repository root. It is a given file: do not edit it. Every line must end in `ok`; the last line must be `FAILURES 0`. A stop at the probe's own `assert` lines, before its self-check prints `ok`, is the probe's fault: report it under "For the architect", not as a finding. The probe uses temporary folders for `HOME` and the data folder and touches no network or Keychain.

It checks what the given tests do not reach: 900 random `edit` and `plan` calls on four tasks (one done) and an unknown id, mixing valid and invalid titles, dates, times, lengths, `--no-due` and `--clear`, each answer compared with the probe's own order of checks (the command's checks, then the core's: title, unknown, ended, conflict, no change) and its model of the tasks, with at most one clock read per call and the stored title, deadline and work time checked after each. Expected text comes from Phase 1d's views. Each kind of answer is reached at least 15 times.

## 5. Searches

Each prints nothing. A match is a finding against the rule it names.

| # | Rule | Command |
|---|---|---|
| Q1 | no network code | `git grep --untracked -n -E 'import (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)\|from (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)' -- src` |
| Q2 | no output outside the CLI | `git grep --untracked -n -E 'print\(\|logging\|logger\|warnings\.warn' -- src ':!src/docket/cli.py'` |
| Q3 | time read only in `clock.py`, through the module | `git grep --untracked -n -E 'datetime\.now\|datetime\.utcnow\|date\.today\|time\.time\(\|from docket\.(clock\|ids) import' -- src ':!src/docket/clock.py'` |
| Q4 | the commands write only through the core | `git grep --untracked -n -E '\.(insert_task\|update_task\|append_audit)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'` |
| Q5 | the command line acts only as the owner | `git grep --untracked -n -E 'actor=.(agent\|email).' -- src/docket/cli.py` |
| Q6 | no environment, machine zone or locale in the commands and views | `git grep --untracked -n -E 'os\.environ\|getenv\(\|strftime\(\|import locale' -- src/docket/cli.py src/docket/views.py` |
| Q7 | no model client | `git grep --untracked -n -E 'ollama\|anthropic\|openai\|langchain' -- src` |
| Q8 | no coverage or lint exclusions in this phase's modules | `git grep --untracked -n -E 'pragma: no cover\|noqa' -- src/docket/cli.py src/docket/views.py` |

(In the table, `\|` is a `|` in the command.)

## 6. Reasonable variations

These are correct even though the spec does not spell them out:

- `edit` reusing Phase 1e's private deadline parser; `plan` reusing the shape patterns with its own messages.
- `DeadlineError` mapped to the two messages by comparing `str(error)` with `WORK_LENGTH_MESSAGE` and `WORK_DAY_MESSAGE`, or by checking the length before calling `make_work_time`.
- `--no-due` and `--clear` as `typer.Option(False, ...)` flags.
- A missing date and a missing start sharing one check.
- Private helpers inside the Scope modules, and extra behaviour tests in `*_more.py` files.

## 7. Verdict

Write `docs/reviews/phase-01g-edit-and-plan.md` in the form `docs/phase-conventions.md` gives (`# Review: Phase 1g`), then run `.venv/bin/python scripts/check_reports.py --phase 1g`; it must print `Reports OK.`
