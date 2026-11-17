# Verification guide: Phase 2h (Nonblocking HTTP and bounded reads)

Spec: `docs/phases/phase-02h-nonblocking-http.md`. Follow `docs/phase-conventions.md` ("For the verifier"). Never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor, never read the Keychain, and never open the real data folder.

## 1. Coder ran

Stop with FAIL ("the coder did not run") if any of these is missing:

- `tests/integration/test_http_coverage.py`
- `grep -c "^## Phase 2h: " docs/progress.md` prints `1`

Stop with FAIL ("the coder stopped") if that entry's first `Follow-ups` line starts with `Stopped:`, as "A stopped coder" in `docs/phase-conventions.md` says. With no entry, `git status --short` tells "the coder did not run" (no Scope path changed) from "the coder broke off without reporting" (Scope paths changed; name them under `For the architect`).

Stop with FAIL ("the baseline is not committed") if `git ls-files --error-unmatch docs/phases/phase-02h-nonblocking-http.md tests/http_cases.py tests/integration/test_web_streaming.py tests/integration/test_web_workers.py docs/verification/probe-02h.py` fails: the diff gates can only be judged against a committed spec and given files.

## 2. Gates

Run each from the repository root, in this order: `.venv/bin/python scripts/accept.py --phase 2h --guide` runs them and the searches, one line each. Given test count: 30.

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_web_streaming.py --ignore=tests/integration/test_web_workers.py` | at least 927 passed, 0 failed (the coder's `*_more.py` tests add to the count) |
| G2 | `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 957 passed, 0 failed, 0 skipped |
| G3 | `.venv/bin/python -m pytest tests/integration/test_web_streaming.py tests/integration/test_web_workers.py --no-cov -q` | `30 passed` |
| G4 | `.venv/bin/python -m coverage report --include=src/docket/web.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| G5 | `.venv/bin/python docs/verification/probe-02h.py` | last line `FAILURES 0` |
| G6 | `grep -c "^## Phase 2h: " docs/progress.md` | `1` |
| G7 | `.venv/bin/python scripts/check_reports.py --phase 2h` | `Reports OK.` |
| G8 | `git diff HEAD --stat -- tests/http_cases.py tests/integration/test_web_streaming.py tests/integration/test_web_workers.py docs/verification/probe-02h.py` | no output |
| G9 | `git status --short` | only the Scope paths |
| G10 | `.venv/bin/python -m pip list --format=freeze \| wc -l` | `39` (unchanged; no package is added) |

## 3. Spot checks

Inspect that every chunk's size is checked before it is appended to the accumulated body, that the body is not cached through Request.body(), and that no Store is created before worker dispatch. The factory, intake and context exit must all remain in that one worker; no connection-affinity relaxation, background task or new error mapping is allowed. Existing tests and other production files have no diff.

Run mutations on a clean disposable checkout containing the planning baseline and implementation under review, with imports directed at that checkout. Do not mutate the user's live checkout: process termination can bypass restoration. Translate each conceptual one-line mutation to the implementation's private helper names. The eight rows were confirmed against the temporary patch during planning; different internal structure does not excuse a deciding test passing after the same behaviour is broken.

For a module under `src/`, write the change as an exact old and new text in the module the coder wrote and run `.venv/bin/python scripts/spot_check.py <module> --old '<old>' --new '<new>' --test '<deciding test>' --row S<n>`; it restores the module and prints one line. For any other file:
1. Copy the module outside the repository.
2. Make the change described in the module the coder wrote.
3. Run the deciding test with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest '<test>' --no-cov -q --tb=line`, and confirm it fails with the "Broken" value; rerun with `-vv` only when it doesn't.
4. Restore the module from your copy, delete `src/docket/__pycache__`, and confirm `git diff` is as before.

A different failure from the "Broken" column is a note, not a finding; a pass is a finding.

