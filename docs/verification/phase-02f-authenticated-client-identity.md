# Verification guide: Phase 2f (Authenticated client identity)

Spec: `docs/phases/phase-02f-authenticated-client-identity.md`. Follow `docs/phase-conventions.md` ("For the verifier"). Never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor, never read the Keychain, and never open the real data folder.

## 1. Coder ran

Stop with FAIL ("the coder did not run") if any of these is missing:

- `tests/integration/test_identity_coverage.py`
- `grep -c "^## Phase 2f: " docs/progress.md` prints `1`

Stop with FAIL ("the coder stopped") if that entry's first `Follow-ups` line starts with `Stopped:`, as "A stopped coder" in `docs/phase-conventions.md` says. With no entry, `git status --short` tells "the coder did not run" (no Scope path changed) from "the coder broke off without reporting" (Scope paths changed; name them under `For the architect`).

Stop with FAIL ("the baseline is not committed") if `git ls-files --error-unmatch docs/phases/phase-02f-authenticated-client-identity.md tests/integration/test_core_identity.py tests/integration/test_intake_identity.py tests/integration/test_web_identity.py docs/verification/probe-02b.py docs/verification/probe-02f.py` fails: the diff gates can only be judged against a committed spec and given files.

## 2. Gates

Run each from the repository root, in this order: `.venv/bin/python scripts/accept.py --phase 2f --guide` runs them and the searches, one line each. Given test count: 41.

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_core_identity.py --ignore=tests/integration/test_intake_identity.py --ignore=tests/integration/test_web_identity.py` | at least 795 passed, 0 failed (the coder's `*_more.py` tests add to the count) |
| G2 | `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 836 passed, 0 failed, 0 skipped |
| G3 | `.venv/bin/python -m pytest tests/integration/test_core_identity.py tests/integration/test_intake_identity.py tests/integration/test_web_identity.py --no-cov -q` | `41 passed` |
| G4 | `.venv/bin/python -m coverage report --include=src/docket/core.py,src/docket/intake.py,src/docket/web.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| G5 | `.venv/bin/python docs/verification/probe-02f.py` | last line `FAILURES 0` |
| G6 | `grep -c "^## Phase 2f: " docs/progress.md` | `1` |
| G7 | `.venv/bin/python scripts/check_reports.py --phase 2f` | `Reports OK.` |
| G8 | `git diff HEAD --stat -- tests/integration/test_core_identity.py tests/integration/test_intake_identity.py tests/integration/test_web_identity.py docs/verification/probe-02b.py docs/verification/probe-02f.py` | no output |
| G9 | `git status --short` | only the Scope paths |
| G10 | `.venv/bin/python -m pip list --format=freeze \| wc -l` | `39` (unchanged; no dependency is added) |

## 3. Spot checks

Before mutations, inspect `tests/integration/test_intake.py`: every diff is only adding `client="email"` and formatter wrapping. The earlier given tests' assertions, cases and names remain intact. Confirm the changed lines in production do not alter client provisioning or any later audit work.

Run mutations in a clean disposable checkout containing the baseline plus the implementation under review, with this repository's virtual environment and imports directed at that checkout. The runner restores on exceptions, but cannot restore after process termination. Keep the user's checkout untouched. Adapt each conceptual one-line mutation below to the exact text in the implementation; do not prescribe helper layout.

For a module under `src/`, write the change as an exact old and new text in the module the coder wrote and run `.venv/bin/python scripts/spot_check.py <module> --old '<old>' --new '<new>' --test '<deciding test>' --row S<n>`; it restores the module and prints one line. For any other file:
1. Copy the module outside the repository.
2. Make the change described in the module the coder wrote.
3. Run the deciding test with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest '<test>' --no-cov -q --tb=line`, and confirm it fails with the "Broken" value; rerun with `-vv` only when it doesn't.
4. Restore the module from your copy, delete `src/docket/__pycache__`, and confirm `git diff` is as before.

A different failure from the "Broken" column is a note, not a finding; a pass is a finding.

