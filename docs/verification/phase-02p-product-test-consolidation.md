# Verification guide: Phase 2p (Product test consolidation)

Spec: `docs/phases/phase-02p-product-test-consolidation.md`. Follow `docs/phase-conventions.md` ("For the verifier"). Never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor, never read the Keychain, and never open the real data folder.

## 1. Coder ran

Stop with FAIL ("the coder did not run") if any of these is missing:

- `tests/unit/test_product_selector_runtime.py`
- `grep -c "^## Phase 2p: " docs/progress.md` prints `1`

Stop with FAIL ("the coder stopped") if that entry's first `Follow-ups` line starts with `Stopped:`, as "A stopped coder" in `docs/phase-conventions.md` says. With no entry, `git status --short` tells "the coder did not run" (no Scope path changed) from "the coder broke off without reporting" (Scope paths changed; name them under `For the architect`).

Stop with FAIL ("the baseline is not committed") if `git ls-files --error-unmatch docs/phases/phase-02p-product-test-consolidation.md tests/product_consolidation_manifest.json tests/product_consolidation_cases.py tests/unit/test_product_consolidation.py docs/verification/probe-02p.py` fails: the diff gates can only be judged against a committed spec and given files.

## 2. Gates

Run each from the repository root, in this order: `.venv/bin/python scripts/accept.py --phase 2p --guide` runs them and the searches, one line each. Given test count: 24.

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_product_consolidation.py` | at least 1295 passed, 0 failed (the coder's `*_more.py` tests add to the count) |
| G2 | `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1319 passed, 0 failed, 0 skipped |
| G3 | `.venv/bin/python -m pytest tests/unit/test_product_consolidation.py --no-cov -q` | `24 passed` |
| G4 | `.venv/bin/python -m coverage report --include=src/docket/config.py,src/docket/server.py,src/docket/core.py,src/docket/store.py,docket_tools/reports.py,docket_tools/acceptance.py,docket_tools/spotcheck.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| G5 | `.venv/bin/python docs/verification/probe-02p.py` | last line `FAILURES 0` |
| G6 | `grep -c "^## Phase 2p: " docs/progress.md` | `1` |
| G7 | `.venv/bin/python scripts/check_reports.py --phase 2p` | `Reports OK.` |
| G8 | `git diff HEAD --stat -- tests/product_consolidation_manifest.json tests/product_consolidation_cases.py tests/unit/test_product_consolidation.py docs/verification/probe-02p.py` | no output |
| G9 | `git status --short` | only the Scope paths |
| G10 | `.venv/bin/python -m pip list --format=freeze \| wc -l` | `39` (unchanged; no dependency added) |

## 3. Spot checks

Judge all four merges and all six exact document migrations, including deleted files, against the committed planning baseline. The manifest supplies the old-to-new case mapping. Do not weaken a fingerprint or bless a changed historical count as a variation. Existing later product continuation modules are explicitly outside this bounded phase.

For a module under `src/`, write the change as an exact old and new text in the module the coder wrote and run `.venv/bin/python scripts/spot_check.py <module> --old '<old>' --new '<new>' --test '<deciding test>' --row S<n>`; it restores the module and prints one line. For any other file:
1. Copy the module outside the repository.
2. Make the change described in the module the coder wrote.
3. Run the deciding test with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest '<test>' --no-cov -q --tb=line`, and confirm it fails with the "Broken" value; rerun with `-vv` only when it doesn't.
4. Restore the module from your copy, delete `src/docket/__pycache__`, and confirm `git diff` is as before.

A different failure from the "Broken" column is a note, not a finding; a pass is a finding.

