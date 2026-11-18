# Verification guide: Phase 2n (Repository phase tooling)

Spec: `docs/phases/phase-02n-repository-phase-tooling.md`. Follow `docs/phase-conventions.md` ("For the verifier"). Never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor, never read the Keychain, and never open the real data folder.

## 1. Coder ran

Stop with FAIL ("the coder did not run") if any of these is missing:

- `docket_tools/__init__.py`
- `docket_tools/reports.py`
- `docket_tools/acceptance.py`
- `docket_tools/spotcheck.py`
- `tests/unit/test_tooling_boundary_more.py`
- `grep -c "^## Phase 2n: " docs/progress.md` prints `1`

Stop with FAIL ("the coder stopped") if that entry's first `Follow-ups` line starts with `Stopped:`, as "A stopped coder" in `docs/phase-conventions.md` says. With no entry, `git status --short` tells "the coder did not run" (no Scope path changed) from "the coder broke off without reporting" (Scope paths changed; name them under `For the architect`).

Stop with FAIL ("the baseline is not committed") if `git ls-files --error-unmatch docs/phases/phase-02n-repository-phase-tooling.md tests/tooling_boundary_manifest.json tests/tooling_boundary_cases.py tests/unit/test_tooling_boundary.py scripts/tooling_modules.txt docs/verification/probe-02n.py` fails: the diff gates can only be judged against a committed spec and given files.

## 2. Gates

Run each from the repository root, in this order: `.venv/bin/python scripts/accept.py --phase 2n --guide` runs them and the searches, one line each. Given test count: 33.

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_tooling_boundary.py` | at least 1223 passed, 0 failed (the coder's `*_more.py` tests add to the count) |
| G2 | `.venv/bin/python scripts/check.py --first tooling` | last line `All checks passed.`; summary lists `tests (tooling): passed`; at least 1256 passed, 0 failed, 0 skipped |
| G3 | `.venv/bin/python -m pytest tests/unit/test_tooling_boundary.py --no-cov -q` | `33 passed` |
| G4 | `.venv/bin/python -m coverage report --include=docket_tools/reports.py,docket_tools/acceptance.py,docket_tools/spotcheck.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| G5 | `.venv/bin/python docs/verification/probe-02e.py` | final line `FAILURES 0`; all five property checks ok |
| G6 | `.venv/bin/python docs/verification/probe-02n.py` | last line `FAILURES 0` |
| G7 | `grep -c "^## Phase 2n: " docs/progress.md` | `1` |
| G8 | `.venv/bin/python scripts/check_reports.py --phase 2n` | `Reports OK.` |
| G9 | `git diff HEAD --stat -- tests/tooling_boundary_manifest.json tests/tooling_boundary_cases.py tests/unit/test_tooling_boundary.py scripts/tooling_modules.txt docs/verification/probe-02n.py` | no output |
| G10 | `git status --short` | only the Scope paths |
| G11 | `.venv/bin/python -m pip list --format=freeze \| wc -l` | `39` (unchanged; no installation is authorized) |

## 3. Spot checks

Audit the entire namespace and gate migration first. Moved source hashes must match, no old product sources/shims remain, ten unit ASTs and the old probe match the manifest, and quiet-runner edits retain its four cases. Check wrappers and the architect linter bootstrap the resolved repository root before imports; the old probe retains its cwd-based ROOT and adds the exact given insertion. Packaging discovery stays src-only. Both coverage lists, measured packages and missing/line/branch failure paths must be preserved independently.

All mutations run in a clean disposable implementation checkout. These targets are outside src, so use the manual copy/mutate/test/restore procedure below; do not widen spot_check.py’s allowlist. S1–S4 were confirmed against a discarded small checker patch using the given synthetic report inputs. S5 is decided directly by the pinned source hash. No complete relocation was implemented by the architect.

