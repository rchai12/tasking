# Verification guide: Phase 2e (Phase tooling)

Spec: `docs/phases/phase-02e-phase-tooling.md`. Follow `docs/phase-conventions.md` ("For the verifier"). Never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor, never read the Keychain, and never open the real data folder.

## 1. Coder ran

Stop with FAIL ("the coder did not run") if any of these is missing:

- `src/docket/acceptance.py`
- `src/docket/spotcheck.py`
- `scripts/accept.py`
- `scripts/spot_check.py`
- `scripts/progress.py`
- `grep -c "^## Phase 2e: " docs/progress.md` prints `1`

Stop with FAIL ("the coder stopped") if that entry's first `Follow-ups` line starts with `Stopped:`, as "A stopped coder" in `docs/phase-conventions.md` says. With no entry, `git status --short` tells "the coder did not run" (no Scope path changed) from "the coder broke off without reporting" (Scope paths changed; name them under `For the architect`).

Stop with FAIL ("the baseline is not committed") if `git ls-files --error-unmatch docs/phases/phase-02e-phase-tooling.md tests/unit/test_reports_put.py tests/unit/test_spotcheck.py tests/unit/test_acceptance.py tests/unit/test_check_quiet.py tests/unit/test_acceptance_script.py tests/unit/test_spotcheck_script.py tests/unit/test_progress_script.py tests/support.py tests/sections.toml scripts/critical_modules.txt docs/verification/probe-02e.py` fails: the diff gates can only be judged against a committed spec and given files.

## 2. Gates

Run each from the repository root, in this order. Given test count: 55.

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_reports_put.py --ignore=tests/unit/test_spotcheck.py --ignore=tests/unit/test_acceptance.py --ignore=tests/unit/test_check_quiet.py --ignore=tests/unit/test_acceptance_script.py --ignore=tests/unit/test_spotcheck_script.py --ignore=tests/unit/test_progress_script.py` | at least 732 passed, 0 failed (the coder's `*_more.py` tests add to the count) |
| G2 | `.venv/bin/python scripts/check.py --first tooling` | last line `All checks passed.`; summary lists `tests (tooling): passed`; at least 787 passed, 0 failed, 0 skipped |
| G3 | `.venv/bin/python -m pytest tests/unit/test_reports_put.py tests/unit/test_spotcheck.py tests/unit/test_acceptance.py tests/unit/test_check_quiet.py tests/unit/test_acceptance_script.py tests/unit/test_spotcheck_script.py tests/unit/test_progress_script.py --no-cov -q` | `55 passed` |
| G4 | `.venv/bin/python -m coverage report --include=src/docket/acceptance.py,src/docket/spotcheck.py,src/docket/reports.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| G5 | `.venv/bin/python docs/verification/probe-02e.py` | last line `FAILURES 0` |
| G6 | `grep -c "^## Phase 2e: " docs/progress.md` | `1` |
| G7 | `.venv/bin/python scripts/check_reports.py --phase 2e` | `Reports OK.` |
| G8 | `git diff HEAD --stat -- tests/unit/test_reports_put.py tests/unit/test_spotcheck.py tests/unit/test_acceptance.py tests/unit/test_check_quiet.py tests/unit/test_acceptance_script.py tests/unit/test_spotcheck_script.py tests/unit/test_progress_script.py tests/support.py tests/sections.toml scripts/critical_modules.txt docs/verification/probe-02e.py` | no output |
| G9 | `git status --short` | only the Scope paths |
| G10 | `.venv/bin/python -m pip list --format=freeze` | the same packages as before this phase: no new dependency |

## 3. Spot checks

