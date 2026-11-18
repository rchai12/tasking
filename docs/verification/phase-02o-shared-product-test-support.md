# Verification guide: Phase 2o (Shared product test support)

Spec: `docs/phases/phase-02o-shared-product-test-support.md`. Follow `docs/phase-conventions.md` ("For the verifier"). Never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor, never read the Keychain, and never open the real data folder.

## 1. Coder ran

**Correction context (Nov 18):** the first implementation f0c9972 stopped on a spec-caused fixture collision, not a changed test body. Review the resumed diff from the corrected-handoff commit and inspect the whole existing eight-consumer/support implementation, including f0c9972. The original fixture dependency is superseded by store(tmp_path). The explicit seeded __all__ export replaces the no-op decorator. Corrected givens have 32 cases; preservation also runs all 28 real reference cases. All gates and searches are live again. No report should treat the first probe’s old success as runtime compatibility evidence.

Stop with FAIL ("the coder did not run") if any of these is missing:

- `tests/unit/test_product_test_support_more.py`
- `grep -c "^## Phase 2o: " docs/progress.md` prints `1`

Stop with FAIL ("the coder stopped") if that entry's first `Follow-ups` line starts with `Stopped:`, as "A stopped coder" in `docs/phase-conventions.md` says. With no entry, `git status --short` tells "the coder did not run" (no Scope path changed) from "the coder broke off without reporting" (Scope paths changed; name them under `For the architect`).

Stop with FAIL ("the baseline is not committed") if `git ls-files --error-unmatch docs/phases/phase-02o-shared-product-test-support.md tests/product_support_manifest.json tests/product_support_cases.py tests/unit/test_product_test_support.py docs/verification/probe-02o.py` fails: the diff gates can only be judged against a committed spec and given files.

## 2. Gates

Run each from the repository root, in this order: `.venv/bin/python scripts/accept.py --phase 2o --guide` runs them and the searches, one line each. Given test count: 32.

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_product_test_support.py` | `1261` or more passed, 0 failed, 0 errors |
| G2 | `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1293 passed, 0 failed, 0 skipped |
| G3 | `.venv/bin/python -m pytest tests/unit/test_product_test_support.py --no-cov -q` | `32 passed` |
| G4 | `.venv/bin/python -m coverage report --include=src/docket/core.py,src/docket/store.py,docket_tools/reports.py,docket_tools/acceptance.py,docket_tools/spotcheck.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| G5 | `.venv/bin/python docs/verification/probe-02o.py` | last line `FAILURES 0` |
| G6 | `grep -c "^## Phase 2o: " docs/progress.md` | `1` |
| G7 | `.venv/bin/python scripts/check_reports.py --phase 2o` | `Reports OK.` |
| G8 | `git diff HEAD --stat -- tests/product_support_manifest.json tests/product_support_cases.py tests/unit/test_product_test_support.py docs/verification/probe-02o.py` | no output |
| G9 | `git status --short` | only the Scope paths |
| G10 | `.venv/bin/python -m pip list --format=freeze \| wc -l` | `39` (unchanged; no installation is authorized) |

## 3. Spot checks

Audit explicit shared bindings in all eight consumers first. Seven import the same empty store/path fixtures; the seeded module imports base_store and retains only its original seed adapter. No fixture plugin, global guard or settings/clock lookup is added. The store depends on tmp_path directly; path case labels must never be used as database paths. The seeded adapter declares only __all__ = ["base_store"] and its original fixture decorator, without a no-op decorator. The strict helper checks CoreError type/code/text, and old support functions, all 304 scoped case IDs, other bodies and frozen source/config files remain pinned. No test files or IDs move and both coverage gates stay intact.

Run mutations only in a clean disposable implementation checkout with imports directed at that checkout. S1–S2 were checked using the existing strict core helper as a stand-in, S3 against the discarded fixture-only patch, and S4–S6 against baseline preservation guards. No complete shared-support migration was built. For non-src helper/test targets use the manual restoration procedure; the product mutation in S3 is an intentional disposable test of the lifetime assertion, not an authorized implementation edit.

For a module under `src/`, write the change as an exact old and new text in the module the coder wrote and run `.venv/bin/python scripts/spot_check.py <module> --old '<old>' --new '<new>' --test '<deciding test>' --row S<n>`; it restores the module and prints one line. For any other file:
1. Copy the module outside the repository.
2. Make the change described in the module the coder wrote.
3. Run the deciding test with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest '<test>' --no-cov -q --tb=line`, and confirm it fails with the "Broken" value; rerun with `-vv` only when it doesn't.
4. Restore the module from your copy, delete `src/docket/__pycache__`, and confirm `git diff` is as before.

A different failure from the "Broken" column is a note, not a finding; a pass is a finding.