| # | Module | Change | Deciding test | Correct | Broken |
|---|---|---|---|---|---|
| S1 | `tests/unit/test_settings_port.py` | replace the one occurrence of `get_settings().web_port == 8767` with `get_settings().web_port == 8768` | `tests/unit/test_product_consolidation.py::test_canonical_modules_keep_exact_bodies_and_remove_continuations[tests/unit/test_settings_port.py]` | exact body inventory | AssertionError: changed body inventory |
| S2 | `tests/unit/test_settings_port.py` | rename `def test_a_bad_time_zone_is_reported_before_the_port(` to `def removed_a_bad_time_zone_is_reported_before_the_port(` | `tests/unit/test_product_consolidation.py::test_all_existing_cases_keep_their_mapping_and_core_section[tests/unit/test_settings_port.py]` | 13 mapped cases | AssertionError: missing case |
| S3 | `tests/e2e/test_cli_tasks.py` | rename `def test_a_newer_schema_is_refused(` to `def removed_a_newer_schema_is_refused(` | `tests/unit/test_product_consolidation.py::test_moved_cases_execute_with_the_canonical_fixtures[tests/e2e/test_cli_tasks.py]` | 3 passed | AssertionError: selector not found |
| S4 | `docs/phases/phase-02a-keyed-intake.md` | in its migrated git diff HEAD guard, replace the one `tests/e2e/test_cli_tasks.py` token with `tests/e2e/test_cli_tasks_more.py` | `tests/unit/test_product_consolidation.py::test_historical_documents_apply_only_the_recorded_selector_migration[docs/phases/phase-02a-keyed-intake.md]` | exact document fingerprint | AssertionError: document fingerprint |
| S5 | `tests/support.py` | replace the one `"COLUMNS": "200"` with `"COLUMNS": "199"` in the runner configuration | `tests/unit/test_product_consolidation.py::test_other_tests_product_tooling_and_global_guards_are_unchanged` | frozen bytes | AssertionError: tests/support.py |

## 4. Probe

Run `.venv/bin/python docs/verification/probe-02p.py` from the repository root. It is a given file: do not edit it. Every line must end in `ok`; the last line must be `FAILURES 0`. A stop at the probe's own `assert` lines, before its self-check prints `ok`, is the probe's fault: report it under "For the architect", not as a finding. It touches no network, Keychain or real data folder.

The probe runs the same immutable mapping independently of pytest discovery and summarizes every family, runtime, historical document/command and frozen boundary; it makes no extra randomized coverage claim. Its oracle validates literal mapping totals before touching the candidate. The eight moved cases run as real pytest consumers. Historical positive selectors also execute through the coder-owned runtime checks. No real services or Keychain access occurs.

## 5. Searches

Each prints nothing. A match is a finding against the rule it names.

| # | Rule | Command |
|---|---|---|
| Q1 | No new network client imports | `git grep --untracked -n -E 'import (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)\|from (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)' -- src docket_tools tests/product_consolidation_cases.py` |
| Q2 | No new output or logging outside CLI | `git grep --untracked -n -E 'print\(\|logging\|logger\|warnings\.warn' -- src docket_tools tests/product_consolidation_cases.py ':!src/docket/cli.py'` |
| Q3 | Clock and IDs only through their modules | `git grep --untracked -n -E 'datetime\.now\|datetime\.utcnow\|date\.today\|time\.time\(\|from docket\.(clock\|ids) import' -- src docket_tools tests/product_consolidation_cases.py ':!src/docket/clock.py'` |
| Q4 | Task writes only through existing owners | `git grep --untracked -n -E '\.(insert_task\|update_task\|append_audit\|insert_link\|insert_request_key)\(' -- src docket_tools tests/product_consolidation_cases.py ':!src/docket/core.py' ':!src/docket/store.py'` |
| Q5 | No model client imports | `git grep --untracked -n -E 'ollama\|anthropic\|openai\|langchain' -- src docket_tools tests/product_consolidation_cases.py` |
| Q6 | no coverage or lint exclusions in this phase's modules | `git grep --untracked -n -E 'pragma: no cover\|noqa' -- tests/product_consolidation_cases.py tests/unit/test_product_selector_runtime.py` |

(In the table, `\|` is a `|` in the command.)

## 6. Reasonable variations

These are correct even though the spec does not spell them out:

- Regrouped imports and reordered top-level definitions are allowed only when the normalized import union and exact non-import AST inventory remain equal. Duplicate identical server constants are deduplicated; no other node is removed.
- Coder-owned helper organization inside tests/unit/test_product_selector_runtime.py may vary. The manifest, exact document patches, historical counts, file deletions, case IDs, existing bodies and frozen inventory do not vary. No new continuation file or compatibility shim is permitted.

## 7. Verdict

Write `docs/reviews/phase-02p-product-test-consolidation.md` in the form `docs/phase-conventions.md` gives (`# Review: Phase 2p`), then run `.venv/bin/python scripts/check_reports.py --phase 2p`; it must print `Reports OK.`
