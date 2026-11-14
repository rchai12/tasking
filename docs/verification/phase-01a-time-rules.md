# Verification guide: Phase 1a (Time rules)

Spec: `docs/phases/phase-01a-time-rules.md`. Follow `docs/phase-conventions.md` ("For the verifier"). Never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor, never read the Keychain, and never open the real data folder.

## 1. Coder ran

Stop with FAIL ("the coder did not run") if any of these is missing:

- `src/docket/deadlines.py`
- `grep -c "^## Phase 1a: " docs/progress.md` prints `1`

Stop with FAIL ("the baseline is not committed") if `git ls-files --error-unmatch docs/phases/phase-01a-time-rules.md tests/unit/test_deadlines.py scripts/critical_modules.txt docs/verification/probe-01a.py` fails: the diff gates can only be judged against a committed spec and given files.

## 2. Gates

Run each from the repository root, in this order. Given test count: 56.

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_deadlines.py` | at least 96 passed, 0 failed (the coder's `*_more.py` tests add to the count) |
| G2 | `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 152 passed, 0 failed, 0 skipped |
| G3 | `.venv/bin/python -m pytest tests/unit/test_deadlines.py --no-cov -q` | `56 passed` |
| G4 | `.venv/bin/python -m coverage report --include=src/docket/deadlines.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| G5 | `.venv/bin/python docs/verification/probe-01a.py` | last line `FAILURES 0` |
| G6 | `grep -c "^## Phase 1a: " docs/progress.md` | `1` |
| G7 | `.venv/bin/python scripts/check_reports.py --phase 1a` | `Reports OK.` |
| G8 | `git diff HEAD --stat -- tests/unit/test_deadlines.py scripts/critical_modules.txt docs/verification/probe-01a.py` | no output |
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
| S1 | `deadlines.py` | turn wall times into instants with `fold=1` instead of `fold=0` | `tests/unit/test_deadlines.py::test_a_deadline_is_a_utc_instant_in_its_zone[repeated-time-is-the-first]` | `at` 05:30 UTC | `at` 06:30 UTC |
| S2 | `deadlines.py` | use 23:59 instead of `DEFAULT_TIME` when no time is given | `tests/unit/test_deadlines.py::test_a_deadline_is_a_utc_instant_in_its_zone[date-only]` | `at` 2026-11-20 22:00 UTC | `at` 2026-11-21 04:59 UTC |
| S3 | `deadlines.py` | set `time_given` to true always | `tests/unit/test_deadlines.py::test_a_deadline_is_a_utc_instant_in_its_zone[date-only]` | `time_given` False | True |
| S4 | `deadlines.py` | accept a zone when `ZoneInfo(name)` loads, instead of the exact-name check, in every place the zone is checked | `tests/unit/test_deadlines.py::test_an_unknown_zone_is_refused[lower-case]` | `DeadlineError` | no exception |
| S5 | `deadlines.py` | in `status`, make due include the end of the window (`<=` instead of `<`) | `tests/unit/test_deadlines.py::test_status_comes_from_the_deadline_and_now[thirty-minutes-after]` | `'overdue'` | `'due'` |
| S6 | `deadlines.py` | in `status`, call the deadline's own instant upcoming (`<=` instead of `<`) | `tests/unit/test_deadlines.py::test_status_comes_from_the_deadline_and_now[at-the-deadline]` | `'due'` | `'upcoming'` |
| S7 | `deadlines.py` | refuse an end equal to midnight (`>=` instead of `>`) | `tests/unit/test_deadlines.py::test_a_work_time_is_a_start_and_a_length[ends-at-midnight]` | a `WorkTime` | `DeadlineError` (`WORK_DAY_MESSAGE`) |
| S8 | `deadlines.py` | take midnight as the day's 00:00 instant plus 24 hours | `tests/unit/test_deadlines.py::test_a_work_time_ends_by_midnight[spring-forward-day-is-shorter]` | `DeadlineError` (`WORK_DAY_MESSAGE`) | a `WorkTime` ending 04:30 UTC |
| S9 | `deadlines.py` | compare the work time's start, not its end, with the deadline | `tests/unit/test_deadlines.py::test_a_work_time_ends_by_the_deadline[a-minute-late]` | `DeadlineError` (`WORK_DEADLINE_MESSAGE`) | a `WorkTime` |
| S10 | `deadlines.py` | check the deadline before midnight | `tests/unit/test_deadlines.py::test_the_first_broken_rule_is_reported[midnight-first]` | `WORK_DAY_MESSAGE` | `WORK_DEADLINE_MESSAGE` |
| S11 | `deadlines.py` | drop `Deadline`'s UTC check | `tests/unit/test_deadlines.py::test_a_stored_instant_must_be_utc[naive]` | `DeadlineError` (`INSTANT_MESSAGE`) | no exception from `Deadline` |
| S12 | `deadlines.py` | drop `WorkTime`'s length check (keep `make_work_time`'s) | `tests/unit/test_deadlines.py::test_a_stored_work_time_keeps_the_length_rule[too-short]` | `DeadlineError` (`WORK_LENGTH_MESSAGE`) | no exception |
| S13 | `deadlines.py` | ignore seconds in a time | `tests/unit/test_deadlines.py::test_a_time_is_hours_and_minutes_only[seconds]` | `DeadlineError` (`TIME_MESSAGE`) | no exception |

## 4. Probe

Run `.venv/bin/python docs/verification/probe-01a.py` from the repository root. It is a given file: do not edit it. Every line must end in `ok`; the last line must be `FAILURES 0`. A stop at the probe's own `assert` lines, before its self-check prints `ok`, is the probe's fault: report it under "For the architect", not as a finding. It reads no clock, network, Keychain or data folder, and takes a few seconds.

It checks what the given tests do not reach: `make_deadline` against its own offset-based oracle (never `fold`) on every half hour of each change day in 2026 and 2027 in nine zones, among them Lord Howe's 30-minute change, Santiago's change at midnight and Chatham's 45-minute offset; 17:00 for date-only deadlines on 500 random days; 4000 work times against the length, midnight and deadline rules, with each outcome reached at least 20 times; `status` from any zone; and fuzzed zone names, which are refused with the zone message only, or accepted only when they are exact names that load.

## 5. Searches

Each prints nothing. A match is a finding against the rule it names.

| # | Rule | Command |
|---|---|---|
| Q1 | no network code | `git grep --untracked -n -E 'import (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)\|from (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)' -- src` |
| Q2 | no output or logging outside the CLI | `git grep --untracked -n -E 'print\(\|logging\|logger\|warnings\.warn' -- src ':!src/docket/cli.py'` |
| Q3 | time read only in `clock.py`, through the module | `git grep --untracked -n -E 'datetime\.now\|datetime\.utcnow\|date\.today\|time\.time\(\|from docket\.(clock\|ids) import' -- src ':!src/docket/clock.py'` |
| Q4 | the time rules are pure: no project import, settings, environment or machine zone | `git grep --untracked -n -E '(from\|import) docket\|get_settings\(\|os\.environ\|getenv\(\|localtime\(\|astimezone\(\)' -- src/docket/deadlines.py` |
| Q5 | no model client | `git grep --untracked -n -E 'ollama\|anthropic\|openai\|langchain' -- src` |
| Q6 | no coverage or lint exclusions in the critical module | `git grep --untracked -n -E 'pragma: no cover\|noqa' -- src/docket/deadlines.py` |

(In the table, `\|` is a `|` in the command.)

## 6. Reasonable variations

These are correct even though the spec does not spell them out:

- The zone check as a cached `frozenset` of `available_timezones()`, built at import or on first use.
- `datetime.combine(day, at, tzinfo=ZoneInfo(zone))` or `datetime(..., tzinfo=...)`, with `fold=0` written out or left as the default.
- Midnight from `datetime.combine(day + timedelta(days=1), time(0), ...)`, or from the next day's date by any means that applies the wall-time rule.
- The checks in `__post_init__`, or in a shared private helper called from it; `make_work_time` building the `WorkTime` before or after its own length check, as long as the order of messages holds.
- `status` returning plain strings or `str` constants; `Literal` in the hint.
- `minutes` not an `int` (a float, a string) raising `TypeError` or `DeadlineError`: the spec sets no rule for it.
- Private helpers inside the Scope modules, and extra behaviour tests in `*_more.py` files.

## 7. Verdict

Write `docs/reviews/phase-01a-time-rules.md` in the form `docs/phase-conventions.md` gives (`# Review: Phase 1a`), then run `.venv/bin/python scripts/check_reports.py --phase 1a`; it must print `Reports OK.`
