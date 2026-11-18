# Phase 2n: Repository phase tooling

## Goal

Move phase-only report, acceptance and spot-check utilities out of the installed product into a repository-only docket_tools package. Preserve their bodies, commands and test behavior, and separate product critical coverage from an independently enforced 100% tooling gate. This addresses audit finding 7’s product/tooling boundary; parser simplification, runner redesign and test consolidation remain later work.

Sections: `tooling`. The `tooling` section runs in the full check.

Follow `docs/phase-conventions.md`. N is 1223, the tests the previous phase left passing.

Start: `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_tooling_boundary.py` must show `1223 passed`. The ignored file describes the new boundary. Existing tests retain their old imports until the coder performs the explicitly scoped migration, so this Start runs before edits.

## Facts

Checked 2026-11-17 against baseline `22fa017`:

- Phase 2m is committed and independently PASS: 1,223 tests, no findings/follow-ups. Approved private task helper names are insert_task/update_task/select_task/select_tasks/select_tasks_in_states/select_existence; there is no policy deviation.
- reports.py, acceptance.py and spotcheck.py import only the standard library. Their callers are four script wrappers, ten unit-test files, the Phase 2e probe and the architect linter. No application component imports them. The given inventory pins all utility bytes and migrated consumer ASTs.
- Existing setuptools discovery is confined to src. Use a root docket_tools package outside that tree; no dependency or installation is needed. This environment has no setuptools/wheel/build import available. Packaging verification therefore combines unchanged src-only discovery with a fresh isolated src-copy smoke test, not an unrun wheel-build claim.
- Installed pytest-cov accepts repeated --cov options. Add docket_tools alongside docket, retain branch coverage and the overall 90% floor. Three existing critical utility modules move to their own gate rather than losing coverage enforcement.
- The change is three mechanical byte-identical renames (about 650 existing lines) plus under 150 estimated new wiring/gate lines. Utility implementation is immutable; this is not a parser rewrite or a 650-line reference implementation.
- Baseline new tests fail on the absent namespace, legacy imports and missing gate. Four unrelated-directory --help guards already pass. A discarded small checker patch passed all seven independent gate cases and four mutations (missing measurement, line gap, branch gap and product-gate bypass); no combined relocation was built.
- The probe validates its own synthetic coverage inputs first. Baseline namespace/binding/gate/import checks fail without crashing. Full baseline check.py passed 1,223 tests.

## Owner's decisions

No new product decision or dependency approval. The architect selects the repository package arrangement below, preserving command names, utility behavior, safety rules and both coverage thresholds.

## Architect's decisions

- Use root `docket_tools/` with an empty __init__.py. Move reports.py, acceptance.py and spotcheck.py byte-for-byte from src/docket; remove the old sources without compatibility shims or aliases. Keep every function/class/constant and exception behavior, now under docket_tools. Do not rewrite historical strings/data naming old modules.
- Scripts accept.py, check_reports.py, progress.py and spot_check.py explicitly insert their resolved repository ROOT into sys.path before importing docket_tools. Keep their existing ROOT semantics, argparse, commands, real runners and output behavior. A targeted noqa: E402 on only those post-bootstrap imports is allowed; no wider exclusion. The architect linter also bootstraps ROOT and changes its read_rows import. Do not refactor its templates or checks.
- Preserve coverage_gaps(report, modules) behavior, adding only keyword-only prefix: str = "src/docket". It resolves coverage file keys relative to that prefix; empty prefix uses repository-relative module paths. Existing callers remain valid.
- In scripts/check.py add TOOLING_FILE = ROOT / "scripts/tooling_modules.txt" and TOOLING_COVERAGE_STEP = "tooling coverage". Keep the product step named critical coverage, then run tooling coverage as a distinct commandless step. Each reads its own list and independently refuses absent measurements, uncovered lines or branches. Stop on the first failure, marking later steps not run; quiet/first/section behavior stays intact.
- Product list keeps all existing product modules and removes only the three relocated utilities. The given tooling list contains their three repository-relative paths. Add --cov=docket_tools alongside --cov=docket in pytest defaults, preserve --cov-branch/90%, include docket_tools in first-party formatting, and place test_tooling_boundary*.py in the tooling section. Do not add scripts/check.py to a new coverage promise or lower an existing one.
- Explicitly authorize import-only changes in the ten earlier unit tests listed in Scope, plus imports and exactly one sys.path.insert(0, str(ROOT)) after ROOT in probe-02e.py. These are scoped earlier consumers, not this phase’s immutable given files. The manifest pins their normalized AST, including that probe bootstrap. test_check_quiet.py separately needs only fake coverage data and expected summaries updated for the extra gate; retain all four test functions and their assertions’ intent.

## Requirements

