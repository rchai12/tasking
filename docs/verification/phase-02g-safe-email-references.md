# Verification guide: Phase 2g (Safe email references)

Spec: `docs/phases/phase-02g-safe-email-references.md`. Follow `docs/phase-conventions.md` ("For the verifier"). Never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor, never read the Keychain, and never open the real data folder.

## 1. Coder ran

Stop with FAIL ("the coder did not run") if any of these is missing:

- `src/docket/references.py`
- `tests/integration/test_reference_coverage.py`
- `grep -c "^## Phase 2g: " docs/progress.md` prints `1`

Stop with FAIL ("the coder stopped") if that entry's first `Follow-ups` line starts with `Stopped:`, as "A stopped coder" in `docs/phase-conventions.md` says. With no entry, `git status --short` tells "the coder did not run" (no Scope path changed) from "the coder broke off without reporting" (Scope paths changed; name them under `For the architect`).

Stop with FAIL ("the baseline is not committed") if `git ls-files --error-unmatch docs/phases/phase-02g-safe-email-references.md src/docket/schema.py scripts/critical_modules.txt tests/reference_cases.py tests/unit/test_references.py tests/integration/test_core_references.py tests/integration/test_reference_migration.py tests/e2e/test_reference_intake.py tests/integration/test_store.py tests/integration/test_store_links.py tests/integration/test_server.py docs/verification/probe-02g.py` fails: the diff gates can only be judged against a committed spec and given files.

## 2. Gates

Run each from the repository root, in this order: `.venv/bin/python scripts/accept.py --phase 2g --guide` runs them and the searches, one line each. Given test count: 84.

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_references.py --ignore=tests/integration/test_core_references.py --ignore=tests/integration/test_reference_migration.py --ignore=tests/e2e/test_reference_intake.py` | at least 837 passed, 0 failed (the coder's `*_more.py` tests add to the count) |
| G2 | `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 921 passed, 0 failed, 0 skipped |
| G3 | `.venv/bin/python -m pytest tests/unit/test_references.py tests/integration/test_core_references.py tests/integration/test_reference_migration.py tests/e2e/test_reference_intake.py --no-cov -q` | `84 passed` |
| G4 | `.venv/bin/python -m coverage report --include=src/docket/references.py,src/docket/core.py,src/docket/store.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| G5 | `.venv/bin/python docs/verification/probe-02g.py` | last line `FAILURES 0` |
| G6 | `grep -c "^## Phase 2g: " docs/progress.md` | `1` |
| G7 | `.venv/bin/python scripts/check_reports.py --phase 2g` | `Reports OK.` |
| G8 | `git diff HEAD --stat -- src/docket/schema.py scripts/critical_modules.txt tests/reference_cases.py tests/unit/test_references.py tests/integration/test_core_references.py tests/integration/test_reference_migration.py tests/e2e/test_reference_intake.py tests/integration/test_store.py tests/integration/test_store_links.py tests/integration/test_server.py docs/verification/probe-02g.py` | no output |
| G9 | `git status --short` | only the Scope paths |
| G10 | `.venv/bin/python -m pip list --format=freeze \| wc -l` | `39` (unchanged; no package is added) |

## 3. Spot checks

Before mutations, confirm migrations 1 and 2 are unchanged and that the given migration/earlier-version-pin tests have no diff from the committed planning baseline. Check reference validation is used in all three core entry points and before the migration touches tables. Confirm that it scans tasks in every state and never rewrites audit or retry JSON.

Run spot checks in a clean disposable checkout containing the committed planning baseline and the implementation under review, with imports directed at that checkout. Never mutate the user's live working tree: process termination can bypass the runner's restoration. Adapt each conceptual one-line mutation to the coder's actual helpers. The fixed clock sequence is a defence layer: S3–S5 intentionally fail at an unexpected clock read before SQLite's length CHECK can intervene.

For a module under `src/`, write the change as an exact old and new text in the module the coder wrote and run `.venv/bin/python scripts/spot_check.py <module> --old '<old>' --new '<new>' --test '<deciding test>' --row S<n>`; it restores the module and prints one line. For any other file:
1. Copy the module outside the repository.
2. Make the change described in the module the coder wrote.
3. Run the deciding test with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest '<test>' --no-cov -q --tb=line`, and confirm it fails with the "Broken" value; rerun with `-vv` only when it doesn't.
4. Restore the module from your copy, delete `src/docket/__pycache__`, and confirm `git diff` is as before.

A different failure from the "Broken" column is a note, not a finding; a pass is a finding.

