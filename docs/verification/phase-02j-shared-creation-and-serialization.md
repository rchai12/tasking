# Verification guide: Phase 2j (Shared creation and serialization)

Spec: `docs/phases/phase-02j-shared-creation-and-serialization.md`. Follow `docs/phase-conventions.md` ("For the verifier"). Never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor, never read the Keychain, and never open the real data folder.

## 1. Coder ran

Stop with FAIL ("the coder did not run") if any of these is missing:

- `src/docket/serialization.py`
- `tests/integration/test_shared_creation_more.py`
- `grep -c "^## Phase 2j: " docs/progress.md` prints `1`

Stop with FAIL ("the coder stopped") if that entry's first `Follow-ups` line starts with `Stopped:`, as "A stopped coder" in `docs/phase-conventions.md` says. With no entry, `git status --short` tells "the coder did not run" (no Scope path changed) from "the coder broke off without reporting" (Scope paths changed; name them under `For the architect`).

Stop with FAIL ("the baseline is not committed") if `git ls-files --error-unmatch docs/phases/phase-02j-shared-creation-and-serialization.md tests/unit/test_canonical_json.py tests/integration/test_shared_creation.py scripts/critical_modules.txt docs/verification/probe-02j.py` fails: the diff gates can only be judged against a committed spec and given files.

## 2. Gates

Run each from the repository root, in this order: `.venv/bin/python scripts/accept.py --phase 2j --guide` runs them and the searches, one line each. Given test count: 25.

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_canonical_json.py --ignore=tests/integration/test_shared_creation.py` | at least 1042 passed, 0 failed (the coder's `*_more.py` tests add to the count) |
| G2 | `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1067 passed, 0 failed, 0 skipped |
| G3 | `.venv/bin/python -m pytest tests/unit/test_canonical_json.py tests/integration/test_shared_creation.py --no-cov -q` | `25 passed` |
| G4 | `.venv/bin/python -m coverage report --include=src/docket/serialization.py,src/docket/core.py,src/docket/store.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| G5 | `.venv/bin/python docs/verification/probe-02j.py` | last line `FAILURES 0` |
| G6 | `grep -c "^## Phase 2j: " docs/progress.md` | `1` |
| G7 | `.venv/bin/python scripts/check_reports.py --phase 2j` | `Reports OK.` |
| G8 | `git diff HEAD --stat -- tests/unit/test_canonical_json.py tests/integration/test_shared_creation.py scripts/critical_modules.txt docs/verification/probe-02j.py` | no output |
| G9 | `git status --short` | only the Scope paths |
| G10 | `.venv/bin/python -m pip list --format=freeze \| wc -l` | `39` (unchanged; no package is added) |

## 3. Spot checks

Inspect the architecture first: one private helper contains insertion plus the complete create audit and is directly called from both public creates. Its caller retains validation, its single clock read and the original transaction. The helper has no clock, validation, transaction or request-key responsibility. Store decoding remains local; all encoding/comparison calls route through the shared module. No schema, client identity or refusal-order drift is allowed.

Run mutations in a clean disposable checkout containing the planning baseline and implementation, with PYTHONPATH=src:. directed at that checkout; never mutate the owner's live checkout. Rows S1–S5 were confirmed against the discarded small serializer-routing patch plus existing code. S6 is a paper check of the new helper, whose private name the coder chooses; translate its one-line mutation to the submitted helper.

For a module under `src/`, write the change as an exact old and new text in the module the coder wrote and run `.venv/bin/python scripts/spot_check.py <module> --old '<old>' --new '<new>' --test '<deciding test>' --row S<n>`; it restores the module and prints one line. For any other file:
1. Copy the module outside the repository.
2. Make the change described in the module the coder wrote.
3. Run the deciding test with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest '<test>' --no-cov -q --tb=line`, and confirm it fails with the "Broken" value; rerun with `-vv` only when it doesn't.
4. Restore the module from your copy, delete `src/docket/__pycache__`, and confirm `git diff` is as before.

A different failure from the "Broken" column is a note, not a finding; a pass is a finding.

