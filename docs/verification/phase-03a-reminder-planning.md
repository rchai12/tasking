# Verification guide: Phase 3a (Deterministic reminder planning)

Spec: `docs/phases/phase-03a-reminder-planning.md`. Follow `docs/phase-conventions.md` ("For the verifier"). Never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor, never read the Keychain, and never open the real data folder.

## 1. Coder ran

Stop with FAIL ("the coder did not run") if any of these is missing:

- `src/docket/reminders.py`
- `tests/unit/test_reminder_plan_edges.py`
- `grep -c "^## Phase 3a: " docs/progress.md` prints `1`

Stop with FAIL ("the coder stopped") if that entry's first `Follow-ups` line starts with `Stopped:`, as "A stopped coder" in `docs/phase-conventions.md` says. With no entry, `git status --short` tells "the coder did not run" (no Scope path changed) from "the coder broke off without reporting" (Scope paths changed; name them under `For the architect`).

Stop with FAIL ("the baseline is not committed") if `git ls-files --error-unmatch docs/phases/phase-03a-reminder-planning.md tests/reminder_plan_cases.json tests/reminder_cases.py tests/unit/test_reminder_plans.py scripts/critical_modules.txt tests/tooling_boundary_manifest.json tests/product_support_manifest.json tests/product_consolidation_manifest.json tests/product_organization_manifest.json docs/verification/probe-03a.py` fails: the diff gates can only be judged against a committed spec and given files.

## 2. Gates

Run each from the repository root, in this order: `.venv/bin/python scripts/accept.py --phase 3a --guide` runs them and the searches, one line each. Given test count: 30.

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_reminder_plans.py` | at least 1349 passed, 0 failed (the coder's `*_more.py` tests add to the count) |
| G2 | `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1379 passed, 0 failed, 0 skipped |
| G3 | `.venv/bin/python -m pytest tests/unit/test_reminder_plans.py --no-cov -q` | `30 passed` |
| G4 | `.venv/bin/python -m coverage report --include=src/docket/reminders.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| G5 | `.venv/bin/python docs/verification/probe-03a.py` | last line `FAILURES 0` |
| G6 | `grep -c "^## Phase 3a: " docs/progress.md` | `1` |
| G7 | `.venv/bin/python scripts/check_reports.py --phase 3a` | `Reports OK.` |
| G8 | `git diff HEAD --stat -- tests/reminder_plan_cases.json tests/reminder_cases.py tests/unit/test_reminder_plans.py scripts/critical_modules.txt tests/tooling_boundary_manifest.json tests/product_support_manifest.json tests/product_consolidation_manifest.json tests/product_organization_manifest.json docs/verification/probe-03a.py` | no output |
| G9 | `git status --short` | only the Scope paths |
| G10 | `.venv/bin/python -m pip list --format=freeze \| wc -l` | `39` (unchanged; no added dependency) |

## 3. Spot checks

These are paper mutations against the specified pure contract, not mutations run against a reference implementation. Apply each as a one-line semantic change to the named role in the coder's implementation; retain the deciding input. There is no architect-built planner to compare against.

Before PASS, inspect planning-time guard edits against 5bafc08: AGENTS.md changes only the approved ID rule; the critical registry and tooling product_critical list append reminders.py. The remaining three manifest changes update only authorized frozen hashes and their dependent manifest hashes; product_organization also updates manifest.after_sha256. All before_sha256 history, case lists, body/import fingerprints, frozen counts, document and selector inventories must remain exact. No old guard is deleted or widened. These files are committed givens and coder-immutable.

For a module under `src/`, write the change as an exact old and new text in the module the coder wrote and run `.venv/bin/python scripts/spot_check.py <module> --old '<old>' --new '<new>' --test '<deciding test>' --row S<n>`; it restores the module and prints one line. For any other file:
1. Copy the module outside the repository.
2. Make the change described in the module the coder wrote.
3. Run the deciding test with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest '<test>' --no-cov -q --tb=line`, and confirm it fails with the "Broken" value; rerun with `-vv` only when it doesn't.
4. Restore the module from your copy, delete `src/docket/__pycache__`, and confirm `git diff` is as before.

A different failure from the "Broken" column is a note, not a finding; a pass is a finding.

