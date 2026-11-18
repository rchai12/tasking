# Verification guide: Phase 2q (Product behaviour test paths)

Spec: `docs/phases/phase-02q-product-behaviour-test-paths.md`. Follow `docs/phase-conventions.md` ("For the verifier"). Never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor, never read the Keychain, and never open the real data folder.

## 1. Coder ran

Stop with FAIL ("the coder did not run") if any of these is missing:

- `tests/integration/test_creation_transactions_and_retries.py`
- `tests/integration/test_domain_adapter_contracts.py`
- `tests/integration/test_task_sql_contracts.py`
- `tests/integration/test_audit_link_key_contracts.py`
- `tests/unit/test_product_support_runtime.py`
- `grep -c "^## Phase 2q: " docs/progress.md` prints `1`

Stop with FAIL ("the coder stopped") if that entry's first `Follow-ups` line starts with `Stopped:`, as "A stopped coder" in `docs/phase-conventions.md` says. With no entry, `git status --short` tells "the coder did not run" (no Scope path changed) from "the coder broke off without reporting" (Scope paths changed; name them under `For the architect`).

Stop with FAIL ("the baseline is not committed") if `git ls-files --error-unmatch docs/phases/phase-02q-product-behaviour-test-paths.md tests/product_organization_manifest.json tests/product_organization_cases.py tests/unit/test_product_organization.py docs/verification/probe-02q.py` fails: the diff gates can only be judged against a committed spec and given files.

## 2. Gates

Run each from the repository root, in this order: `.venv/bin/python scripts/accept.py --phase 2q --guide` runs them and the searches, one line each. Given test count: 28.

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_product_organization.py` | at least 1321 passed, 0 failed (the coder's `*_more.py` tests add to the count) |
| G2 | `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1349 passed, 0 failed, 0 skipped |
| G3 | `.venv/bin/python -m pytest tests/unit/test_product_organization.py --no-cov -q` | `28 passed` |
| G4 | `.venv/bin/python -m coverage report --include=src/docket/core.py,src/docket/store.py,src/docket/domain.py,src/docket/parsing.py,docket_tools/reports.py,docket_tools/acceptance.py,docket_tools/spotcheck.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| G5 | `.venv/bin/python docs/verification/probe-02p.py` | last line `FAILURES 0` |
| G6 | `.venv/bin/python docs/verification/probe-02q.py` | last line `FAILURES 0` |
| G7 | `grep -c "^## Phase 2q: " docs/progress.md` | `1` |
| G8 | `.venv/bin/python scripts/check_reports.py --phase 2q` | `Reports OK.` |
| G9 | `git diff HEAD --stat -- tests/product_organization_manifest.json tests/product_organization_cases.py tests/unit/test_product_organization.py docs/verification/probe-02q.py` | no output |
| G10 | `git status --short` | only the Scope paths |
| G11 | `.venv/bin/python -m pip list --format=freeze \| wc -l` | `39` (unchanged; no dependency added) |

## 3. Spot checks

Judge against the committed Phase 2q planning baseline. Verify that the five module contents are byte-identical and all other existing tests are frozen. The Phase 2p inventory must change exactly five keys with unchanged values, not drop entries or refresh hashes. Guide-only assertion diagnostics that name the changed path are the expected fingerprint failures. The older guides receive only their literal authorized path migrations; no old review is rewritten.

For a module under `src/`, write the change as an exact old and new text in the module the coder wrote and run `.venv/bin/python scripts/spot_check.py <module> --old '<old>' --new '<new>' --test '<deciding test>' --row S<n>`; it restores the module and prints one line. For any other file:
1. Copy the module outside the repository.
2. Make the change described in the module the coder wrote.
3. Run the deciding test with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest '<test>' --no-cov -q --tb=line`, and confirm it fails with the "Broken" value; rerun with `-vv` only when it doesn't.
4. Restore the module from your copy, delete `src/docket/__pycache__`, and confirm `git diff` is as before.

A different failure from the "Broken" column is a note, not a finding; a pass is a finding.