1. **Repository-only utilities:** create the package and relocate the three utility modules exactly as pinned by the given digest manifest. No old sources, shims, dynamic aliases or tool imports remain in src/docket. Setuptools discovery remains src-only; product dependencies/version/entry point are unchanged. Given: three byte/namespace cases, source-boundary and isolated product smoke tests.
2. **Stable entry points:** migrate all actual consumers named in Scope to docket_tools. Four scripts run directly with isolated Python from an unrelated working directory; their ROOT bootstrap does not depend on cwd or PYTHONPATH. Update the architect linter and old Phase 2e probe, preserving all their checks and commands. Keep the spot-check runner’s current src-only mutation allowlist. Given: four script bindings, four direct --help cases, manifest ASTs; coder adds non-help bootstrap behavior below and the old probe remains an acceptance gate.
3. **Preserved existing tests:** the ten import-only unit files and probe match the given normalized AST; no assertion, case, fixture value, historical string or random-walk behavior changes. Authorize only the described import/bootstrap edits. In test_check_quiet retain its four functions; add synthetic tooling coverage entries and passed/not-run summary expectations for the new step. Do not consolidate, rename or delete tests. Given: eleven consumer digest cases; full existing suite.
4. **Separate coverage inventories:** product critical list equals the manifest’s 18 modules, removing only reports/acceptance/spotcheck. TOOLING_FILE names the three moved paths exactly. Both lists remain measured at 100% lines and branches; an absent file entry is failure, not zero uncovered lines. Prefix defaults preserve existing coverage_gaps callers, including key/gap text semantics. Given: list/constants check and independent gate cases.
5. **Checker integration:** full check.py runs critical coverage then tooling coverage on the same completed pytest JSON report. Both have separate headings/summary lines, with failure text Check failed at: <step>. An earlier product failure prevents tooling from running; a tooling failure cannot be reported as success. --quiet --first tooling and --section tooling retain existing behavior/logging and final All checks passed. on success. Overall 90%, branch coverage and both measured packages remain configured. Given: seven gate cases, configuration/section checks; coder covers remaining checker branches.
6. **Behavior preservation:** utility bytes and old tests preserve report forms/error messages, acceptance row/digest/log semantics and mutation restoration even when the runner raises. Command arguments and generated progress/review formats stay stable; literal historical module names in sample entries are data and stay untouched. No new shell/network operation, model, telemetry, product capability or dependency. Given: manifest checks, existing utility tests and old probe.
7. **Scope and validation:** no product source changes except removal of the three utilities. Retain both independent 100% gates and every existing product critical path. No reinstall/build/dependency step, parser redesign, template split, mutation isolation redesign, type checker, test consolidation or later product feature.

8. **Progress entry** for `## Phase 2n: Repository phase tooling (YYYY-MM-DD)` at the end of `docs/progress.md`.

## Given files

Already committed with this spec; never change them.

| File | What it is |
|---|---|
| `tests/tooling_boundary_manifest.json` | Immutable utility hashes, ten test ASTs, one probe AST and complete product critical inventory |
| `tests/tooling_boundary_cases.py` | Given AST normalization and synthetic independent coverage runner; no test cases |
| `tests/unit/test_tooling_boundary.py` | 33 tests from 9 functions (requirements 1–5) |
| `scripts/tooling_modules.txt` | Immutable repository-relative inventory of the three moved critical utilities |
| `docs/verification/probe-02n.py` | The verifier's probe |

Given test count: **33** (9 functions). Baseline and names-only utilities give 29 intended failures and four passing direct-help guards. Old unit tests keep their 1,223 baseline cases; their authorized imports migrate only during implementation.

## Tests to write

Write tests/unit/test_tooling_boundary_more.py:

- Exercise default/prefixed coverage_gaps, both gate failures and successful dispatch, keeping product gap messages unchanged. Assert the correct gate/summary is used rather than merely executing it.
- Run progress.py and check_reports.py directly with isolated Python from an unrelated cwd against a synthetic temporary progress file/root; assert literal output and no unexpected file changes. Test accept/spot wrappers with their existing fakes; retain their src-only mutation boundary.
- Confirm --section tooling and --first tooling classify all new tests correctly; full run still measures both packages, first/section-only runs keep --no-cov semantics.
- Preserve old test_check_quiet intent with fake coverage entries from both inventories; test an early lint/format failure leaves both coverage steps not run.
- Cover newly added dispatch/bootstrap branches with meaningful assertions. Do not edit this phase’s given files, module bodies or unrelated tests.

## Scope

