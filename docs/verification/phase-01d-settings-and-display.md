# Verification guide: Phase 1d (Settings and display text)

Spec: `docs/phases/phase-01d-settings-and-display.md`. Follow `docs/phase-conventions.md` ("For the verifier"). Never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor, never read the Keychain, and never open the real data folder.

## 1. Coder ran

Stop with FAIL ("the coder did not run") if any of these is missing:

- `src/docket/views.py`
- `grep -c "^## Phase 1d: " docs/progress.md` prints `1`

Stop with FAIL ("the baseline is not committed") if `git ls-files --error-unmatch docs/phases/phase-01d-settings-and-display.md tests/unit/test_settings.py tests/unit/test_views.py docs/verification/probe-01d.py` fails: the diff gates can only be judged against a committed spec and given files.

## 2. Gates

Run each from the repository root, in this order. Given test count: 54.

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_settings.py --ignore=tests/unit/test_views.py` | at least 291 passed, 0 failed (the coder's `*_more.py` tests add to the count) |
| G2 | `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 345 passed, 0 failed, 0 skipped |
| G3 | `.venv/bin/python -m pytest tests/unit/test_settings.py tests/unit/test_views.py --no-cov -q` | `54 passed` |
| G4 | `.venv/bin/python -m coverage report --include=src/docket/config.py,src/docket/views.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| G5 | `.venv/bin/python docs/verification/probe-01d.py` | last line `FAILURES 0` |
| G6 | `grep -c "^## Phase 1d: " docs/progress.md` | `1` |
| G7 | `.venv/bin/python scripts/check_reports.py --phase 1d` | `Reports OK.` |
| G8 | `git diff HEAD --stat -- tests/unit/test_settings.py tests/unit/test_views.py docs/verification/probe-01d.py` | no output |
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
| S1 | `views.py` | take day and month names from `strftime("%a")` and `strftime("%b")` | `tests/unit/test_views.py::test_when_is_english_whatever_the_locale` | `'Fri Nov 20 17:00 EST'` | `'ven. nov. 20 17:00 EST'` |
| S2 | `views.py` | write the day of the month with a leading zero | `tests/unit/test_views.py::test_when_names_the_day_time_and_zone[next-year]` | `'Fri Jan 8 2027 17:00 EST'` | `'Fri Jan 08 2027 17:00 EST'` |
| S3 | `views.py` | compare with `now`'s year in UTC, not in the zone | `tests/unit/test_views.py::test_when_names_the_day_time_and_zone[still-last-year-here]` | `'Fri Jan 1 2027 10:00 EST'` | `'Fri Jan 1 10:00 EST'` |
| S4 | `views.py` | take `at`'s year in UTC, not in the zone | `tests/unit/test_views.py::test_when_names_the_day_time_and_zone[already-next-year-in-utc]` | `'Thu Dec 31 22:00 EST'` | `'Thu Dec 31 2027 22:00 EST'` |
| S5 | `views.py` | drop the `where set` part of `deadline_text` | `tests/unit/test_views.py::test_a_deadline_in_your_zone_and_where_it_was_set[set-elsewhere]` | `'Fri Nov 20 17:00 EST (Sat Nov 21 07:00 JST where set)'` | `'Fri Nov 20 17:00 EST'` |
| S6 | `views.py` | drop `, no time given` | `tests/unit/test_views.py::test_a_deadline_in_your_zone_and_where_it_was_set[no-time-given]` | `'Fri Nov 20 17:00 EST, no time given'` | `'Fri Nov 20 17:00 EST'` |
| S7 | `views.py` | in a span, always keep the start's abbreviation | `tests/unit/test_views.py::test_a_work_time_as_a_span[one-hour]` | `'Fri Nov 20 14:00 to 15:00 EST'` | `'Fri Nov 20 14:00 EST to 15:00 EST'` |
| S8 | `views.py` | compare the span's dates in UTC, not in the zone | `tests/unit/test_views.py::test_a_work_time_as_a_span[to-midnight]` | `'Fri Nov 20 23:00 EST to Sat Nov 21 00:00 EST'` | `'Fri Nov 20 23:00 to 00:00 EST'` |
| S9 | `views.py` | in a span, ignore a change of abbreviation | `tests/unit/test_views.py::test_a_work_time_as_a_span[across-the-change]` | `'Sun Nov 1 00:30 EDT to 02:30 EST'` | `'Sun Nov 1 00:30 to 02:30 EST'` |
| S10 | `views.py` | add due and overdue to ended tasks too | `tests/unit/test_views.py::test_the_status_word[done-ignores-the-deadline]` | `'done'` | `'done, overdue'` |
| S11 | `config.py` | stop treating an empty zone as not set | `tests/unit/test_settings.py::test_the_time_zone_comes_from_the_environment[empty-is-unset]` | `None` | `ConfigError` (`TIME_ZONE_MESSAGE`) |
| S12 | `config.py` | accept a zone when `ZoneInfo(value)` loads, instead of the exact-name check | `tests/unit/test_settings.py::test_a_bad_time_zone_is_refused[lower-case]` | `ConfigError` | DID NOT RAISE |
| S13 | `config.py` | map every `ValidationError` to `DATA_DIR_MESSAGE`, as Phase 0 did | `tests/unit/test_settings.py::test_a_bad_work_length_is_refused[four]` | `'DOCKET_WORK_MINUTES must be 5 to 720'` | `'DOCKET_DATA_DIR must be an absolute path'` |
| S14 | `config.py` | allow 721 minutes | `tests/unit/test_settings.py::test_a_bad_work_length_is_refused[721]` | `ConfigError` | DID NOT RAISE |
| S15 | `config.py` | have `home_zone` return `"UTC"` when the setting is unset | `tests/unit/test_settings.py::test_home_zone_needs_the_setting` | `ConfigError` (`TIME_ZONE_UNSET_MESSAGE`) | DID NOT RAISE |
| S16 | `config.py` | report `work_minutes` before `time_zone` | `tests/unit/test_settings.py::test_the_first_bad_setting_is_reported[zone-before-length]` | `TIME_ZONE_MESSAGE` | `WORK_MINUTES_MESSAGE` |

## 4. Probe

Run `.venv/bin/python docs/verification/probe-01d.py` from the repository root. It is a given file: do not edit it. Every line must end in `ok`; the last line must be `FAILURES 0`. A stop at the probe's own `assert` lines, before its self-check prints `ok`, is the probe's fault: report it under "For the architect", not as a finding. The probe uses temporary folders for `HOME` and the data folder and touches no network or Keychain.

It checks what the given tests do not reach: `when` on 4000 random instants in ten zones (half-hour, 45-minute and 30-minute-daylight zones, a midnight change, a numeric abbreviation) under every locale installed among C, French, German, Japanese and Turkish, against the standard library's local time and a strict shape; `deadline_text` and `work_text` on 3000 random cases rebuilt from its own `when`; `status_text` on 2000 cases; and 400 fuzzed zone names and every work length from -3 to 729, accepted exactly when they should be, with the exact message otherwise. It needs at least two locales; C is always there.

## 5. Searches

Each prints nothing. A match is a finding against the rule it names.

| # | Rule | Command |
|---|---|---|
| Q1 | no network code | `git grep --untracked -n -E 'import (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)\|from (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)' -- src` |
| Q2 | no output or logging outside the CLI | `git grep --untracked -n -E 'print\(\|logging\|logger\|warnings\.warn' -- src ':!src/docket/cli.py'` |
| Q3 | time read only in `clock.py`, through the module | `git grep --untracked -n -E 'datetime\.now\|datetime\.utcnow\|date\.today\|time\.time\(\|from docket\.(clock\|ids) import' -- src ':!src/docket/clock.py'` |
| Q4 | the views are pure and never use the locale | `git grep --untracked -n -E 'strftime\(\|import locale\|from locale\|clock\.now\|get_settings\(\|os\.environ\|getenv\(' -- src/docket/views.py` |
| Q5 | nothing reads the machine's time zone | `git grep --untracked -n -E 'tzlocal\|time\.tzname\|localtime\(\|astimezone\(\)\|environ\[.TZ.\]' -- src` |
| Q6 | no model client | `git grep --untracked -n -E 'ollama\|anthropic\|openai\|langchain' -- src` |
| Q7 | no coverage or lint exclusions in this phase's modules | `git grep --untracked -n -E 'pragma: no cover\|noqa' -- src/docket/config.py src/docket/views.py` |

(In the table, `\|` is a `|` in the command.)

## 6. Reasonable variations

These are correct even though the spec does not spell them out:

- Day and month tables as tuples or lists; hours and minutes through an f-string format such as `{local:%H:%M}` (not a locale name) or `:02d`.
- The empty-to-`None` rule in a `mode="before"` validator; the zone check against a cached set of `available_timezones()`.
- `get_settings` choosing the message from the first error's `loc`, or from the fields in the spec's order.
- A private span helper shared by both halves of `work_text`.
- `status_text` calling `deadlines.status`, or comparing instants with `DUE_WINDOW` itself.
- Private helpers inside the Scope modules, and extra behaviour tests in `*_more.py` files.

## 7. Verdict

Write `docs/reviews/phase-01d-settings-and-display.md` in the form `docs/phase-conventions.md` gives (`# Review: Phase 1d`), then run `.venv/bin/python scripts/check_reports.py --phase 1d`; it must print `Reports OK.`
