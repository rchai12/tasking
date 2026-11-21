# Verification guide: Phase 6d (MCP write tools)

Spec: `docs/phases/phase-06d-mcp-write-tools.md`. Follow `docs/phase-conventions.md` ("For the verifier"). Never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor, never read the Keychain, and never open the real data folder.

## 1. Coder ran

Stop with FAIL ("the coder did not run") if any of these is missing:


- `grep -c "^## Phase 6d: " docs/progress.md` prints `1`

Stop with FAIL ("the coder stopped") if that entry's first `Follow-ups` line starts with `Stopped:`, as "A stopped coder" in `docs/phase-conventions.md` says. With no entry, `git status --short` tells "the coder did not run" (no Scope path changed) from "the coder broke off without reporting" (Scope paths changed; name them under `For the architect`).

Stop with FAIL ("the baseline is not committed") if `git ls-files --error-unmatch docs/phases/phase-06d-mcp-write-tools.md tests/integration/test_core_state_keys.py tests/integration/test_writes.py tests/integration/test_mcp_writes.py tests/integration/test_mcp_server.py docs/verification/probe-06d.py` fails: the diff gates can only be judged against a committed spec and given files. If the coder's work is already committed (a commit after the spec's, and a clean tree), judge every `git diff HEAD` gate against the spec's commit instead (`git log --diff-filter=A --format=%h -1 -- docs/phases/phase-06d-mcp-write-tools.md`), and the `git status --short` gate with `git diff <that commit> --name-status`.

## 2. Gates

Run each from the repository root, in this order: `.venv/bin/python scripts/accept.py --phase 6d --guide` runs them and the searches, one line each. Given test count: 67.

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_core_state_keys.py --ignore=tests/integration/test_writes.py --ignore=tests/integration/test_mcp_writes.py` | at least 1707 passed, 0 failed (the coder's `*_more.py` tests add to the count) |
| G2 | `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1774 passed, 0 failed, 0 skipped |
| G3 | `.venv/bin/python -m pytest tests/integration/test_core_state_keys.py tests/integration/test_writes.py tests/integration/test_mcp_writes.py --no-cov -q` | `67 passed` |
| G4 | `.venv/bin/python -m coverage report --include=src/docket/writes.py,src/docket/core.py,src/docket/mcp_server/server.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| G5 | `.venv/bin/python docs/verification/probe-06d.py` | last line `FAILURES 0` |
| G6 | `grep -c "^## Phase 6d: " docs/progress.md` | `1` |
| G7 | `.venv/bin/python scripts/check_reports.py --phase 6d` | `Reports OK.` |
| G8 | `git diff HEAD --stat -- docs/verification/probe-06d.py tests/support.py tests/conftest.py tests/mcp_cases.py tests/sections.toml docs/reviews AGENTS.md pyproject.toml scripts/check.py` | no output |
| G9 | `git diff HEAD --numstat -- tests/integration/test_core_state_keys.py tests/integration/test_writes.py tests/integration/test_mcp_writes.py tests/integration/test_mcp_server.py` | three lines: 0 added, 8 deleted, `tests/integration/test_core_state_keys.py`; 0 added, 7 deleted, `tests/integration/test_mcp_writes.py`; 0 added, 7 deleted, `tests/integration/test_writes.py` (the markers, nothing else; `test_mcp_server.py` stays unchanged) |
| G10 | `git status --short` | only the Scope paths |
| G11 | `.venv/bin/python -m pip list --format=freeze \| wc -l` | `52` (the count before this phase, plus each package the spec adds) |

## 3. Spot checks

For a module under `src/`, write the change as an exact old and new text in the module the coder wrote and run `.venv/bin/python scripts/spot_check.py <module> --old '<old>' --new '<new>' --test '<deciding test>' --row S<n>`; it restores the module and prints one line. For any other file:
1. Copy the module outside the repository.
2. Make the change described in the module the coder wrote.
3. Run the deciding test with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest '<test>' --no-cov -q --tb=line`, and confirm it fails with the "Broken" value; rerun with `-vv` only when it doesn't.
4. Restore the module from your copy, delete `src/docket/__pycache__`, and confirm `git diff` is as before.

A different failure from the "Broken" column is a note, not a finding; a pass is a finding.