| # | Module | Change | Deciding test | Correct | Broken |
|---|---|---|---|---|---|
| S1 | tests/support.py, refused | Replace the code/string tuple assertion with a code-only assertion | `tests/unit/test_product_test_support.py::test_shared_refusal_checks_code_text_and_exception_type[wrong-text]` | wrong text triggers AssertionError | expected AssertionError not raised |
| S2 | tests/support.py, refused | Change pytest.raises(CoreError) to pytest.raises(Exception) | `tests/unit/test_product_test_support.py::test_shared_refusal_checks_code_text_and_exception_type[other-error]` | original OtherError propagates | expected OtherError not raised |
| S3 | src/docket/store.py, Store.close | Replace self._connection.close() with return None | `tests/unit/test_product_test_support.py::test_shared_store_is_empty_and_closes_once_on_every_exit[normal]` | closed store raises ProgrammingError | expected ProgrammingError not raised |
| S4 | tests/integration/test_core.py, test_the_codes | Replace assert issubclass(CoreError, Exception) with assert True | `tests/unit/test_product_test_support.py::test_existing_cases_assertions_and_helpers_remain_unchanged[tests/integration/test_core.py]` | pinned AST | changed AST |
| S5 | tests/integration/test_store_links.py, seeded store | Replace the Pay rent seed title with Changed in the two-title tuple | `tests/unit/test_product_test_support.py::test_seeded_link_fixture_keeps_exact_setup_and_values` | original seed AST | changed seed AST |
| S6 | tests/integration/test_core.py | Rename test_the_codes to hidden_the_codes | `tests/unit/test_product_test_support.py::test_all_304_existing_consumer_cases_keep_their_nodeids_and_sections` | 304 original IDs | missing original ID |

## 4. Probe

Run `.venv/bin/python docs/verification/probe-02o.py` from the repository root. It is a given file: do not edit it. Every line must end in `ok`; the last line must be `FAILURES 0`. A stop at the probe's own `assert` lines, before its self-check prints `ok`, is the probe's fault: report it under "For the architect", not as a finding. It touches no network, Keychain or real data folder.

The probe self-checks its eight-file/304-case inventory, then verifies actual shared fixture/refusal identities, strict refusal behavior, real temporary Store lifetime, unchanged body/seed/collection fingerprints and actual execution of all 28 reference cases. Runtime execution must pass, not just collection. Baseline reports three missing-helper/binding failures and passes the preservation guard. Every SQLite database and case is synthetic. `--oracle-only` must print FAILURES 0; no new helper import can crash the main run.

## 5. Searches

Each prints nothing. A match is a finding against the rule it names.

| # | Rule | Command |
|---|---|---|
| Q1 | no network code in product, tooling or shared support | `git grep --untracked -n -E 'import (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)\|from (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)' -- src docket_tools tests/support.py` |
| Q2 | no output outside the product CLI | `git grep --untracked -n -E 'print\(\|logging\|logger\|warnings\.warn' -- src docket_tools tests/support.py ':!src/docket/cli.py'` |
| Q3 | time read only through the existing clock module | `git grep --untracked -n -E 'datetime\.now\|datetime\.utcnow\|date\.today\|time\.time\(\|from docket\.(clock\|ids) import' -- src docket_tools tests/support.py ':!src/docket/clock.py'` |
| Q4 | no new task mutation in shared support | `git grep --untracked -n -E '\.(insert_task\|update_task\|append_audit\|insert_link\|insert_request_key)\(' -- src docket_tools tests/support.py ':!src/docket/core.py' ':!src/docket/store.py'` |
| Q5 | no model client in product, tooling or support | `git grep --untracked -n -E 'ollama\|anthropic\|openai\|langchain' -- src docket_tools tests/support.py` |
| Q6 | no coverage or lint exclusions in this phase's modules | `git grep --untracked -n -E 'pragma: no cover\|noqa' -- tests/support.py` |

(In the table, `\|` is a `|` in the command.)

## 6. Reasonable variations

These are correct even though the spec does not spell them out:

- Type imports and import layout, including separate explicit self-alias lines accepted by Ruff. Imported fixture decorators still have no explicit name, allowing the base_store alias.
- Private implementation details of the three new support contracts, retaining actual context ownership and strict refusal behavior; the four existing support function bodies remain exact.
- Additional deciding checks in the one new coder test file. Existing consumer cases/bodies, node IDs, seeded values, global configuration and application/tooling source are not variation points.
- Private helpers inside the Scope modules, and extra behaviour tests in `*_more.py` files.

## 7. Verdict

Write `docs/reviews/phase-02o-shared-product-test-support.md` in the form `docs/phase-conventions.md` gives (`# Review: Phase 2o`), then run `.venv/bin/python scripts/check_reports.py --phase 2o`; it must print `Reports OK.`
