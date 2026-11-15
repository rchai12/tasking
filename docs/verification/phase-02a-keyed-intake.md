# Verification guide: Phase 2a (Keyed intake)

Spec: `docs/phases/phase-02a-keyed-intake.md`. Follow `docs/phase-conventions.md` ("For the verifier"). Never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor, never read the Keychain, and never open the real data folder.

## 1. Coder ran

Stop with FAIL ("the coder did not run") if any of these is missing:


- `grep -c "^## Phase 2a: " docs/progress.md` prints `1`

Stop with FAIL ("the coder stopped") if that entry's first `Follow-ups` line starts with `Stopped:`, as "A stopped coder" in `docs/phase-conventions.md` says. With no entry, `git status --short` tells "the coder did not run" (no Scope path changed) from "the coder broke off without reporting" (Scope paths changed; name them under `For the architect`).

Stop with FAIL ("the baseline is not committed") if `git ls-files --error-unmatch docs/phases/phase-02a-keyed-intake.md tests/integration/test_store_links.py tests/integration/test_core_keyed.py src/docket/schema.py tests/integration/test_store.py tests/e2e/test_cli_tasks_more.py docs/verification/probe-02a.py` fails: the diff gates can only be judged against a committed spec and given files.

## 2. Gates

Run each from the repository root, in this order. Given test count: 56.

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_store_links.py --ignore=tests/integration/test_core_keyed.py` | at least 522 passed, 0 failed (the coder's `*_more.py` tests add to the count) |
| G2 | `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 578 passed, 0 failed, 0 skipped |
| G3 | `.venv/bin/python -m pytest tests/integration/test_store_links.py tests/integration/test_core_keyed.py --no-cov -q` | `56 passed` |
| G4 | `.venv/bin/python -m coverage report --include=src/docket/store.py,src/docket/core.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| G5 | `.venv/bin/python docs/verification/probe-02a.py` | last line `FAILURES 0` |
| G6 | `grep -c "^## Phase 2a: " docs/progress.md` | `1` |
| G7 | `.venv/bin/python scripts/check_reports.py --phase 2a` | `Reports OK.` |
| G8 | `git diff HEAD --stat -- tests/integration/test_store_links.py tests/integration/test_core_keyed.py src/docket/schema.py tests/integration/test_store.py tests/e2e/test_cli_tasks_more.py docs/verification/probe-02a.py` | no output |
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
| S1 | `store.py` | store the request with `json.dumps(request)`, unsorted and spaced | `tests/integration/test_store_links.py::test_the_stored_request_text_is_canonical` | `'{"a":[1,2],"deadline":null,"title":"Café"}'` | `'{"title": "Café", "deadline": null, "a": [1, 2]}'` |
| S2 | `store.py` | drop `insert_request_key`'s check that the link exists | `tests/integration/test_store_links.py::test_a_request_key_write_follows_the_store_rules` | `StoreError` (`unknown link`) | `sqlite3.IntegrityError` (the foreign key) |
| S3 | `store.py` | list a task's links newest first | `tests/integration/test_store_links.py::test_links_are_numbered_and_listed_per_task` | `[first, second]` | `[second, first]` |
| S4 | `core.py` | compare a repeated request with `json.dumps(request)` against the stored text | `tests/integration/test_core_keyed.py::test_the_request_is_compared_as_data_not_as_text` | `changed` False | `CoreError` (`key_reused`) |
| S5 | `core.py` | drop the rule that the source must be the client | `tests/integration/test_core_keyed.py::test_a_refused_keyed_create_writes_nothing[source-not-the-client]` | `CoreError` (`invalid_source`) | `StopIteration` (the test gives the clock no moment) |
| S6 | `core.py` | allow a 201-character key | `tests/integration/test_core_keyed.py::test_a_refused_keyed_create_writes_nothing[long-key]` | `CoreError` (`invalid_key`) | `StopIteration` |
| S7 | `core.py` | answer a repeat with `changed=True` | `tests/integration/test_core_keyed.py::test_the_same_key_and_request_answer_with_the_task_again` | `changed` False | `changed` True |
| S8 | `core.py` | match a repeated link by key and request, ignoring its task | `tests/integration/test_core_keyed.py::test_a_link_key_reused_differently_is_refused[another-task]` | `CoreError` (`key_reused`) | DID NOT RAISE (a repeat of `l1`) |
| S9 | `core.py` | in `add_link`, look up the task before the key | `tests/integration/test_core_keyed.py::test_a_link_key_reused_differently_is_refused[key-before-unknown-task]` | `key_reused` | `unknown_task` |
| S10 | `core.py` | accept links from client `agent` | `tests/integration/test_core_keyed.py::test_a_refused_link_writes_nothing[agent]` | `CoreError` (`invalid_client`) | `StopIteration` (no clock moment left for the link) |
| S11 | `core.py` | commit the new task, then record the key in a second transaction | `tests/integration/test_core_keyed.py::test_a_keyed_write_commits_whole_or_not_at_all` | tasks `['t1']` | tasks `['t1', 't2']` |
| S12 | `core.py` | write a `link` audit row for each new link | `tests/integration/test_core_keyed.py::test_a_follow_up_link_is_added_once` | 1 audit row on `t1` | `sqlite3.IntegrityError` (the audit log's action CHECK has no `link`) |
| S13 | `core.py` | refuse a link to an ended task | `tests/integration/test_core_keyed.py::test_a_link_may_follow_an_ended_task` | `changed` True | `CoreError` (`task_ended`) |

Each row was traced with its test's clock list as a layer (S5, S6 and S10 stop at the clock read the broken path reaches) and with the schema as a layer (S2 and S12 stop at a constraint).

## 4. Probe

Run `.venv/bin/python docs/verification/probe-02a.py` from the repository root. It is a given file: do not edit it. Every line must end in `ok`; the last line must be `FAILURES 0`. A stop at the probe's own `assert` lines, before its self-check prints `ok`, is the probe's fault: report it under "For the architect", not as a finding. It touches no network, Keychain or real data folder.

It checks what the given tests do not reach: 700 random keyed creates and links through two `Store` objects on one file, from both clients, with keys fresh, repeated and reused, links to known and unknown tasks, every answer (new, same, reused, unknown task) compared with the probe's own model of the keys, and the tasks and links checked after each step, each answer reached at least 15 times; and 40 races of two threads sending one key at once, where one makes the task and the other gets its answer (same request) or `key_reused` (another request), with exactly one task.

## 5. Searches

Each prints nothing. A match is a finding against the rule it names.

| # | Rule | Command |
|---|---|---|
| Q1 | no network code | `git grep --untracked -n -E 'import (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)\|from (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)' -- src` |
| Q2 | no output outside the CLI | `git grep --untracked -n -E 'print\(\|logging\|logger\|warnings\.warn' -- src ':!src/docket/cli.py'` |
| Q3 | time read only in `clock.py`, through the module | `git grep --untracked -n -E 'datetime\.now\|datetime\.utcnow\|date\.today\|time\.time\(\|from docket\.(clock\|ids) import' -- src ':!src/docket/clock.py'` |
| Q4 | only the core writes tasks, audit rows, links and keys | `git grep --untracked -n -E '\.(insert_task\|update_task\|append_audit\|insert_link\|insert_request_key)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'` |
| Q5 | no model client | `git grep --untracked -n -E 'ollama\|anthropic\|openai\|langchain' -- src` |
| Q6 | no coverage or lint exclusions in this phase's modules | `git grep --untracked -n -E 'pragma: no cover\|noqa' -- src/docket/store.py src/docket/core.py` |

(In the table, `\|` is a `|` in the command.)

## 6. Reasonable variations

These are correct even though the spec does not spell them out:

- `create_task_once` sharing private helpers with `create_task` for the checks, the insert and the audit row.
- The repeat check comparing the stored `RequestKey.request` with the new request as dicts, or comparing their canonical JSON.
- `Link` and `RequestKey` built by private row helpers; a private `_link_number` like Phase 1b's task id rule.
- `store.links(task_id)` read to find the link a repeated key names.
- Private helpers inside the Scope modules, and extra behaviour tests in `*_more.py` files.

## 7. Verdict

Write `docs/reviews/phase-02a-keyed-intake.md` in the form `docs/phase-conventions.md` gives (`# Review: Phase 2a`), then run `.venv/bin/python scripts/check_reports.py --phase 2a`; it must print `Reports OK.`