For each row:
1. Copy the module outside the repository.
2. Make the change described in the module the coder wrote.
3. Run the deciding test with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest '<test>' --no-cov -q --tb=line`, and confirm it fails with the "Broken" value; rerun with `-vv` only when it doesn't.
4. Restore the module from your copy, delete `src/docket/__pycache__`, and confirm `git diff` is as before.

A different failure from the "Broken" column is a note, not a finding; a pass is a finding.

| # | Module | Change | Deciding test | Correct | Broken |
|---|---|---|---|---|---|
| S1 | `reports.py` | `put_entry` always appends, never replaces | `tests/unit/test_reports_put.py::test_the_phase_entry_is_replaced_in_place[last]` | one 2e entry, the new one | the old 2e entry kept and the new one appended after it |
| S2 | `reports.py` | skip the `parse_progress` check in `put_entry` | `tests/unit/test_reports_put.py::test_an_entry_out_of_form_is_refused[line-break]` | `ValueError` | DID NOT RAISE |
| S3 | `reports.py` | write an empty list as no lines instead of `  - None` | `tests/unit/test_reports_put.py::test_an_entry_is_written_in_the_progress_form` | `- Deviations:\n  - None` | `- Deviations:\n- Follow-ups:` |
| S4 | `spotcheck.py` | restore the module after `run()` returns instead of in a `finally` | `tests/unit/test_spotcheck.py::test_the_module_is_restored_when_the_run_raises` | the original module | `PORT = 9000` left in |
| S5 | `spotcheck.py` | take a failure's message from the `FAILED` summary line | `tests/unit/test_spotcheck.py::test_the_verdict_is_one_line[assertion]` | the whole assertion | a message ending `{'h...` |
| S6 | `spotcheck.py` | treat exit 4 as any other code | `tests/unit/test_spotcheck.py::test_the_verdict_is_one_line[unknown-test]` | `no test ran` | `error: exit 4` |
| S7 | `acceptance.py` | keep `\|` in a table command | `tests/unit/test_acceptance.py::test_a_guide_gives_its_labels_and_unescapes_pipes` | `... --format=freeze \| wc -l` | the command with a backslash before the pipe |
| S8 | `acceptance.py` | read past the next `## ` heading | `tests/unit/test_acceptance.py::test_a_spec_gives_its_acceptance_rows_and_searches` | six rows, ending `Q2` | a seventh, `Row('A5', 'git log')` |
| S9 | `acceptance.py` | show ` (exit 1)` for a `git grep` too | `tests/unit/test_acceptance.py::test_each_row_is_digested[search-silent]` | `Q1: empty` | `Q1: empty (exit 1)` |
| S10 | `acceptance.py` | no cut after `MAX_DETAIL` lines | `tests/unit/test_acceptance.py::test_long_details_are_cut_with_a_count` | `m19` then `... 5 more lines in the log` | `m19` to `m24`, no count line |
| S11 | `scripts/check.py` | print the `== <step>` lines with `--quiet` too | `tests/unit/test_check_quiet.py::test_a_quiet_run_prints_the_tables_and_the_summary` | output starting `Sections:` | output starting `== lint` |
| S12 | `scripts/check.py` | leave out the failing step's last lines | `tests/unit/test_check_quiet.py::test_a_quiet_failure_shows_the_last_lines_of_its_log` | output starting `Last 20 lines of` | output starting with an empty line, then `Summary:` |
| S13 | `scripts/spot_check.py` | drop the check that the module is under `src/` | `tests/unit/test_spotcheck_script.py::test_a_bad_change_runs_nothing[a-test-file]` | exit 2, nothing run | exit 1, the test run once (`passes`) |
| S14 | `scripts/accept.py` | run each command in the current folder instead of `--root` | `tests/unit/test_acceptance_script.py::test_the_spec_rows_run_from_the_root` | each call with the temporary root | each call with the folder pytest runs in |

## 4. Probe

Run `.venv/bin/python docs/verification/probe-02e.py` from the repository root. It is a given file: do not edit it. Every line must end in `ok`; the last line must be `FAILURES 0`. A stop at the probe's own `assert` lines, before its self-check prints `ok`, is the probe's fault: report it under "For the architect", not as a finding. It touches no network, Keychain or real data folder.

It checks that 600 random spot checks always leave the module as it was, that 300 random progress entries leave every other entry as it was, that every committed spec and guide gives its rows, that `accept.py` and `spot_check.py` work with their real runners on a temporary project, and that `check.py --quiet --section tooling` prints four lines.

## 5. Searches

Each prints nothing. A match is a finding against the rule it names.

| # | Rule | Command |
|---|---|---|
| Q1 | no network code | `git grep --untracked -n -E 'import (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)\|from (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)' -- src` |
| Q2 | no output outside the CLI | `git grep --untracked -n -E 'print\(\|logging\|logger\|warnings\.warn' -- src ':!src/docket/cli.py'` |
| Q3 | time read only in `clock.py`, through the module | `git grep --untracked -n -E 'datetime\.now\|datetime\.utcnow\|date\.today\|time\.time\(\|from docket\.(clock\|ids) import' -- src ':!src/docket/clock.py'` |
| Q4 | no model client | `git grep --untracked -n -E 'ollama\|anthropic\|openai\|langchain' -- src` |
| Q5 | no coverage or lint exclusions in this phase's modules | `git grep --untracked -n -E 'pragma: no cover\|noqa' -- src/docket/acceptance.py src/docket/spotcheck.py src/docket/reports.py` |
| Q6 | the tooling modules start no process; the scripts do | `git grep --untracked -n -E 'import subprocess\|from subprocess\|os\.system\|os\.popen' -- src` |

(In the table, `\|` is a `|` in the command.)

## 6. Reasonable variations

These are correct even though the spec does not spell them out:

- `put_entry` working on lines or on the text with a regular expression, as long as the given results hold.
- The `run` default of a script as a module-level function, or a parameter default of a lambda.
- `read_rows` with one loop or with separate table and code-block passes, keeping the document's order.
- A script's private helper for the padded phase id, or the id padded in place.
- `check.py`'s log names from a table or computed from the step, as long as they are the five given.
- Private helpers inside the Scope modules, and extra behaviour tests in `*_more.py` files.

## 7. Verdict

Write `docs/reviews/phase-02e-phase-tooling.md` in the form `docs/phase-conventions.md` gives (`# Review: Phase 2e`), then run `.venv/bin/python scripts/check_reports.py --phase 2e`; it must print `Reports OK.`