| # | Module | Change | Deciding test | Correct | Broken |
|---|---|---|---|---|---|
| S1 | `web.py`, task dispatch | Pass `client="email"` instead of the matched identity on the `accept_task` call | `tests/integration/test_web_identity.py::test_http_passes_the_matched_identity_to_intake[other-task]` | captured `agent` | captured `email` |
| S2 | `web.py`, link dispatch | Pass `client="email"` instead of the matched identity on the `accept_link` call | `tests/integration/test_web_identity.py::test_http_passes_the_matched_identity_to_intake[other-link]` | captured `agent` | captured `email` |
| S3 | `intake.py`, `accept_task` | Replace the new invalid-client condition with `False` in this function only | `tests/integration/test_intake_identity.py::test_only_email_identity_can_enter_intake[agent]` | 422 `invalid_client` | 422 `invalid_source` |
| S4 | `intake.py`, `accept_link` | Replace the new invalid-client condition with `False` in this function only | `tests/integration/test_intake_identity.py::test_only_email_identity_can_enter_intake[agent]` | 422 `invalid_client` | 404 `unknown_task` on the link call |
| S5 | `core.py`, `create_task_once` | Remove only the `isinstance(client, str)` guard, leaving membership validation | `tests/integration/test_core_identity.py::test_keyed_create_refuses_non_string_identity_fields[equal-client]` | `CoreError(invalid_client)` | `StopIteration` at the clock |
| S6 | `core.py`, `create_task_once` | Remove only the source type guard, leaving `source != client` validation | `tests/integration/test_core_identity.py::test_keyed_create_refuses_non_string_identity_fields[equal-source]` | `CoreError(invalid_source)` | `StopIteration` at the clock |
| S7 | `core.py`, `add_link` | Remove only the client type guard, leaving email equality validation | `tests/integration/test_core_identity.py::test_links_refuse_non_string_identity_fields_before_the_clock[equal-client]` | `CoreError(invalid_client)` | `StopIteration` at the clock |
| S8 | `core.py`, email reference validation | Remove only the provider type guard used by `create_task_once`, leaving provider membership validation | `tests/integration/test_core_identity.py::test_keyed_create_refuses_non_string_identity_fields[equal-provider]` | `CoreError(invalid_reference)` | `StopIteration` at the clock |
| S9 | `core.py`, `add_link` reference validation | Remove only the provider type guard used by `add_link`, leaving provider membership validation | `tests/integration/test_core_identity.py::test_links_refuse_non_string_identity_fields_before_the_clock[equal-provider]` | `CoreError(invalid_reference)` | `StopIteration` at the clock |
| S10 | `intake.py`, `accept_task` signature | Give the new client keyword the default `"email"` | `tests/integration/test_intake_identity.py::test_client_is_a_required_keyword[task]` | no default | default `email` |

## 4. Probe

Run `.venv/bin/python docs/verification/probe-02f.py` from the repository root. It is a given file: do not edit it. Every line must end in `ok`; the last line must be `FAILURES 0`. A stop at the probe's own `assert` lines, before its self-check prints `ok`, is the probe's fault: report it under "For the architect", not as a finding. It touches no network, Keychain or real data folder.

The finite matrix combines three token identities, task/link retries and a pre-existing agent key in both map orders, then reopens the database to check persistent isolation. It also checks the required intake keywords. Its oracle uses literal cases, with `--oracle-only` assertions for case coverage.

## 5. Searches

Each prints nothing. A match is a finding against the rule it names.

| # | Rule | Command |
|---|---|---|
| Q1 | no network code | `git grep --untracked -n -E 'import (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)\|from (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)' -- src` |
| Q2 | no output outside the CLI | `git grep --untracked -n -E 'print\(\|logging\|logger\|warnings\.warn' -- src ':!src/docket/cli.py'` |
| Q3 | time read only in clock.py, through the module | `git grep --untracked -n -E 'datetime\.now\|datetime\.utcnow\|date\.today\|time\.time\(\|from docket\.(clock\|ids) import' -- src ':!src/docket/clock.py'` |
| Q4 | only the core writes tasks, audit rows, links and keys | `git grep --untracked -n -E '\.(insert_task\|update_task\|append_audit\|insert_link\|insert_request_key)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'` |
| Q5 | no model client | `git grep --untracked -n -E 'ollama\|anthropic\|openai\|langchain' -- src` |
| Q6 | no coverage or lint exclusions in this phase's modules | `git grep --untracked -n -E 'pragma: no cover\|noqa' -- src/docket/core.py src/docket/intake.py src/docket/web.py` |
| Q7 | no environment, machine zone or locale in this phase's modules | `git grep --untracked -n -E 'os\.environ\|getenv\(\|strftime\(\|import locale' -- src/docket/core.py src/docket/intake.py src/docket/web.py` |

(In the table, `\|` is a `|` in the command.)

## 6. Reasonable variations

These are correct even though the spec does not spell them out:

- Private bearer-helper naming and shape; no test or contract requires a new public authentication API.
- A shared private client/type validator or inline checks, with the specified refusal order and no coercion.
- The provider guard may live in the shared reference validator, provided both keyed paths refuse non-strings before the clock.
- Formatting-only line wrapping accompanying the existing intake test call-site migration; assertions and cases are unchanged.
- Private helpers inside the Scope modules and behaviour tests in the Scope test file; no unlisted test paths.

## 7. Verdict

Write `docs/reviews/phase-02f-authenticated-client-identity.md` in the form `docs/phase-conventions.md` gives (`# Review: Phase 2f`), then run `.venv/bin/python scripts/check_reports.py --phase 2f`; it must print `Reports OK.`