For a module under `src/`, write the change as an exact old and new text in the module the coder wrote and run `.venv/bin/python scripts/spot_check.py <module> --old '<old>' --new '<new>' --test '<deciding test>' --row S<n>`; it restores the module and prints one line. For any other file:
1. Copy the module outside the repository.
2. Make the change described in the module the coder wrote.
3. Run the deciding test with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest '<test>' --no-cov -q --tb=line`, and confirm it fails with the "Broken" value; rerun with `-vv` only when it doesn't.
4. Restore the module from your copy, delete `src/docket/__pycache__`, and confirm `git diff` is as before.

A different failure from the "Broken" column is a note, not a finding; a pass is a finding.

| # | Module | Change | Deciding test | Correct | Broken |
|---|---|---|---|---|---|
| S1 | scripts/check.py, coverage_gaps absent-file branch | Replace appending the not-measured gap with pass, retaining continue | `tests/unit/test_tooling_boundary.py::test_each_coverage_gate_refuses_missing_lines_and_branches_independently[tool-missing]` | exit 1 at tooling coverage | exit 0 |
| S2 | scripts/check.py, coverage gap condition | Replace if lines or branches with if branches | `tests/unit/test_tooling_boundary.py::test_each_coverage_gate_refuses_missing_lines_and_branches_independently[tool-line]` | exit 1 | exit 0 |
| S3 | scripts/check.py, coverage gap condition | Replace if lines or branches with if lines | `tests/unit/test_tooling_boundary.py::test_each_coverage_gate_refuses_missing_lines_and_branches_independently[tool-branch]` | exit 1 | exit 0 |
| S4 | scripts/check.py, product gate dispatch | Substitute True for the product gate result while retaining tooling evaluation | `tests/unit/test_tooling_boundary.py::test_each_coverage_gate_refuses_missing_lines_and_branches_independently[product-line]` | exit 1, tooling not run | exit 0 |
| S5 | docket_tools/spotcheck.py, mutate | Replace return text.replace(old, new, 1) with return text | `tests/unit/test_tooling_boundary.py::test_moved_modules_are_byte_identical_and_old_sources_are_removed[docket_tools/spotcheck.py]` | exact pinned digest | changed digest |

## 4. Probe

Run `.venv/bin/python docs/verification/probe-02n.py` from the repository root. It is a given file: do not edit it. Every line must end in `ok`; the last line must be `FAILURES 0`. A stop at the probe's own `assert` lines, before its self-check prints `ok`, is the probe's fault: report it under "For the architect", not as a finding. It touches no network, Keychain or real data folder.

The new probe verifies its fake coverage oracle, then checks byte-identical relocated modules, wrapper module bindings, all seven independent gate inputs and every migrated consumer AST. Its baseline has four intended failures. The existing Phase 2e probe remains a separate gate for 600 restoration cases, 300 progress cases, all document-row parsers, real synthetic runners and section-only quiet behavior. No probe touches the owner’s data, services, Keychain or network. No wheel was built; the given isolated src-copy smoke test plus unchanged discovery check is the packaging evidence.

## 5. Searches

Each prints nothing. A match is a finding against the rule it names.

| # | Rule | Command |
|---|---|---|
| Q1 | no network code in product or tooling | `git grep --untracked -n -E 'import (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)\|from (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)' -- src docket_tools` |
| Q2 | no utility output outside the product CLI | `git grep --untracked -n -E 'print\(\|logging\|logger\|warnings\.warn' -- src docket_tools ':!src/docket/cli.py'` |
| Q3 | time read only through the existing clock module | `git grep --untracked -n -E 'datetime\.now\|datetime\.utcnow\|date\.today\|time\.time\(\|from docket\.(clock\|ids) import' -- src docket_tools ':!src/docket/clock.py'` |
| Q4 | only core owns product task mutations | `git grep --untracked -n -E '\.(insert_task\|update_task\|append_audit\|insert_link\|insert_request_key)\(' -- src docket_tools ':!src/docket/core.py' ':!src/docket/store.py'` |
| Q5 | no model client in either package | `git grep --untracked -n -E 'ollama\|anthropic\|openai\|langchain' -- src docket_tools` |
| Q6 | no coverage or lint exclusions in this phase's modules | `git grep --untracked -n -E 'pragma: no cover\|noqa' -- docket_tools/reports.py docket_tools/acceptance.py docket_tools/spotcheck.py` |

(In the table, `\|` is a `|` in the command.)

## 6. Reasonable variations

These are correct even though the spec does not spell them out:

- Internal gate helper names and dispatch structure; coverage_gaps keeps its default behavior and the added prefix keyword. Product and tooling outcomes remain separate and ordered.
- Root bootstrapping before imports with narrowly scoped E402 directives, or a layout that passes the same direct-script/isolated checks without a directive. No global path/environment dependency or broad lint exclusion.
- Preserve mechanically moved file contents exactly, including whitespace. There is no formatting or parser-logic variation for the three pinned utilities.
- Earlier unit import-only changes may be formatted normally if their AST remains pinned. The probe bootstrap is exact; test_check_quiet separately permits only the named fake-data/summary edits.
- Private helpers inside the Scope modules, and extra behaviour tests in `*_more.py` files.

## 7. Verdict

Write `docs/reviews/phase-02n-repository-phase-tooling.md` in the form `docs/phase-conventions.md` gives (`# Review: Phase 2n`), then run `.venv/bin/python scripts/check_reports.py --phase 2n`; it must print `Reports OK.`