| # | Module | Change | Deciding test | Correct | Broken |
|---|---|---|---|---|---|
| S1 | `references.py` | Change `MESSAGE_ID_MAX` from 512 to 513 | `tests/unit/test_references.py::test_reference_limits` | 512 | 513 |
| S2 | `references.py`, forbidden categories | Remove `Cf` from the forbidden category set only | `tests/unit/test_references.py::test_reference_character_categories[format]` | false | true |
| S3 | `core.py`, shared email reference check | Replace the message-ID policy call with a nonempty-string-only check | `tests/integration/test_core_references.py::test_invalid_references_never_write[escape-plain]` | `CoreError(invalid_reference)` | `StopIteration` at the clock |
| S4 | `core.py`, `create_task_once` | Omit its call to the shared reference check | `tests/integration/test_core_references.py::test_invalid_references_never_write[id-long-keyed]` | `CoreError(invalid_reference)` | `StopIteration` at the clock |
| S5 | `core.py`, `add_link` | Replace the link policy call with a nonempty-string-only check | `tests/integration/test_core_references.py::test_invalid_references_never_write[newline-link]` | `CoreError(invalid_reference)` | `StopIteration` at the clock |
| S6 | `store.py`, preflight | Skip task-reference scanning while keeping link scanning | `tests/integration/test_reference_migration.py::test_invalid_legacy_reference_refuses_without_data_changes[escape-tasks-t1]` | ID/field `StoreError` | upgrade succeeds; expected error not raised |
| S7 | `store.py`, preflight | Skip link-reference scanning while keeping task scanning | `tests/integration/test_reference_migration.py::test_invalid_legacy_reference_refuses_without_data_changes[format-links-l1]` | ID/field `StoreError` | upgrade succeeds; expected error not raised |
| S8 | `store.py`, migration 3 | Omit disabling foreign keys before its transaction | `tests/integration/test_reference_migration.py::test_migration_preserves_rows_ids_sequences_and_invariants[populated-v2]` | preserved snapshot | `IntegrityError` at the table rebuild |
| S9 | `store.py`, migration cleanup | Omit restoring foreign keys on the SQL-failure path | `tests/integration/test_reference_migration.py::test_failed_migration_rolls_back_closes_and_restores_foreign_keys` | restored flags `[1]` | `[0]` |
| S10 | `store.py`, failed construction | Omit closing the connection when migration raises | `tests/integration/test_reference_migration.py::test_failed_migration_rolls_back_closes_and_restores_foreign_keys` | closed `[True]` | `[]` |
| S11 | `store.py`, migration 3 integrity check | Ignore a nonempty foreign-key check result | `tests/integration/test_reference_migration.py::test_foreign_key_check_failure_refuses_the_upgrade` | `StoreError(invalid reference migration)` | upgrade succeeds; expected error not raised |

## 4. Probe

Run `.venv/bin/python docs/verification/probe-02g.py` from the repository root. It is a given file: do not edit it. Every line must end in `ok`; the last line must be `FAILURES 0`. A stop at the probe's own `assert` lines, before its self-check prints `ok`, is the probe's fault: report it under "For the architect", not as a finding. It touches no network, Keychain or real data folder.

The probe adds Unicode DEL and word-joiner cases, repeats valid task/link intake across a populated upgrade and reopen, and checks 12 legacy refusals with unchanged rows and version. `--oracle-only` checks its literal cases and Unicode-category assumptions without opening a store.

## 5. Searches

Each prints nothing. A match is a finding against the rule it names.

| # | Rule | Command |
|---|---|---|
| Q1 | no network code | `git grep --untracked -n -E 'import (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)\|from (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)' -- src` |
| Q2 | no output outside the CLI | `git grep --untracked -n -E 'print\(\|logging\|logger\|warnings\.warn' -- src ':!src/docket/cli.py'` |
| Q3 | time read only in clock.py, through the module | `git grep --untracked -n -E 'datetime\.now\|datetime\.utcnow\|date\.today\|time\.time\(\|from docket\.(clock\|ids) import' -- src ':!src/docket/clock.py'` |
| Q4 | only the core writes tasks, audit rows, links and keys | `git grep --untracked -n -E '\.(insert_task\|update_task\|append_audit\|insert_link\|insert_request_key)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'` |
| Q5 | no model client | `git grep --untracked -n -E 'ollama\|anthropic\|openai\|langchain' -- src` |
| Q6 | no coverage or lint exclusions in this phase's modules | `git grep --untracked -n -E 'pragma: no cover\|noqa' -- src/docket/references.py src/docket/core.py src/docket/store.py` |
| Q7 | no environment, machine zone or locale in this phase's modules | `git grep --untracked -n -E 'os\.environ\|getenv\(\|strftime\(\|import locale' -- src/docket/references.py src/docket/core.py src/docket/store.py` |

(In the table, `\|` is a `|` in the command.)

## 6. Reasonable variations

These are correct even though the spec does not spell them out:

- Private helper names and placement inside the Scope modules, including a shared preflight iterator or separate table scans with the specified order.
- A general migration-failure close wrapper is acceptable; it must not change other migrations or move version-read locking into this phase.
- Reference whitespace and URL-like text stay unchanged; rejecting them or adding escaping is not a reasonable variation.
- Extra behaviour tests belong only in the Scope test file; all given files stay unchanged.

## 7. Verdict

Write `docs/reviews/phase-02g-safe-email-references.md` in the form `docs/phase-conventions.md` gives (`# Review: Phase 2g`), then run `.venv/bin/python scripts/check_reports.py --phase 2g`; it must print `Reports OK.`
