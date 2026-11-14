# Verification guide: Phase 1e (Adding and listing tasks)

Spec: `docs/phases/phase-01e-adding-and-listing.md`. Follow `docs/phase-conventions.md` ("For the verifier"). Never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor, never read the Keychain, and never open the real data folder.

## 1. Coder ran

Stop with FAIL ("the coder did not run") if any of these is missing:


- `grep -c "^## Phase 1e: " docs/progress.md` prints `1`

Stop with FAIL ("the coder stopped") if that entry's first `Follow-ups` line starts with `Stopped:`, as "A stopped coder" in `docs/phase-conventions.md` says. With no entry, `git status --short` tells "the coder did not run" (no Scope path changed) from "the coder broke off without reporting" (Scope paths changed; name them under `For the architect`).

Stop with FAIL ("the baseline is not committed") if `git ls-files --error-unmatch docs/phases/phase-01e-adding-and-listing.md tests/unit/test_views_tasks.py tests/e2e/test_cli_tasks.py docs/verification/probe-01e.py` fails: the diff gates can only be judged against a committed spec and given files.

## 2. Gates

Run each from the repository root, in this order. Given test count: 66.

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python -m pytest --no-cov -q --ignore=tests/e2e/test_cli_tasks.py --ignore=tests/unit/test_views_tasks.py` | at least 345 passed, 0 failed (the coder's `*_more.py` tests add to the count) |
| G2 | `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 411 passed, 0 failed, 0 skipped |
| G3 | `.venv/bin/python -m pytest tests/unit/test_views_tasks.py tests/e2e/test_cli_tasks.py --no-cov -q` | `66 passed` |
| G4 | `.venv/bin/python -m coverage report --include=src/docket/views.py,src/docket/cli.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| G5 | `.venv/bin/python docs/verification/probe-01e.py` | last line `FAILURES 0` |
| G6 | `grep -c "^## Phase 1e: " docs/progress.md` | `1` |
| G7 | `.venv/bin/python scripts/check_reports.py --phase 1e` | `Reports OK.` |
| G8 | `git diff HEAD --stat -- tests/unit/test_views_tasks.py tests/e2e/test_cli_tasks.py docs/verification/probe-01e.py` | no output |
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
| S1 | `cli.py` | check `--due` with `date.fromisoformat` alone, without the shape pattern | `tests/e2e/test_cli_tasks.py::test_a_refused_add_writes_nothing[compact-date]` | exit 1, `DUE_MESSAGE` | exit 0, `Added t1: ...` |
| S2 | `cli.py` | check `--at` with `time.fromisoformat` alone, without the shape pattern | `tests/e2e/test_cli_tasks.py::test_a_refused_add_writes_nothing[compact-time]` | exit 1, `AT_MESSAGE` | exit 0, `Added t1: ...` |
| S3 | `cli.py` | drop the `--at needs --due` check | `tests/e2e/test_cli_tasks.py::test_a_refused_add_writes_nothing[at-without-due]` | exit 1, `AT_WITHOUT_DUE_MESSAGE` | exit 0, `Added t1: Pay rent` |
| S4 | `cli.py` | check `--at` before `--due` | `tests/e2e/test_cli_tasks.py::test_a_refused_add_writes_nothing[date-checked-before-time]` | `DUE_MESSAGE` | `AT_MESSAGE` |
| S5 | `cli.py` | list every task by default, as with `--all` | `tests/e2e/test_cli_tasks.py::test_the_list_shows_open_work_soonest_first` | 4 lines | 6 lines |
| S6 | `cli.py` | sort undated tasks first | `tests/e2e/test_cli_tasks.py::test_the_list_shows_open_work_soonest_first` | first line `t3 ...` | first line `t1 ...` |
| S7 | `cli.py` | break a deadline tie by title instead of id | `tests/e2e/test_cli_tasks.py::test_tasks_with_one_deadline_keep_their_id_order` | `['t1', 't2', 't3']` | `['t2', 't3', 't1']` |
| S8 | `cli.py` | open the store before checking the zone | `tests/e2e/test_cli_tasks.py::test_every_task_command_needs_your_time_zone[unset-list]` | no `docket.sqlite3` | the file exists |
| S9 | `cli.py` | print a refusal to stdout instead of stderr | `tests/e2e/test_cli_tasks.py::test_showing_an_unknown_task_is_refused[missing]` | stdout `''` | stdout `'There is no task t9.\n'` |
| S10 | `cli.py` | exit 0 after a refusal | `tests/e2e/test_cli_tasks.py::test_showing_an_unknown_task_is_refused[missing]` | exit 1 | exit 0 |
| S11 | `cli.py` | in `add`, read the clock for the display instead of using `created_at` | `tests/e2e/test_cli_tasks.py::test_listing_and_showing_read_the_clock_once` | `'Added t7: One more\n'` | `''` (the second clock read raises `StopIteration`) |
| S12 | `views.py` | join the padded id to the status with no space | `tests/unit/test_views_tasks.py::test_a_task_line[long-id]` | `'t12345 in progress, overdue  ...'` | `'t12345in progress, overdue  ...'` |
| S13 | `views.py` | write a `Link:` line for every task | `tests/unit/test_views_tasks.py::test_the_source_line[agent]` | 7 lines | 8 lines |
| S14 | `views.py` | ignore the id in `refusal_text` | `tests/unit/test_views_tasks.py::test_every_refusal_reads_as_a_sentence[unknown]` | `'There is no task t9.'` | `'There is no such task.'` |

No row checks the ASCII-digit rule of the shape patterns: a `\d` pattern accepts full-width digits, but `date.fromisoformat` and `time.fromisoformat` refuse them anyway, so no test can tell the two apart. The `fullwidth-digits` row stays as a guard.

## 4. Probe

Run `.venv/bin/python docs/verification/probe-01e.py` from the repository root. It is a given file: do not edit it. Every line must end in `ok`; the last line must be `FAILURES 0`. A stop at the probe's own `assert` lines, before its self-check prints `ok`, is the probe's fault: report it under "For the architect", not as a finding. The probe uses temporary folders for `HOME` and the data folder and touches no network or Keychain.

It checks what the given tests do not reach: 1500 random `tasks add` calls mixing valid and invalid dates (leap days, full-width digits, trailing spaces), times and titles, each judged by the probe's own shape rules and check order, with every added task's deadline compared with `make_deadline`; and 30 random sets of up to 24 tasks in four zones, where `list` and `list --all` must equal the probe's own sort of `task_line`s and `show` must equal `task_detail` for every task. Each kind of add outcome is reached at least 20 times.

## 5. Searches

Each prints nothing. A match is a finding against the rule it names.

| # | Rule | Command |
|---|---|---|
| Q1 | no network code | `git grep --untracked -n -E 'import (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)\|from (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)' -- src` |
| Q2 | no output outside the CLI | `git grep --untracked -n -E 'print\(\|logging\|logger\|warnings\.warn' -- src ':!src/docket/cli.py'` |
| Q3 | time read only in `clock.py`, through the module | `git grep --untracked -n -E 'datetime\.now\|datetime\.utcnow\|date\.today\|time\.time\(\|from docket\.(clock\|ids) import' -- src ':!src/docket/clock.py'` |
| Q4 | the commands write only through the core | `git grep --untracked -n -E '\.(insert_task\|update_task\|append_audit)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'` |
| Q5 | no environment, machine zone or locale in the commands and views | `git grep --untracked -n -E 'os\.environ\|getenv\(\|strftime\(\|import locale' -- src/docket/cli.py src/docket/views.py` |
| Q6 | no model client | `git grep --untracked -n -E 'ollama\|anthropic\|openai\|langchain' -- src` |
| Q7 | no coverage or lint exclusions in this phase's modules | `git grep --untracked -n -E 'pragma: no cover\|noqa' -- src/docket/cli.py src/docket/views.py` |

(In the table, `\|` is a `|` in the command.)

## 6. Reasonable variations

These are correct even though the spec does not spell them out:

- `typer.Option` or `Annotated[...]` parameters; `print(..., file=sys.stderr)` or `typer.echo(..., err=True)`; `raise typer.Exit(1)`.
- One private helper for the shared start (settings, zone) and one for refusing; the store opened with a `with` block.
- The shape patterns compiled once at import, with `fullmatch`, before `fromisoformat`.
- Sorting with one key tuple, or two lists joined; the id's number from `int(task.id[1:])`.
- The `list` command defined as a function with another Python name (`list_`) and registered with the name `list`.
- Private helpers inside the Scope modules, and extra behaviour tests in `*_more.py` files.

## 7. Verdict

Write `docs/reviews/phase-01e-adding-and-listing.md` in the form `docs/phase-conventions.md` gives (`# Review: Phase 1e`), then run `.venv/bin/python scripts/check_reports.py --phase 1e`; it must print `Reports OK.`