| # | Module | Change | Deciding test | Correct | Broken |
|---|---|---|---|---|---|
| S1 | `core.py`, `change_state_once` | on a kept key whose request differs, fall through to the change instead of raising `key_reused` | `tests/integration/test_core_state_keys.py::test_a_key_used_for_another_request_is_refused_and_writes_nothing[other-action]` | `CoreError` `key_reused` | `AssertionError` (the dump changed) or `IntegrityError` |
| S2 | `core.py`, `change_state_once` | skip the kept-key lookup (treat every key as new) | `tests/integration/test_core_state_keys.py::test_a_retried_step_changes_nothing_after_the_owner_reopens` | `changed` False, the dump unchanged | `IntegrityError: UNIQUE constraint failed` |
| S3 | `core.py`, `change_state_once` | keep the key only when the change was made (`if outcome.changed:` before the insert) | `tests/integration/test_core_state_keys.py::test_a_new_key_on_a_finished_task_is_no_change_and_is_kept` | the key is kept | `assert None is not None` |
| S4 | `core.py`, `change_state_once` | pass actor `"owner"` instead of the client's actor | `tests/integration/test_core_state_keys.py::test_keys_are_per_client` | actors `agent`, `email` | `('done', 'owner')` in the audit |
| S5 | `writes.py`, `create_task` | leave `deadline` out of the kept request | `tests/integration/test_writes.py::test_create_task_refuses_a_key_reused_with_other_arguments[other-deadline]` | `WriteRefused` `key_reused` | `DID NOT RAISE` |
| S6 | `writes.py`, `parse_deadline` | accept extra keys (require only that `date`, `time`, `time_zone` are present) | `tests/integration/test_writes.py::test_a_bad_deadline_is_refused[extra-field]` | `WriteRefused` `invalid_deadline` | `DID NOT RAISE` |
| S7 | `writes.py`, the state changes | delete the non-string id check | `tests/integration/test_writes.py::test_state_change_refusals[id-before-key]` | `unknown_task` | `invalid_key` |
| S8 | `mcp_server/server.py`, the write tools' hints | set `read_only_hint=True` | `tests/integration/test_mcp_writes.py::test_it_lists_three_write_tools_that_are_not_read_only` | hints `(False, False, True, False)` | `AssertionError` naming a write tool |
| S9 | `mcp_server/server.py`, the refusal | raise `ToolError` with `str(error) + " " + repr(error)` instead of the code alone | `tests/integration/test_mcp_writes.py::test_refusals_are_constant_codes[unknown-zone]` | `...: invalid_deadline` | the text carries `WriteRefused('invalid_deadline')` |

## 4. Probe

Run `.venv/bin/python docs/verification/probe-06d.py` from the repository root. It is a given file: do not edit it. Every line must end in `ok`; the last line must be `FAILURES 0`. A stop at the probe's own `assert` lines, before its self-check prints `ok`, is the probe's fault: report it under "For the architect", not as a finding. It touches no network, Keychain or real data folder.

It walks 40 and then 60 seeded steps of create, complete and cancel calls through an in-memory MCP client, with new keys, kept keys with their own request, and kept keys with another request, each sometimes sent twice; the owner reopens or starts tasks between steps, and the server is rebuilt every fifth step. After every step the stored states, the count of kept keys and the count of the agent's audited changes must match a model of its own, and the scripted walk must reach replays, `key_reused`, `task_ended`, `unknown_task`, no-change answers, a retry after a reopen and three rebuilds. It also checks the listing: five tools, the writes not read-only, idempotent, with an output schema and a required `request_key`.

## 5. Searches

Each prints nothing. A match is a finding against the rule it names.

| # | Rule | Command |
|---|---|---|
| Q1 | no network code | `git grep --untracked -n -E 'import (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)\|from (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)' -- src` |
| Q2 | no output outside the CLI | `git grep --untracked -n -E 'print\(\|logging\|logger\|warnings\.warn' -- src ':!src/docket/cli.py'` |
| Q3 | no model client | `git grep --untracked -n -E 'ollama\|anthropic\|openai\|langchain' -- src` |
| Q4 | time read only in clock.py, through the module | `git grep --untracked -n -E 'datetime\.now\|datetime\.utcnow\|date\.today\|time\.time\(\|from docket\.(clock\|ids) import' -- src ':!src/docket/clock.py'` |
| Q5 | only the core writes tasks, audit rows, links and keys | `git grep --untracked -n -E '\.(insert_task\|update_task\|append_audit\|insert_link\|insert_request_key)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'` |
| Q6 | no coverage or lint exclusions in this phase's modules | `git grep --untracked -n -E 'pragma: no cover\|noqa' -- src/docket/writes.py src/docket/core.py src/docket/mcp_server/server.py` |

(In the table, `\|` is a `|` in the command.)

## 6. Reasonable variations

These are correct even though the spec does not spell them out:

- The shared private body of `change_state` and `change_state_once` under any name, or `change_state` calling `change_state_once`'s inner part, as long as one body makes the change and writes the audit row.
- In `parse_deadline`, any order of the field checks, as long as every bad value gives `invalid_deadline` and nothing else escapes.
- The `writes` refusal mapping as one helper or written in each function; the tool bodies as one helper or three.
- `DeadlineInput` and `TaskChangeResult` defined anywhere in `server.py`, as long as the schemas match the given tests.
- Private helpers inside the Scope modules, and extra behaviour tests in `*_more.py` files.

## 7. Verdict

Write `docs/reviews/phase-06d-mcp-write-tools.md` in the form `docs/phase-conventions.md` gives (`# Review: Phase 6d`), then run `.venv/bin/python scripts/check_reports.py --phase 6d`; it must print `Reports OK.`
