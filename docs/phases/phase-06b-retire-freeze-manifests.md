# Phase 6b: Retire the freeze manifests

## Goal

Stop pinning the repository's history. Three manifests pin the sha256 of nearly every product module, script, `AGENTS.md`, `pyproject.toml`, 90 test files and 24 reviews, and two structural freezes hold 38 and 86 AST nodes of `core.py` and `store.py` byte-identical. They proved that Phases 2n to 2q moved files without changing them; those phases are verified, and the pins now make every unplanned fix and every refactor (Phases 5a to 5c) need a rehash and a second review. This phase deletes them and the tests that read only them, keeps every behaviour test, and keeps one pin list for the verifier reviews in `docs/reviews/`. It changes no product code, script or tooling module. It leaves the tooling `*_more.py` files (2r) and the store refactors (5a to 5c) for later.

Sections: `core`. The `tooling` section runs in the full check.

Follow `docs/phase-conventions.md`. N is 1719, the tests the previous phase left passing; this phase retires 101 tests.

Start: `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_review_pins.py` must show `1719 passed`. The ignored file is this phase's given test.

## Facts

- The pins live in `tests/product_support_manifest.json` (38 frozen paths), `tests/product_organization_manifest.json` (145) and `tests/product_consolidation_manifest.json` (142), read through `tests/product_support_cases.py`, `tests/product_organization_cases.py`, `tests/product_consolidation_cases.py` and the shared byte or AST check `assert_preserved` in `tests/preservation_cases.py`. `tests/tooling_boundary_manifest.json` pins the three `docket_tools` modules' bytes, eleven tooling tests' normalized AST and the product critical-module list; `tests/tooling_boundary_cases.py` reads it.
- These tests read only the pins or replay historical moves, and go: all of `test_feature_preservation.py` (9 tests), `test_product_consolidation.py` (24), `test_product_organization.py` (28) and `test_product_selector_runtime.py` (2); seven functions in `test_product_test_support.py` (24 of its 32 tests); two in `test_tooling_boundary.py` (14 of its 33). That is 101 tests, so the suite goes from 1,719 to 1,653 with the 35 given.
- These stay, unchanged in what they check: the eight shared-support behaviour tests in `test_product_test_support.py`, both tests in `test_product_support_runtime.py`, the other 19 tests in `test_tooling_boundary.py`, all of `test_tooling_boundary_more.py`, and the store and task boundary tests (`test_store_table_boundaries.py`, `test_task_table_boundary.py`, `test_audit_link_key_contracts.py`, `test_task_sql_contracts.py`), which check SQL ownership and rollback behaviour, not bytes.
- No test outside the files named above imports a retired module or reads a manifest (`git grep` on `tests`, `scripts` and `docket_tools`). Nothing in `src/`, `scripts/` or `docket_tools/` reads a manifest.
- The retired tests cover no product or tooling line that the kept tests miss: both 100% gates in `check.py` pass without them.
- The 31 reviews, `phase-00` through `phase-06a`, are pinned in the given `tests/review_pins.json`. A review written after this spec (6b's own included) starts unpinned; the architect pins it in the next spec's commit.

## Owner's decisions

- **Freezes (2026-11-21):** delete the byte pins on product code, scripts, `AGENTS.md`, `pyproject.toml`, the gate lists and tests, and the AST freezes; keep one manifest pinning `docs/reviews/` (not every pin retired, not kept as they are). Verifiers judge given files with `git diff` against the phase's base commit.
- **New reviews (2026-11-21):** the architect pins each passed phase's review in the next spec's commit (not the verifier on its own review, not a test that fails while any review is unpinned).

## Architect's decisions

- The pins of `docket_tools` and of the tooling tests' AST go too: they are the same kind of history as the product pins. The tooling-boundary behaviour (separate gate lists, wrappers bound to `docket_tools`, a src-only product) stays tested.
- The fake coverage in `tests/tooling_boundary_cases.py` reads the two gate lists from `scripts/`, so adding a critical module (6d adds the MCP modules) needs no test edit.
- The kept shared-support tests stay in `test_product_test_support.py`; renaming or merging test files is 2r's work.
- The given test checks the pins with plain sha256 and fails on any byte; there is no tool that rewrites them.
- Probes stay given files frozen with their phase; this phase's probe compares the collected test ids with the spec commit's.

## Requirements

1. **Delete** these files: `tests/preservation_cases.py`, `tests/product_consolidation_cases.py`, `tests/product_consolidation_manifest.json`, `tests/product_organization_cases.py`, `tests/product_organization_manifest.json`, `tests/product_support_cases.py`, `tests/product_support_manifest.json`, `tests/tooling_boundary_manifest.json`, `tests/unit/test_feature_preservation.py`, `tests/unit/test_product_consolidation.py`, `tests/unit/test_product_organization.py` and `tests/unit/test_product_selector_runtime.py`.
2. **`tests/unit/test_product_test_support.py`**: delete the functions `test_consumers_bind_the_shared_store_and_path`, `test_existing_cases_assertions_and_helpers_remain_unchanged`, `test_seeded_link_fixture_keeps_exact_setup_and_values`, `test_existing_support_helpers_keep_their_bodies`, `test_product_tooling_and_global_guards_are_untouched`, `test_all_304_existing_consumer_cases_keep_their_nodeids_and_sections` and `test_parametrized_path_cases_execute_with_the_shared_store`, and the imports only they used. Keep `test_shared_refusal_checks_code_text_and_exception_type`, `test_shared_path_is_a_function_scoped_explicit_fixture` and `test_shared_store_is_empty_and_closes_once_on_every_exit` (8 tests), with their helper classes, unchanged.
3. **`tests/unit/test_tooling_boundary.py`**: delete `test_moved_modules_are_byte_identical_and_old_sources_are_removed` and `test_prior_test_cases_and_assertions_only_change_import_namespace`. `test_product_and_tooling_gate_lists_are_separate_and_complete` no longer compares with a manifest: it checks that the product list `check.py` reads equals the lines of `scripts/critical_modules.txt` and that each names a file under `src/docket/`, and keeps its other assertions. The other 19 tests stay unchanged.
4. **`tests/tooling_boundary_cases.py`**: no manifest, no `normalized_test` and no `IMPORTS`. `CoverageRunner` builds its fake coverage from the paths in `scripts/critical_modules.txt` (under `src/docket/`) and `scripts/tooling_modules.txt`, with its gap cases unchanged. `ROOT` stays.
5. **`tests/unit/test_product_support_runtime.py`**: define `ROOT` (the repository root) in the file instead of importing it from `tests.product_support_cases`. Nothing else changes.
6. **Nothing else changes**: no file under `src/`, `scripts/` or `docket_tools/`, no other test or helper (`tests/support.py`, `tests/conftest.py`, `tests/sections.toml`, every other test file), and no review.
7. **Given markers**: `tests/unit/test_review_pins.py` carries two strict `xfail` markers with the reason `Phase 6b given test: remove this marker when the freezes are retired`, on `test_the_retired_freeze_files_are_gone` and `test_no_test_or_script_reads_a_retired_freeze`. Delete both (three lines each) once requirements 1 to 5 are done, and nothing else in the file. A strict marker on a passing test fails the run, so `check.py` tells you when.
8. **Progress entry** for `## Phase 6b: Retire the freeze manifests (YYYY-MM-DD)` at the end of `docs/progress.md`.

## Given files

Already committed with this spec; never change them, except the two markers of requirement 7.

| File | What it is |
|---|---|
| `tests/review_pins.json` | `{"reviews": {path: sha256}}` for the 31 reviews `phase-00` to `phase-06a` |
| `tests/unit/test_review_pins.py` | Every pinned review keeps its bytes, the pins name only existing reviews, a changed byte is refused, the retired files are gone, and no test, script or tooling module names a retired freeze |
| `docs/verification/probe-06b.py` | The verifier's probe |

Given test count: **35** (5 functions in `test_review_pins.py`: one parametrized over the 31 pins, and four single tests). Before you start, 33 pass and the two marked tests show as `xfailed`.

## Tests to write

None. This phase removes tests; the given tests cover requirements 1, 4 and 7, `check.py` covers the kept tests and both coverage gates, and the probe covers requirements 2, 3, 5 and 6 by comparing the collected test ids with this spec's commit.

## Scope

| Path | Change |
|---|---|
| the twelve files of requirement 1 | delete |
| `tests/unit/test_product_test_support.py` | edit: requirement 2 |
| `tests/unit/test_tooling_boundary.py` | edit: requirement 3 |
| `tests/tooling_boundary_cases.py` | edit: requirement 4 |
| `tests/unit/test_product_support_runtime.py` | edit: requirement 5 |
| `tests/unit/test_review_pins.py` | delete the two markers only |
| `docs/progress.md` | append your entry |

## Out of scope

- The store and task boundary tests named in Facts: they test behaviour and stay.
- Merging, renaming or moving any test file, the tooling `*_more.py` files, or a `tests/support/` package (2r).
- Any product, script or tooling change, including the refactors the Nov 21 audit recommends (5a to 5c).
- A tool or test that pins new reviews, or a pin on anything but `docs/reviews/`.
- Any change to a given file beyond the two markers, `AGENTS.md`, the design docs or `.claude/`.

## Rules that bite

- **Delete exactly the named tests.** The probe compares every collected test id with this spec's commit: a kept test that goes missing, or a retired one that survives, fails it.
- **Reviews are pinned.** Never edit a file in `docs/reviews/`.
- **Product untouched.** This phase edits only test files; a change under `src/` is a finding even if every test passes.
- If you stop before finishing, still write the progress entry with a `Stopped:` first follow-up (`docs/phase-conventions.md`, "When you stop").
- Commands start with `.venv/bin/python`; no bare `python3`, `pytest` or `ruff`.

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_review_pins.py` (before you start) | `1719 passed` |
| `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1653 passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest tests/unit/test_review_pins.py --no-cov -q` | `35 passed` |
| `.venv/bin/python docs/verification/probe-06b.py` | last line `FAILURES 0` |
| `grep -c "^## Phase 6b: " docs/progress.md` | `1` |
| `.venv/bin/python scripts/check_reports.py --phase 6b` | `Reports OK.` |
| `git diff HEAD --stat -- tests/review_pins.json docs/verification/probe-06b.py src scripts docket_tools docs/reviews AGENTS.md pyproject.toml tests/support.py tests/conftest.py tests/sections.toml` | no output |
| `git diff HEAD --numstat -- tests/unit/test_review_pins.py` | one line: 0 added, 6 deleted, `tests/unit/test_review_pins.py` (the two markers, nothing else) |
| `git status --short` | only the Scope paths |

### Searches

Each prints nothing.

```zsh
git grep --untracked -n -E 'preservation_cases|product_(consolidation|organization|support)_cases|_manifest\.json|assert_preserved|normalized_test' -- tests scripts docket_tools ':!tests/unit/test_review_pins.py'
git grep --untracked -n -E 'import (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)|from (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)' -- src
git grep --untracked -n -E 'ollama|anthropic|openai|langchain' -- src
git grep --untracked -n -E 'pragma: no cover|noqa' -- src tests/tooling_boundary_cases.py tests/unit/test_tooling_boundary.py tests/unit/test_product_test_support.py tests/unit/test_product_support_runtime.py
```
