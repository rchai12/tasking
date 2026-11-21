# Verification guide: Phase 6e (MCP edit tools)

Spec: `docs/phases/phase-06e-mcp-edit-tools.md`. Follow `docs/phase-conventions.md` ("For the verifier"). Never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor, never read the Keychain, and never open the real data folder.

## 1. Coder ran

Stop with FAIL ("the coder did not run") if any of these is missing:


- `grep -c "^## Phase 6e: " docs/progress.md` prints `1`

Stop with FAIL ("the coder stopped") if that entry's first `Follow-ups` line starts with `Stopped:`, as "A stopped coder" in `docs/phase-conventions.md` says. With no entry, `git status --short` tells "the coder did not run" (no Scope path changed) from "the coder broke off without reporting" (Scope paths changed; name them under `For the architect`).

Stop with FAIL ("the baseline is not committed") if `git ls-files --error-unmatch docs/phases/phase-06e-mcp-edit-tools.md tests/integration/test_core_edit_keys.py tests/integration/test_writes_edits.py tests/integration/test_mcp_edits.py tests/integration/test_mcp_writes.py docs/verification/probe-06d.py docs/verification/probe-06e.py` fails: the diff gates can only be judged against a committed spec and given files. If the coder's work is already committed (a commit after the spec's, and a clean tree), judge every `git diff HEAD` gate against the spec's commit instead (`git log --diff-filter=A --format=%h -1 -- docs/phases/phase-06e-mcp-edit-tools.md`), and the `git status --short` gate with `git diff <that commit> --name-status`.

## 2. Gates

Run each from the repository root, in this order: `.venv/bin/python scripts/accept.py --phase 6e --guide` runs them and the searches, one line each. Given test count: 74.

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_core_edit_keys.py --ignore=tests/integration/test_writes_edits.py --ignore=tests/integration/test_mcp_edits.py` | at least 1775 passed, 0 failed (the coder's `*_more.py` tests add to the count) |
| G2 | `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1849 passed, 0 failed, 0 skipped |
| G3 | `.venv/bin/python -m pytest tests/integration/test_core_edit_keys.py tests/integration/test_writes_edits.py tests/integration/test_mcp_edits.py --no-cov -q` | `74 passed` |
| G4 | `.venv/bin/python -m coverage report --include=src/docket/core.py,src/docket/writes.py,src/docket/mcp_server/server.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| G5 | `.venv/bin/python docs/verification/probe-06e.py` | last line `FAILURES 0` |
| G6 | `.venv/bin/python docs/verification/probe-06d.py` | last line `FAILURES 0` |
| G7 | `grep -c "^## Phase 6e: " docs/progress.md` | `1` |
| G8 | `.venv/bin/python scripts/check_reports.py --phase 6e` | `Reports OK.` |
| G9 | `git diff HEAD --stat -- tests/integration/test_mcp_writes.py docs/verification/probe-06d.py docs/verification/probe-06e.py tests/support.py tests/conftest.py tests/mcp_cases.py tests/sections.toml docs/reviews AGENTS.md pyproject.toml scripts` | no output |
| G10 | `git diff HEAD --numstat -- tests/integration/test_core_edit_keys.py tests/integration/test_writes_edits.py tests/integration/test_mcp_edits.py` | three lines: 0 added, 7 deleted, `tests/integration/test_core_edit_keys.py`; 0 added, 6 deleted, `tests/integration/test_mcp_edits.py`; 0 added, 5 deleted, `tests/integration/test_writes_edits.py` (the markers, nothing else) |
| G11 | `git status --short` | only the Scope paths |
| G12 | `.venv/bin/python -m pip list --format=freeze \| wc -l` | `52` (the count before this phase, plus each package the spec adds) |

## 3. Spot checks

For a module under `src/`, write the change as an exact old and new text in the module the coder wrote and run `.venv/bin/python scripts/spot_check.py <module> --old '<old>' --new '<new>' --test '<deciding test>' --row S<n>`; it restores the module and prints one line. For any other file:
1. Copy the module outside the repository.
2. Make the change described in the module the coder wrote.
3. Run the deciding test with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest '<test>' --no-cov -q --tb=line`, and confirm it fails with the "Broken" value; rerun with `-vv` only when it doesn't.
4. Restore the module from your copy, delete `src/docket/__pycache__`, and confirm `git diff` is as before.

A different failure from the "Broken" column is a note, not a finding; a pass is a finding.

