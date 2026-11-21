# Verification guide: Phase 6b (Retire the freeze manifests)

Spec: `docs/phases/phase-06b-retire-freeze-manifests.md`. Follow `docs/phase-conventions.md` ("For the verifier"). Never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor, never read the Keychain, and never open the real data folder.

## 1. Coder ran

Stop with FAIL ("the coder did not run") if `tests/unit/test_feature_preservation.py` still exists and this is missing:

- `grep -c "^## Phase 6b: " docs/progress.md` prints `1`

Stop with FAIL ("the coder stopped") if that entry's first `Follow-ups` line starts with `Stopped:`, as "A stopped coder" in `docs/phase-conventions.md` says. With no entry, `git status --short` tells "the coder did not run" (no Scope path changed) from "the coder broke off without reporting" (Scope paths changed; name them under `For the architect`).

Stop with FAIL ("the baseline is not committed") if `git ls-files --error-unmatch docs/phases/phase-06b-retire-freeze-manifests.md tests/review_pins.json tests/unit/test_review_pins.py docs/verification/probe-06b.py` fails: the diff gates can only be judged against a committed spec and given files.

## 2. Gates

Run each from the repository root, in this order: `.venv/bin/python scripts/accept.py --phase 6b --guide` runs them and the searches, one line each. Given test count: 35.

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_review_pins.py` | at least 1618 passed, 0 failed (1719 before, less the 101 retired tests) |
| G2 | `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1653 passed, 0 failed, 0 skipped |
| G3 | `.venv/bin/python -m pytest tests/unit/test_review_pins.py --no-cov -q` | `35 passed` |
| G4 | `.venv/bin/python docs/verification/probe-06b.py` | last line `FAILURES 0` |
| G5 | `grep -c "^## Phase 6b: " docs/progress.md` | `1` |
| G6 | `.venv/bin/python scripts/check_reports.py --phase 6b` | `Reports OK.` |
| G7 | `git diff HEAD --stat -- tests/review_pins.json docs/verification/probe-06b.py src scripts docket_tools docs/reviews AGENTS.md pyproject.toml tests/support.py tests/conftest.py tests/sections.toml` | no output |
| G8 | `git diff HEAD --numstat -- tests/unit/test_review_pins.py` | one line: 0 added, 6 deleted, `tests/unit/test_review_pins.py` (the two markers, nothing else) |
| G9 | `git status --short` | only the Scope paths |
| G10 | `.venv/bin/python -m pip list --format=freeze \| wc -l` | `52` (unchanged: this phase adds no package) |

## 3. Spot checks