| # | Module | Change | Deciding test | Correct | Broken |
|---|---|---|---|---|---|
| S1 | serialization.py, canonical_json | Change ensure_ascii=False to ensure_ascii=True | `tests/unit/test_canonical_json.py::test_canonical_json_keeps_the_existing_representation[unicode-null-order]` | unescaped Café and 雪 | Unicode escape sequences |
| S2 | serialization.py, canonical_json | Change sort_keys=True to sort_keys=False | `tests/unit/test_canonical_json.py::test_canonical_json_keeps_the_existing_representation[unicode-null-order]` | a before z | z before a |
| S3 | serialization.py, canonical_json | Change separators=(",", ":") to separators=(", ", ": ") | `tests/unit/test_canonical_json.py::test_canonical_json_keeps_the_existing_representation[unicode-null-order]` | compact JSON | spaces after separators |
| S4 | core.py, request comparison | Replace the canonical-string equality return with stored == request | `tests/integration/test_shared_creation.py::test_replays_compare_canonical_json_and_return_current_task_without_writes` | changed true-to-1 body raises key_reused | expected CoreError not raised |
| S5 | store.py, Store.transaction exception branch | Change self._connection.execute("ROLLBACK") to self._connection.execute("COMMIT") | `tests/integration/test_shared_creation.py::test_each_partial_create_rolls_back_every_write[keyed-key]` | tasks, audit and keys empty after forced failure | committed task remains |
| S6 | core.py, private creation helper | In its insertion call, replace at=at with at=clock.now() | `tests/integration/test_shared_creation.py::test_both_paths_keep_literal_task_and_audit_rows[keyed-agent]` | t1 plus one create audit at supplied timestamp | StopIteration from an extra clock read |

## 4. Probe

Run `.venv/bin/python docs/verification/probe-02j.py` from the repository root. It is a given file: do not edit it. Every line must end in `ok`; the last line must be `FAILURES 0`. A stop at the probe's own `assert` lines, before its self-check prints `ok`, is the probe's fault: report it under "For the architect", not as a finding. It touches no network, Keychain or real data folder.

The probe independently checks literal canonical bytes and the single insertion site, then forces three saved-key replays after close/reopen (including an ended task), three changed-body conflicts and a post-key interruption across reopen. It asserts unchanged tasks/audits and absent failed keys. `--oracle-only` checks the literal JSON table against the standard library first. On baseline, codec and sharing checks fail while persistence/rollback guards pass; no complete reference creation path was built.

## 5. Searches

Each prints nothing. A match is a finding against the rule it names.

| # | Rule | Command |
|---|---|---|
| Q1 | no network code | `git grep --untracked -n -E 'import (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)\|from (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)' -- src` |
| Q2 | no output outside the CLI | `git grep --untracked -n -E 'print\(\|logging\|logger\|warnings\.warn' -- src ':!src/docket/cli.py'` |
| Q3 | time read only in clock.py, through the module | `git grep --untracked -n -E 'datetime\.now\|datetime\.utcnow\|date\.today\|time\.time\(\|from docket\.(clock\|ids) import' -- src ':!src/docket/clock.py'` |
| Q4 | only the core writes tasks, audit rows, links and keys | `git grep --untracked -n -E '\.(insert_task\|update_task\|append_audit\|insert_link\|insert_request_key)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'` |
| Q5 | no model client | `git grep --untracked -n -E 'ollama\|anthropic\|openai\|langchain' -- src` |
| Q6 | no coverage or lint exclusions in this phase's modules | `git grep --untracked -n -E 'pragma: no cover\|noqa' -- src/docket/serialization.py src/docket/core.py src/docket/store.py` |

(In the table, `\|` is a `|` in the command.)

## 6. Reasonable variations

These are correct even though the spec does not spell them out:

- The private helper name, its parameter ordering and whether validated values are passed as keyword arguments. Both public creates still call it directly, with one insert and one create audit body.
- Removing private JSON wrappers or retaining policy-free forwarding wrappers; every real encoding and comparison still calls the module-based shared writer.
- Test organization inside the one new coder test file; no earlier tests or given files change.
- Private helpers inside the Scope modules, and extra behaviour tests in `*_more.py` files.

## 7. Verdict

Write `docs/reviews/phase-02j-shared-creation-and-serialization.md` in the form `docs/phase-conventions.md` gives (`# Review: Phase 2j`), then run `.venv/bin/python scripts/check_reports.py --phase 2j`; it must print `Reports OK.`