| # | Module | Change | Deciding test | Correct | Broken |
|---|---|---|---|---|---|
| S1 | `web.py`, request body handling | Insert `await request.body()` immediately before the new bounded read | `tests/integration/test_web_streaming.py::test_route_never_uses_request_body` | 201 | `UnboundedReadCalled` |
| S2 | `web.py`, size guard | Change the accumulated-byte comparison from `>` to `>=` | `tests/integration/test_web_streaming.py::test_exact_limit_uses_actual_bytes_not_content_length[task-absent]` | 201 | 413 |
| S3 | `web.py`, size guard | Replace its overflow condition with `False` | `tests/integration/test_web_streaming.py::test_oversized_stream_stops_before_another_chunk[split-task]` | 413 after 2 chunks | extra-read assertion in an exception group |
| S4 | `web.py`, before the bounded read | Return 413 when the parsed Content-Length header is greater than MAX_BODY | `tests/integration/test_web_streaming.py::test_exact_limit_uses_actual_bytes_not_content_length[task-overstated]` | 201 | 413 |
| S5 | `web.py`, dispatch | Call the synchronous store/intake helper inline instead of awaiting the worker call | `tests/integration/test_web_workers.py::test_open_intake_and_close_share_one_worker[email-task]` | worker store lifetime | `AssertionError: store opened on the event loop` |
| S6 | `web.py`, worker context | Replace `with open_store() as store:` with `if (store := open_store()):`, retaining its indented body | `tests/integration/test_web_workers.py::test_intake_failure_closes_the_worker_connection[task]` | one recorded close on the open thread | no recorded close |
| S7 | `web.py`, worker task intake | Pass `client="email"` to task intake instead of the matched client | `tests/integration/test_web_workers.py::test_open_intake_and_close_share_one_worker[agent-task]` | matched `agent`, 422 | identity assertion: email differs from agent |
| S8 | `web.py`, before the bounded read | Return 400 missing_key when the key header is absent, before the body is read | `tests/integration/test_web_streaming.py::test_streaming_preserves_size_key_and_json_order[size-before-key]` | 413 | 400 |

## 4. Probe

Run `.venv/bin/python docs/verification/probe-02h.py` from the repository root. It is a given file: do not edit it. Every line must end in `ok`; the last line must be `FAILURES 0`. A stop at the probe's own `assert` lines, before its self-check prints `ok`, is the probe's fault: report it under "For the architect", not as a finding. It touches no network, Keychain or real data folder.

The probe combines three oversized chunk layouts with unread tails, then task/link creation and retries using real temporary stores, checks worker lifetime and reopens the database to confirm one task, link and create audit row. Run without PYTHONPATH overrides so the published helper-import path is checked. `--oracle-only` checks its literal size and result assumptions.

## 5. Searches

Each prints nothing. A match is a finding against the rule it names.

| # | Rule | Command |
|---|---|---|
| Q1 | no network code | `git grep --untracked -n -E 'import (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)\|from (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)' -- src` |
| Q2 | no output outside the CLI | `git grep --untracked -n -E 'print\(\|logging\|logger\|warnings\.warn' -- src ':!src/docket/cli.py'` |
| Q3 | time read only in clock.py, through the module | `git grep --untracked -n -E 'datetime\.now\|datetime\.utcnow\|date\.today\|time\.time\(\|from docket\.(clock\|ids) import' -- src ':!src/docket/clock.py'` |
| Q4 | only the core writes tasks, audit rows, links and keys | `git grep --untracked -n -E '\.(insert_task\|update_task\|append_audit\|insert_link\|insert_request_key)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'` |
| Q5 | no model client | `git grep --untracked -n -E 'ollama\|anthropic\|openai\|langchain' -- src` |
| Q6 | no coverage or lint exclusions in this phase's modules | `git grep --untracked -n -E 'pragma: no cover\|noqa' -- src/docket/web.py` |
| Q7 | no environment, machine zone or locale in this phase's modules | `git grep --untracked -n -E 'os\.environ\|getenv\(\|strftime\(\|import locale' -- src/docket/web.py` |

(In the table, `\|` is a `|` in the command.)

## 6. Reasonable variations

These are correct even though the spec does not spell them out:

- Private helper names, a bytearray or a bounded list of byte chunks, and equivalent use of the installed framework worker API.
- JSON parsing and response construction may stay in the async handler; every operation using the store remains within one synchronous worker context.
- A worker may be reused for a later request, but a store connection may not be shared across requests.
- Private helpers inside web.py and extra behaviour tests only in the Scope test file.

## 7. Verdict

Write `docs/reviews/phase-02h-nonblocking-http.md` in the form `docs/phase-conventions.md` gives (`# Review: Phase 2h`), then run `.venv/bin/python scripts/check_reports.py --phase 2h`; it must print `Reports OK.`