This phase changes no module under `src/`, so every row uses the second procedure. For a module under `src/`, write the change as an exact old and new text in the module the coder wrote and run `.venv/bin/python scripts/spot_check.py <module> --old '<old>' --new '<new>' --test '<deciding test>' --row S<n>`; it restores the module and prints one line. For any other file:
1. Copy the module outside the repository.
2. Make the change described in the module the coder wrote.
3. Run the deciding test with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest '<test>' --no-cov -q --tb=line`, and confirm it fails with the "Broken" value; rerun with `-vv` only when it doesn't.
4. Restore the module from your copy, delete `src/docket/__pycache__`, and confirm `git diff` is as before.

A different failure from the "Broken" column is a note, not a finding; a pass is a finding.

| # | Module | Change | Deciding test | Correct | Broken |
|---|---|---|---|---|---|
| S1 | `tests/tooling_boundary_manifest.json` (deleted) | restore it: `git show HEAD:tests/tooling_boundary_manifest.json > tests/tooling_boundary_manifest.json` | `tests/unit/test_review_pins.py::test_the_retired_freeze_files_are_gone` | [] | ['tests/tooling_boundary_manifest.json'] |
| S2 | `tests/tooling_boundary_cases.py` | append a function `def normalized_test(path): return path` | `tests/unit/test_review_pins.py::test_no_test_or_script_reads_a_retired_freeze` | [] | ['tests/tooling_boundary_cases.py: normalized_test'] |
| S3 | `docs/reviews/phase-03e-reminder-loop.md` | append one space | `tests/unit/test_review_pins.py::test_every_pinned_review_keeps_its_bytes[docs/reviews/phase-03e-reminder-loop.md]` | None | 'pinned review changed: phase-03e-reminder-loop.md' |
| S4 | `tests/tooling_boundary_cases.py`, `CoverageRunner` | give the tooling paths as `docket_tools/reports.py` and `docket_tools/acceptance.py` only, instead of the lines of `scripts/tooling_modules.txt` | `tests/unit/test_tooling_boundary.py::test_each_coverage_gate_refuses_missing_lines_and_branches_independently[healthy]` | result 0 | result 1 |
| S5 | `tests/unit/test_product_test_support.py` | delete `test_shared_path_is_a_function_scoped_explicit_fixture` | the probe, `only the retired tests go` | `only the retired tests go ok` | `FAIL only the retired tests go: removed tests Phase 6b keeps: [...test_shared_path_is_a_function_scoped_explicit_fixture]` |

## 4. Probe

Run `.venv/bin/python docs/verification/probe-06b.py` from the repository root. It is a given file: do not edit it. Every line must end in `ok`; the last line must be `FAILURES 0`. A stop at the probe's own `assert` lines, before its self-check prints `ok`, is the probe's fault: report it under "For the architect", not as a finding. It touches no network, Keychain or real data folder.

It reads the spec commit with `git archive` (read-only) and copies the working tree into a temporary folder, then: compares the collected test ids, which must differ by exactly the 101 retired tests and nothing else; appends a comment (or, in `core.py` and `store.py`, a private helper) to each of the 36 or so non-test files the old manifests pinned and runs the whole suite in the copy, which must pass; and appends a space to one review, which must fail exactly that review's pin. The given tests cannot see a kept test that was deleted, or a pin that survives in a file the coder did not touch. It runs the suite twice, about 30 seconds in all.

## 5. Searches

Each prints nothing. A match is a finding against the rule it names.

| # | Rule | Command |
|---|---|---|
| Q1 | no test, script or tooling module reads a retired freeze | `git grep --untracked -n -E 'preservation_cases\|product_(consolidation\|organization\|support)_cases\|_manifest\.json\|assert_preserved\|normalized_test' -- tests scripts docket_tools ':!tests/unit/test_review_pins.py'` |
| Q2 | no network code | `git grep --untracked -n -E 'import (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)\|from (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)' -- src` |
| Q3 | no model client | `git grep --untracked -n -E 'ollama\|anthropic\|openai\|langchain' -- src` |
| Q4 | no coverage or lint exclusions in this phase's modules | `git grep --untracked -n -E 'pragma: no cover\|noqa' -- src tests/tooling_boundary_cases.py tests/unit/test_tooling_boundary.py tests/unit/test_product_test_support.py tests/unit/test_product_support_runtime.py` |

(In the table, `\|` is a `|` in the command.)

## 6. Reasonable variations

These are correct even though the spec does not spell them out:

- Reading the gate lists in `tests/tooling_boundary_cases.py` through `check.py`'s `read_critical` or a small parser of its own, as long as comments and blank lines are skipped.
- `ROOT` in `test_product_support_runtime.py` as `Path(__file__).resolve().parents[2]` or taken from another kept helper.
- The file-existence check in the gate-list test written as a loop or with `all()`.
- Private helpers inside the Scope modules, and extra behaviour tests in `*_more.py` files.

## 7. Verdict

Write `docs/reviews/phase-06b-retire-freeze-manifests.md` in the form `docs/phase-conventions.md` gives (`# Review: Phase 6b`), then run `.venv/bin/python scripts/check_reports.py --phase 6b`; it must print `Reports OK.`