| # | Module | Change | Deciding test | Correct | Broken |
|---|---|---|---|---|---|
| S1 | `core.py`, `edit_task_once` | on a kept key whose request differs, fall through to the edit instead of raising `key_reused` | `tests/integration/test_core_edit_keys.py::test_a_key_used_for_another_request_is_refused_and_writes_nothing[other-deadline]` | `CoreError` `key_reused` | `IntegrityError: UNIQUE constraint failed` or a changed dump |
| S2 | `core.py`, `edit_task_once` | keep the key only when the edit changed the task | `tests/integration/test_core_edit_keys.py::test_a_keyed_work_time_is_planned_once` | the no-change key is kept | `assert None is not None` |
| S3 | `core.py`, `edit_task_once` | check the values after `clock.now()` instead of before | `tests/integration/test_core_edit_keys.py::test_bad_input_is_refused_before_the_clock[string-deadline]` | `CoreError` `invalid_deadline` | `StopIteration` |
| S4 | `core.py`, `edit_task_once` | pass actor `"owner"` instead of the client's actor | `tests/integration/test_core_edit_keys.py::test_a_keyed_deadline_change_is_made_once_and_keeps_its_key` | audit actor `agent` | `('deadline', 'owner')` |
| S5 | `writes.py`, `plan_work_time` | leave `minutes` out of the kept request | `tests/integration/test_writes_edits.py::test_plan_work_time_plans_once_per_key` | the request holds `minutes` | `AssertionError` on the kept request |
| S6 | `writes.py`, `parse_work_time` | delete the `int` check on `minutes` | `tests/integration/test_writes_edits.py::test_a_bad_work_time_is_refused[float-minutes]` | `WriteRefused` `invalid_work` | `DID NOT RAISE` |
| S7 | `writes.py`, `change_deadline` | parse the deadline before the id check | `tests/integration/test_writes_edits.py::test_edit_refusals[number-id-first]` | `unknown_task` | `invalid_deadline` |
| S8 | `mcp_server/server.py`, `change_deadline` | give `deadline` the default `None` | `tests/integration/test_mcp_edits.py::test_the_edit_schemas` | `deadline` required, no default | `AssertionError` on the required list |
| S9 | `mcp_server/server.py`, `WorkStartInput` | make `time` `str \| None` | `tests/integration/test_mcp_edits.py::test_the_edit_schemas` | `time` a string | `AssertionError` on the `WorkStartInput` shape |

## 4. Probe

Run `.venv/bin/python docs/verification/probe-06e.py` from the repository root. It is a given file: do not edit it. Every line must end in `ok`; the last line must be `FAILURES 0`. A stop at the probe's own `assert` lines, before its self-check prints `ok`, is the probe's fault: report it under "For the architect", not as a finding. It touches no network, Keychain or real data folder.

It first forces a move, the owner clearing it and the same step again (which must change nothing), then a work time ending exactly at the deadline (which is allowed). It then walks 40 and 60 seeded steps of all five write tools through an in-memory MCP client, with valid and invalid deadlines and work times, new keys, kept keys with their own request and with another, repeats, the owner reopening tasks or clearing deadlines and work times, and a server rebuild every fifth step. After every step each task's state, deadline instant, time-given flag, work start and length, the count of kept keys and the count of the agent's audited changes must match a model of its own, and the scripted walk must reach moves, plans, replays, a replay after the owner's edit, `work_after_deadline`, invalid values, `key_reused`, `task_ended`, `unknown_task` and three rebuilds.

## 5. Searches

Each prints nothing. A match is a finding against the rule it names.

| # | Rule | Command |
|---|---|---|
| Q1 | no network code | `git grep --untracked -n -E 'import (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)\|from (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)' -- src` |
| Q2 | no output outside the CLI | `git grep --untracked -n -E 'print\(\|logging\|logger\|warnings\.warn' -- src ':!src/docket/cli.py'` |
| Q3 | no model client | `git grep --untracked -n -E 'ollama\|anthropic\|openai\|langchain' -- src` |
| Q4 | time read only in clock.py, through the module | `git grep --untracked -n -E 'datetime\.now\|datetime\.utcnow\|date\.today\|time\.time\(\|from docket\.(clock\|ids) import' -- src ':!src/docket/clock.py'` |
| Q5 | only the core writes tasks, audit rows, links and keys | `git grep --untracked -n -E '\.(insert_task\|update_task\|append_audit\|insert_link\|insert_request_key)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'` |
| Q6 | no coverage or lint exclusions in this phase's modules | `git grep --untracked -n -E 'pragma: no cover\|noqa' -- src/docket/core.py src/docket/writes.py src/docket/mcp_server/server.py` |

(In the table, `\|` is a `|` in the command.)

## 6. Reasonable variations

These are correct even though the spec does not spell them out:

- The shared private body of `edit_task` and `edit_task_once` under any name, as long as one body makes the edit, writes the audit rows and replans reminders.
- In `parse_work_time`, any order of the field and `minutes` checks, as long as every bad value gives `invalid_work` and nothing else escapes; `isinstance(minutes, int) and not isinstance(minutes, bool)` is also fine.
- One private helper in `writes` for the id check and the core call, or each written inline.
- `WorkStartInput` defined anywhere in `server.py`, as long as the schemas match the given tests.
- Private helpers inside the Scope modules, and extra behaviour tests in `*_more.py` files.

## 7. Verdict

Write `docs/reviews/phase-06e-mcp-edit-tools.md` in the form `docs/phase-conventions.md` gives (`# Review: Phase 6e`), then run `.venv/bin/python scripts/check_reports.py --phase 6e`; it must print `Reports OK.`