| # | Module | Change | Deciding test | Correct | Broken |
|---|---|---|---|---|---|
| S1 | `tests/integration/test_creation_transactions_and_retries.py` | append one blank line | `tests/unit/test_product_organization.py::test_product_files_move_byte_identically_without_shims[tests/integration/test_shared_creation_more.py]` | original bytes | AssertionError naming destination |
| S2 | `tests/integration/test_creation_transactions_and_retries.py` | rename `def test_one_transaction_holds_creation_and_the_helper_does_not_nest(` to `def removed_one_transaction_holds_creation_and_the_helper_does_not_nest(` | `tests/unit/test_product_organization.py::test_mapped_cases_preserve_parameters_and_core_ownership[tests/integration/test_shared_creation_more.py]` | 7 mapped cases | AssertionError naming destination |
| S3 | `tests/unit/test_product_support_runtime.py` | rename `def test_refused_invokes_the_callback_once_and_does_not_catch_other_errors(` to `def removed_refused_invokes_the_callback_once_and_does_not_catch_other_errors(` | `tests/unit/test_product_organization.py::test_moved_consumers_execute_with_existing_fixtures[tests/unit/test_product_test_support_more.py]` | 2 passed | AssertionError: 1 passed |
| S4 | `tests/product_consolidation_manifest.json` | set the migrated frozen value for tests/integration/test_creation_transactions_and_retries.py to 64 zeroes | `tests/unit/test_product_organization.py::test_phase_2p_inventory_migrates_only_the_five_frozen_keys` | all original fingerprints | AssertionError naming manifest |
| S5 | `docs/verification/phase-02j-shared-creation-and-serialization.md` | in the Coder ran bullet, replace tests/integration/test_creation_transactions_and_retries.py with tests/integration/test_shared_creation_more.py | `tests/unit/test_product_organization.py::test_historical_paths_follow_only_the_literal_document_plan[docs/verification/phase-02j-shared-creation-and-serialization.md]` | exact migrated document | AssertionError naming guide |
| S6 | `tests/support.py` | replace the one `"COLUMNS": "200"` with `"COLUMNS": "199"` | `tests/unit/test_product_organization.py::test_other_tests_product_tooling_and_global_guards_stay_unchanged` | frozen bytes | AssertionError: tests/support.py |

## 4. Probe

Run `.venv/bin/python docs/verification/probe-02q.py` from the repository root. It is a given file: do not edit it. Every line must end in `ok`; the last line must be `FAILURES 0`. A stop at the probe's own `assert` lines, before its self-check prints `ok`, is the probe's fault: report it under "For the architect", not as a finding. It touches no network, Keychain or real data folder.

The probe independently orchestrates the same byte, mapping, runtime, document, older-manifest and frozen checks outside pytest discovery. It claims no extra randomized cases. The oracle pins 27 unique cases before inspecting the candidate. The earlier Phase 2p probe must also stay green after its five-key inventory migration; no helper or old hash is weakened.

## 5. Searches

Each prints nothing. A match is a finding against the rule it names.

| # | Rule | Command |
|---|---|---|
| Q1 | No new network clients | `git grep --untracked -n -E 'import (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)\|from (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)' -- src docket_tools tests/product_organization_cases.py` |
| Q2 | No new logging or output outside CLI | `git grep --untracked -n -E 'print\(\|logging\|logger\|warnings\.warn' -- src docket_tools tests/product_organization_cases.py ':!src/docket/cli.py'` |
| Q3 | Clock and IDs only through their modules | `git grep --untracked -n -E 'datetime\.now\|datetime\.utcnow\|date\.today\|time\.time\(\|from docket\.(clock\|ids) import' -- src docket_tools tests/product_organization_cases.py ':!src/docket/clock.py'` |
| Q4 | Task writes stay in existing owners | `git grep --untracked -n -E '\.(insert_task\|update_task\|append_audit\|insert_link\|insert_request_key)\(' -- src docket_tools tests/product_organization_cases.py ':!src/docket/core.py' ':!src/docket/store.py'` |
| Q5 | No model client import | `git grep --untracked -n -E 'ollama\|anthropic\|openai\|langchain' -- src docket_tools tests/product_organization_cases.py` |
| Q6 | no coverage or lint exclusions in this phase's modules | `git grep --untracked -n -E 'pragma: no cover\|noqa' -- tests/product_organization_cases.py` |

(In the table, `\|` is a `|` in the command.)

## 6. Reasonable variations

These are correct even though the spec does not spell them out:

- File move mechanics and the order of literal reference edits may vary. Destination contents, old-path deletion, all case IDs, document plans and the older manifest result must be exact.
- No moved source bytes, fixture definitions, import layout, hash values or configuration may vary. No new continuation file or compatibility mechanism is approved. The coder does not regenerate the immutable given inventory.

## 7. Verdict

Write `docs/reviews/phase-02q-product-behaviour-test-paths.md` in the form `docs/phase-conventions.md` gives (`# Review: Phase 2q`), then run `.venv/bin/python scripts/check_reports.py --phase 2q`; it must print `Reports OK.`
