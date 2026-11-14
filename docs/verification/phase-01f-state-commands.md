# Verification guide: Phase 1f (State commands)

Spec: `docs/phases/phase-01f-state-commands.md`. Follow `docs/phase-conventions.md` ("For the verifier"). Never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor, never read the Keychain, and never open the real data folder.

## 1. Coder ran

Stop with FAIL ("the coder did not run") if any of these is missing:


- `grep -c "^## Phase 1f: " docs/progress.md` prints `1`

Stop with FAIL ("the coder stopped") if that entry's first `Follow-ups` line starts with `Stopped:`, as "A stopped coder" in `docs/phase-conventions.md` says. With no entry, `git status --short` tells "the coder did not run" (no Scope path changed) from "the coder broke off without reporting" (Scope paths changed; name them under `For the architect`).

Stop with FAIL ("the baseline is not committed") if `git ls-files --error-unmatch docs/phases/phase-01f-state-commands.md tests/unit/test_views_changes.py tests/e2e/test_cli_states.py docs/verification/probe-01f.py` fails: the diff gates can only be judged against a committed spec and given files.

## 2. Gates

Run each from the repository root, in this order. Given test count: 52.

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_views_changes.py --ignore=tests/e2e/test_cli_states.py` | at least 414 passed, 0 failed (the coder's `*_more.py` tests add to the count) |
| G2 | `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 466 passed, 0 failed, 0 skipped |
| G3 | `.venv/bin/python -m pytest tests/unit/test_views_changes.py tests/e2e/test_cli_states.py --no-cov -q` | `52 passed` |
| G4 | `.venv/bin/python -m coverage report --include=src/docket/views.py,src/docket/cli.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| G5 | `.venv/bin/python docs/verification/probe-01f.py` | last line `FAILURES 0` |
| G6 | `grep -c "^## Phase 1f: " docs/progress.md` | `1` |
| G7 | `.venv/bin/python scripts/check_reports.py --phase 1f` | `Reports OK.` |
| G8 | `git diff HEAD --stat -- tests/unit/test_views_changes.py tests/e2e/test_cli_states.py docs/verification/probe-01f.py` | no output |
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
| S1 | `views.py` | ignore `changed` and always write the verb sentence | `tests/unit/test_views_changes.py::test_a_change_reads_as_a_sentence[already-done]` | `'t3 is already done.'` | `'Done t3: Pay rent'` |
| S2 | `views.py` | name the action's target state instead of the task's stored state | `tests/unit/test_views_changes.py::test_a_change_reads_as_a_sentence[reopen-while-in-progress]` | `'t3 is already in progress.'` | `'t3 is already open.'` |
| S3 | `cli.py` | pass `actor="agent"` | `tests/e2e/test_cli_states.py::test_a_state_change_is_yours_and_recorded[start]` | last audit row `('start', 'owner')` | `('start', 'agent')` |
| S4 | `cli.py` | exit 1 when nothing changed | `tests/e2e/test_cli_states.py::test_a_repeat_says_so_and_writes_nothing[done]` | exit 0 | exit 1 |
| S5 | `cli.py` | call `refusal_text(code)` without the id | `tests/e2e/test_cli_states.py::test_a_change_to_an_ended_task_is_refused[start-done]` | `'Task t1 has ended; reopen it first.'` | `'That task has ended; reopen it first.'` |
| S6 | `cli.py` | skip the shared start (the zone check) in the state commands | `tests/e2e/test_cli_states.py::test_every_state_command_needs_your_time_zone[done]` | `'DOCKET_TIME_ZONE is not set'` | `'There is no task t1.'` (and the database file is made) |
| S7 | `cli.py` | read `clock.now()` in a state command before calling the core | `tests/e2e/test_cli_states.py::test_a_state_command_reads_only_the_cores_clock[done]` | exit 0 | exit 1 (the core's read raises `StopIteration`) |
| S8 | `cli.py` | in `add`, show the due line against `clock.now()` instead of `created_at` | `tests/e2e/test_cli_states.py::test_adding_with_a_deadline_reads_only_the_cores_clock` | exit 0 | exit 1 (`StopIteration`) |
| S9 | `cli.py` | print a refusal to stdout | `tests/e2e/test_cli_states.py::test_an_unknown_task_is_refused[missing-done]` | stdout `''` | stdout `'There is no task t9.\n'` |

## 4. Probe

Run `.venv/bin/python docs/verification/probe-01f.py` from the repository root. It is a given file: do not edit it. Every line must end in `ok`; the last line must be `FAILURES 0`. A stop at the probe's own `assert` lines, before its self-check prints `ok`, is the probe's fault: report it under "For the architect", not as a finding. The probe uses temporary folders for `HOME` and the data folder and touches no network or Keychain.

It checks what the given tests do not reach: 600 random `start`, `done`, `cancel` and `reopen` commands over five tasks (titles with an emoji, a leading dash, 100 characters, an id-like title) and malformed ids, each answer compared with the probe's own transition table and sentences, with exactly one clock read per command on a known task and the stored state and audit rows checked after each. Each kind of answer (changed, repeat, ended, unknown) is reached at least 20 times.

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

- One private helper that the four commands call with their action, or four bodies.
- `change_text` with dicts for the verbs and the state words, or `match`.
- The four commands registered with `@tasks_app.command()` and their names as function names, or with explicit names.
- Private helpers inside the Scope modules, and extra behaviour tests in `*_more.py` files.

## 7. Verdict

Write `docs/reviews/phase-01f-state-commands.md` in the form `docs/phase-conventions.md` gives (`# Review: Phase 1f`), then run `.venv/bin/python scripts/check_reports.py --phase 1f`; it must print `Reports OK.`
