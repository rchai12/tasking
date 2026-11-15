# Verification guide: Phase 2b (Intake rules)

Spec: `docs/phases/phase-02b-intake-rules.md`. Follow `docs/phase-conventions.md` ("For the verifier"). Never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor, never read the Keychain, and never open the real data folder.

## 1. Coder ran

Stop with FAIL ("the coder did not run") if any of these is missing:

- `src/docket/intake.py`
- `grep -c "^## Phase 2b: " docs/progress.md` prints `1`

Stop with FAIL ("the coder stopped") if that entry's first `Follow-ups` line starts with `Stopped:`, as "A stopped coder" in `docs/phase-conventions.md` says. With no entry, `git status --short` tells "the coder did not run" (no Scope path changed) from "the coder broke off without reporting" (Scope paths changed; name them under `For the architect`).

Stop with FAIL ("the baseline is not committed") if `git ls-files --error-unmatch docs/phases/phase-02b-intake-rules.md tests/integration/test_intake.py scripts/critical_modules.txt docs/verification/probe-02b.py` fails: the diff gates can only be judged against a committed spec and given files.

## 2. Gates

Run each from the repository root, in this order. Given test count: 55.

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_intake.py` | at least 579 passed, 0 failed (the coder's `*_more.py` tests add to the count) |
| G2 | `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 634 passed, 0 failed, 0 skipped |
| G3 | `.venv/bin/python -m pytest tests/integration/test_intake.py --no-cov -q` | `55 passed` |
| G4 | `.venv/bin/python -m coverage report --include=src/docket/intake.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| G5 | `.venv/bin/python docs/verification/probe-02b.py` | last line `FAILURES 0` |
| G6 | `grep -c "^## Phase 2b: " docs/progress.md` | `1` |
| G7 | `.venv/bin/python scripts/check_reports.py --phase 2b` | `Reports OK.` |
| G8 | `git diff HEAD --stat -- tests/integration/test_intake.py scripts/critical_modules.txt docs/verification/probe-02b.py` | no output |
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
| S1 | `intake.py` | accept keys up to 201 characters | `tests/integration/test_intake.py::test_a_missing_or_overlong_key_answers_400[too-long]` | `Answer(400, {'error': 'missing_key'})` | `Answer(422, {'error': 'invalid_key'})` (the core's own check) |
| S2 | `intake.py` | allow fields beyond the six | `tests/integration/test_intake.py::test_an_invalid_task_answers_422_and_writes_nothing[extra-field]` | `Answer(422, {'error': 'invalid_body'})` | `StopIteration` (the core's clock read; the test gives no moment) |
| S3 | `intake.py` | drop the check that the text fields are strings | `tests/integration/test_intake.py::test_an_invalid_task_answers_422_and_writes_nothing[provider-a-list]` | `Answer(422, {'error': 'invalid_body'})` | `TypeError` (unhashable list in the core) |
| S4 | `intake.py` | read the date with `date.fromisoformat` alone, without the shape pattern | `tests/integration/test_intake.py::test_an_invalid_task_answers_422_and_writes_nothing[compact-date]` | `Answer(422, {'error': 'invalid_deadline'})` | `StopIteration` |
| S5 | `intake.py` | read the time with `time.fromisoformat` alone, without the shape pattern | `tests/integration/test_intake.py::test_an_invalid_task_answers_422_and_writes_nothing[time-with-seconds]` | `Answer(422, {'error': 'invalid_deadline'})` | `StopIteration` |
| S6 | `intake.py` | call the core before checking the deadline | `tests/integration/test_intake.py::test_an_invalid_task_answers_422_and_writes_nothing[deadline-before-title]` | `'invalid_deadline'` | `'invalid_title'` |
| S7 | `intake.py` | answer 201 whether or not the core made something | `tests/integration/test_intake.py::test_a_repeat_answers_200_with_the_same_id` | `Answer(200, {'id': 't1'})` | `Answer(201, {'id': 't1'})` |
| S8 | `intake.py` | answer `key_reused` with 422 | `tests/integration/test_intake.py::test_a_reused_key_answers_409` | `Answer(409, ...)` | `Answer(422, ...)` |
| S9 | `intake.py` | check a link's body before its task | `tests/integration/test_intake.py::test_a_link_follows_the_fakes_order` | first answer `Answer(404, {'error': 'unknown_task'})` | `Answer(422, {'error': 'invalid_body'})` |
| S10 | `intake.py` | drop the link's `source == "email"` check | `tests/integration/test_intake.py::test_an_invalid_link_writes_nothing[source-agent]` | `Answer(422, {'error': 'invalid_source'})` | `StopIteration` (the core's clock read; the one moment went to the task) |
| S11 | `intake.py` | add the refused field's value to an error body | `tests/integration/test_intake.py::test_answers_never_echo_the_request` | bodies with only `error` | a second key in the body |
| S12 | `intake.py` | pass the request to the core without its `deadline` | `tests/integration/test_intake.py::test_an_approved_email_task_is_created[date-and-time]` | the stored request equals the body | the stored request lacks `deadline` |

Each row was traced with the test's clock list (S2, S4, S5 and S10 reach the core's clock read with no moment left) and with the core as a layer (S1 reaches the core's own key check, S3 the core's unhashable comparison).

## 4. Probe

Run `.venv/bin/python docs/verification/probe-02b.py` from the repository root. It is a given file: do not edit it. Every line must end in `ok`; the last line must be `FAILURES 0`. A stop at the probe's own `assert` lines, before its self-check prints `ok`, is the probe's fault: report it under "For the architect", not as a finding. It touches no network, Keychain or real data folder.

It checks what the given tests do not reach: 1500 task and link bodies fuzzed one change at a time from the real payload (a field dropped, added or given another JSON type; dates, times and zones good and bad, wrong-case zones included; titles, sources and references), sent with fresh, repeated and reused keys, missing and overlong keys, known, unknown and malformed task ids, each answer compared with the probe's own rules in the spec's order, with every 201 and 200 checked against the stored task; and 300 valid deadlines in four zones stored exactly as `make_deadline` makes them. Every status is reached at least 15 times.

## 5. Searches

Each prints nothing. A match is a finding against the rule it names.

| # | Rule | Command |
|---|---|---|
| Q1 | no network code | `git grep --untracked -n -E 'import (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)\|from (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)' -- src` |
| Q2 | no output outside the CLI | `git grep --untracked -n -E 'print\(\|logging\|logger\|warnings\.warn' -- src ':!src/docket/cli.py'` |
| Q3 | time read only in `clock.py`, through the module | `git grep --untracked -n -E 'datetime\.now\|datetime\.utcnow\|date\.today\|time\.time\(\|from docket\.(clock\|ids) import' -- src ':!src/docket/clock.py'` |
| Q4 | only the core writes tasks, audit rows, links and keys | `git grep --untracked -n -E '\.(insert_task\|update_task\|append_audit\|insert_link\|insert_request_key)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'` |
| Q5 | no model client | `git grep --untracked -n -E 'ollama\|anthropic\|openai\|langchain' -- src` |
| Q6 | no coverage or lint exclusions in this phase's modules | `git grep --untracked -n -E 'pragma: no cover\|noqa' -- src/docket/intake.py` |
| Q7 | intake has no HTTP, settings, environment or clock of its own | `git grep --untracked -n -E 'fastapi\|starlette\|uvicorn\|os\.environ\|getenv\(\|get_settings\(\|clock\.now' -- src/docket/intake.py` |

(In the table, `\|` is a `|` in the command.)

## 6. Reasonable variations

These are correct even though the spec does not spell them out:

- The shape checks as small private helpers, or one function returning the first code; the patterns compiled once.
- `accept_task` building the deadline with `make_deadline` and catching `DeadlineError` for `invalid_deadline`.
- Mapping `CoreError` codes to statuses with a dict.
- `Answer.body` built fresh for each answer.
- Private helpers inside the Scope modules, and extra behaviour tests in `*_more.py` files.

## 7. Verdict

Write `docs/reviews/phase-02b-intake-rules.md` in the form `docs/phase-conventions.md` gives (`# Review: Phase 2b`), then run `.venv/bin/python scripts/check_reports.py --phase 2b`; it must print `Reports OK.`