| # | Module | Change | Deciding test | Correct | Broken |
|---|---|---|---|---|---|
| S1 | `reminders.py`, plan_reminders | change the warning boundary from at least one hour to strictly more than one hour | `tests/unit/test_reminder_plans.py::test_the_complete_reminder_plan[exact-hour]` | before at 17:00 UTC | due_soon at 17:00 UTC or missing warning |
| S2 | `reminders.py`, LATE_MINUTES | change its final value 720 to 721 | `tests/unit/test_reminder_plans.py::test_late_offsets_are_the_seven_decided_real_minute_offsets` | final offset 720 | final offset 721 |
| S3 | `reminders.py`, plan_reminders | remove cancelled from the terminal-state guard | `tests/unit/test_reminder_plans.py::test_the_complete_reminder_plan[cancelled]` | empty tuple | nonempty start/deadline plan |
| S4 | `reminders.py`, plan_reminders | change the equal-time ordering to put before ahead of start | `tests/unit/test_reminder_plans.py::test_the_complete_reminder_plan[start-before-warning-tie]` | start then before at 17:00 | before then start |
| S5 | `reminders.py`, plan_reminders | omit validation of now before the terminal-state return | `tests/unit/test_reminder_plans.py::test_now_requires_the_existing_canonical_utc_contract[done-zoneinfo-utc]` | DeadlineError: an instant must be in UTC | DID NOT RAISE |
| S6 | `reminders.py`, PlannedReminder | change its frozen dataclass decorator to a mutable dataclass decorator | `tests/unit/test_reminder_plans.py::test_plan_rows_are_frozen_and_contain_only_kind_and_fire_time` | FrozenInstanceError | DID NOT RAISE |
| S7 | `reminders.py`, plan_reminders | insert the single body line __import__("docket.clock", fromlist=["now"]).now() before planning | `tests/unit/test_reminder_plans.py::test_planning_is_repeatable_and_reads_no_clock_ids_settings_or_database` | two equal plans with no reads | UnexpectedRead |

## 4. Probe

Run `.venv/bin/python docs/verification/probe-03a.py` from the repository root. It is a given file: do not edit it. Every line must end in `ok`; the last line must be `FAILURES 0`. A stop at the probe's own `assert` lines, before its self-check prints `ok`, is the probe's fault: report it under "For the architect", not as a finding. It touches no network, Keychain or real data folder.

The literal oracle checks both real ZoneInfo fold=0 conversions and all seven elapsed late offsets independently of the planner. The probe then checks the 19 whole-plan examples plus 21 deterministic boundary plans (before reached 6 times, due_soon 6, past 9). It checks repeatability, unique rows, original due instants, seven late slots and ordering. This is a pure scheduling probe, not a restart or delivery test. --oracle-only must pass before judging implementation; an oracle assertion is an architect issue.

## 5. Searches

Each prints nothing. A match is a finding against the rule it names.

| # | Rule | Command |
|---|---|---|
| Q1 | no network code | `git grep --untracked -n -E 'import (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)\|from (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)' -- src` |
| Q2 | no output outside the CLI | `git grep --untracked -n -E 'print\(\|logging\|logger\|warnings\.warn' -- src ':!src/docket/cli.py'` |
| Q3 | time read only in clock.py, through the module | `git grep --untracked -n -E 'datetime\.now\|datetime\.utcnow\|date\.today\|time\.time\(\|from docket\.(clock\|ids) import' -- src ':!src/docket/clock.py'` |
| Q4 | only the core writes tasks, audit rows, links and keys | `git grep --untracked -n -E '\.(insert_task\|update_task\|append_audit\|insert_link\|insert_request_key)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'` |
| Q5 | no model client | `git grep --untracked -n -E 'ollama\|anthropic\|openai\|langchain' -- src` |
| Q6 | no coverage or lint exclusions in this phase's modules | `git grep --untracked -n -E 'pragma: no cover\|noqa' -- src/docket/reminders.py` |
| Q7 | Planner reads no clock, ID, settings, store, files, environment, local zone or sleep | `git grep --untracked -n -E 'clock\.now\(\|ids\.new_id\(\|get_settings\(\|os\.environ\|getenv\(\|open\(\|connect\(\|Store\(\|localtime\(\|astimezone\(\|time\.sleep\(' -- src/docket/reminders.py` |

(In the table, `\|` is a `|` in the command.)

## 6. Reasonable variations

These are correct even though the spec does not spell them out:

- Private helper organization and sorting implementation may vary while producing the exact frozen record, tuple, ordering, offsets, refusal and purity contracts. Arithmetic may use equivalent timedelta expressions.
- Extra meaningful edge tests stay in tests/unit/test_reminder_plan_edges.py. No persistence, sends, IDs, fake notifier API, task wiring, digest or new generic continuation is approved. No live integration is required.

## 7. Verdict

Write `docs/reviews/phase-03a-reminder-planning.md` in the form `docs/phase-conventions.md` gives (`# Review: Phase 3a`), then run `.venv/bin/python scripts/check_reports.py --phase 3a`; it must print `Reports OK.`