| Path | Change |
|---|---|
| `docket_tools/__init__.py` | create |
| `docket_tools/reports.py` | create |
| `docket_tools/acceptance.py` | create |
| `docket_tools/spotcheck.py` | create |
| `tests/unit/test_tooling_boundary_more.py` | create |
| `src/docket/reports.py` | edit: delete after byte-identical relocation; no shim |
| `src/docket/acceptance.py` | edit: delete after byte-identical relocation; no shim |
| `src/docket/spotcheck.py` | edit: delete after byte-identical relocation; no shim |
| `scripts/check.py` | edit: separate prefixed product/tooling coverage gates and dispatch only |
| `scripts/critical_modules.txt` | edit: remove only the three relocated utility paths |
| `scripts/accept.py` | edit: repository bootstrap and tooling imports only |
| `scripts/check_reports.py` | edit: repository bootstrap and tooling import only |
| `scripts/progress.py` | edit: repository bootstrap and tooling import only |
| `scripts/spot_check.py` | edit: repository bootstrap and tooling import only; runner allowlist unchanged |
| `pyproject.toml` | edit: add tooling coverage source and first-party name only; packaging/dependencies unchanged |
| `tests/sections.toml` | edit: add unit/test_tooling_boundary*.py to tooling |
| `.claude/skills/phase-architect/phase_tools.py` | edit: ROOT bootstrap and read_rows import only |
| `tests/unit/test_check_quiet.py` | edit: fake tooling coverage inputs and separate gate summary expectations only |
| `docs/verification/probe-02e.py` | edit: three tooling imports and one ROOT sys.path insertion only |
| `tests/unit/test_acceptance.py` | edit: import namespace only; normalized AST pinned |
| `tests/unit/test_acceptance_more.py` | edit: import namespace only; normalized AST pinned |
| `tests/unit/test_reports.py` | edit: import namespace only; normalized AST pinned |
| `tests/unit/test_reports_more.py` | edit: import namespace only; normalized AST pinned |
| `tests/unit/test_reports_phase.py` | edit: import namespace only; normalized AST pinned |
| `tests/unit/test_reports_phase_more.py` | edit: import namespace only; normalized AST pinned |
| `tests/unit/test_reports_put.py` | edit: import namespace only; normalized AST pinned |
| `tests/unit/test_reports_put_more.py` | edit: import namespace only; normalized AST pinned |
| `tests/unit/test_spotcheck.py` | edit: import namespace only; normalized AST pinned |
| `tests/unit/test_spotcheck_more.py` | edit: import namespace only; normalized AST pinned |
| `docs/progress.md` | append your entry |

## Out of scope

- Report-parser simplification, source-template/linter split, new tool APIs, test consolidation or file moves beyond the three utilities.
- Compatibility shims/aliases in product, separate distributable package, build/install workflow, changed dependencies, wheel-building prerequisites or type checking.
- Mutation-runner isolation/allowlist changes, new shell/network operations, application/runtime behavior, schema, settings, IDs or service integrations.
- Changes to earlier utility test bodies, fixture strings, cases or assertions; only the explicit import/bootstrap and quiet-runner edits are authorized.
- Any change to a given file, `AGENTS.md` or the design docs.

## Rules that bite

- **Coverage:** separation is not exemption. Never drop an inventory entry, ignore a missing measurement, skip branches or merge the two success/failure results.
- **Packaging/layering:** installed product discovers src only and imports no docket_tools; repository tooling uses explicit local roots and no product runtime dependency.
- **Preservation:** hash-pinned modules and AST-pinned consumers remain unchanged except authorized relocation/import/bootstrap. No real data, Keychain, accounts, services or new dependencies.
- **Safety:** keep existing runner restoration and src allowlist; actual mutations run only in disposable implementation checkouts. No live-checkout mutation or external communication.
- **Time through the module**: `clock.now()`, never `datetime.now()`, and never `from docket.clock import now`.
- If you stop before finishing, still write the progress entry with a `Stopped:` first follow-up (`docs/phase-conventions.md`, "When you stop").
- Commands start with `.venv/bin/python`; no bare `python3`, `pytest` or `ruff`.

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_tooling_boundary.py` (before you start) | `1223 passed` |
| `.venv/bin/python scripts/check.py --first tooling` | last line `All checks passed.`; summary lists `tests (tooling): passed`; at least 1256 passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest tests/unit/test_tooling_boundary.py --no-cov -q` | `33 passed` |
| `.venv/bin/python -m coverage report --include=docket_tools/reports.py,docket_tools/acceptance.py,docket_tools/spotcheck.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| `.venv/bin/python docs/verification/probe-02e.py` | final line `FAILURES 0`; all five property checks ok |
| `.venv/bin/python docs/verification/probe-02n.py` | last line `FAILURES 0` |
| `grep -c "^## Phase 2n: " docs/progress.md` | `1` |
| `.venv/bin/python scripts/check_reports.py --phase 2n` | `Reports OK.` |
| `git diff HEAD --stat -- tests/tooling_boundary_manifest.json tests/tooling_boundary_cases.py tests/unit/test_tooling_boundary.py scripts/tooling_modules.txt docs/verification/probe-02n.py` | no output |
| `git status --short` | only the Scope paths |

### Searches

Each prints nothing.

```zsh
git grep --untracked -n -E 'import (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)|from (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)' -- src docket_tools
git grep --untracked -n -E 'print\(|logging|logger|warnings\.warn' -- src docket_tools ':!src/docket/cli.py'
git grep --untracked -n -E 'datetime\.now|datetime\.utcnow|date\.today|time\.time\(|from docket\.(clock|ids) import' -- src docket_tools ':!src/docket/clock.py'
git grep --untracked -n -E '\.(insert_task|update_task|append_audit|insert_link|insert_request_key)\(' -- src docket_tools ':!src/docket/core.py' ':!src/docket/store.py'
git grep --untracked -n -E 'ollama|anthropic|openai|langchain' -- src docket_tools
git grep --untracked -n -E 'pragma: no cover|noqa' -- docket_tools/reports.py docket_tools/acceptance.py docket_tools/spotcheck.py
```
