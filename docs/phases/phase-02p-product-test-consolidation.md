# Phase 2p: Product test consolidation

## Goal

Fold the four product continuation files named by audit finding 7 into their existing behaviour modules: port settings, server startup, CLI serve and CLI tasks. Preserve every test body, parameter, assertion, fixture and synthetic value, with an explicit case/selector migration. No product code changes. Remaining product continuation organization is Phase 2q and tooling consolidation is Phase 2r.

Sections: `core`. The `tooling` section runs in the full check.

Follow `docs/phase-conventions.md`. N is 1295, the tests the previous phase left passing.

Start: `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_product_consolidation.py` must show `1295 passed`. The ignored files import names you create.

## Facts

Checked 2026-11-18 against committed and independently verified baseline c9fdbfd:

- Phase 2o passed with 1,295 tests, no findings or deviations. The clean baseline full checker passes both 100% coverage gates and the overall 90% floor.
- The eight scoped files collect 78 cases. Eight cases from six functions move: port 2, server 1, CLI serve 2 and CLI tasks 3. Canonical-plus-continuation totals are respectively 13, 7, 9 and 49.
- No function names collide in these pairs. Server NOW/BODY assignments are AST-identical and may be deduplicated. Import aliases must retain their exact meaning. CLI tasks has the sole inherited autouse fixture, home; it sets the same explicit America/New_York zone already set by every moved newer-schema case. Preserve both the fixture and the moved test's explicit setting. No fixture dependencies or parametrized names are renamed.
- The manifest pins the 78 old-to-new IDs, all non-import AST nodes, normalized import atoms, four historical pytest selection sets, exact replacements for six historical documents and 142 frozen paths. Product/SQL helpers, tooling, scripts, support fixtures, section/coverage/dependency configuration, other tests and review reports stay byte-identical. Phase 2n/2o manifests require no migration because none of their pinned consumers move.
- Historical commands use whole canonical files or ignore them. A merge changes those selections unless translated: positive selections deselect the moved continuation functions; an old canonical-file ignore becomes deselection of only its original functions. This preserves the original 66-case Phase 1e and 24-case Phase 2d given commands. Historical baseline counts remain historical.
- The 24 given cases come from seven functions. Baseline and names-only runs fail 22 intended layout/collection/runtime/document/selector checks and pass two inventory guards. The oracle independently checks literal totals 78, 8 and 13/7/9/49. Discarded bounded slices passed three settings inventory/collection/runtime checks and all 13 settings consumers, one real CLI newer-schema execution check, eight document/positive-selector checks and the frozen guard. All five deliberate mutations failed their deciding givens. No full reference consolidation is built.

## Owner's decisions

No new owner decision. This implements the already planned audit test-organization work without changing product policy, APIs, dependencies, data or privacy rules.

## Architect's decisions

Use the existing canonical filenames, unchanged function/parameter names and unchanged pytest sections. Delete each listed continuation after moving its contents. No forwarding module, imported-test re-export, compatibility alias, pytest hook or global fixture registration. The manifest is the complete literal migration contract, not a generator to modify.

| Canonical module | Retired continuation | Total after merge | Moved cases |
|---|---|---|---|
| tests/unit/test_settings_port.py | tests/unit/test_settings_port_more.py | 13 | 2 |
| tests/integration/test_server.py | tests/integration/test_server_more.py | 7 | 1 |
| tests/e2e/test_cli_serve.py | tests/e2e/test_cli_serve_more.py | 9 | 2 |
| tests/e2e/test_cli_tasks.py | tests/e2e/test_cli_tasks_more.py | 49 | 3 |

For a retired node ID, replace only its file component with the canonical path; parameter suffixes remain exact. Canonical IDs remain exact. The manifest records every case individually, not only these totals. Preserve all non-import AST nodes, deduplicating only identical top-level assignments already present in both inputs; imports may be regrouped/deduplicated but their normalized atoms must equal the union. No new public application names.

Apply the documents section of tests/product_consolidation_manifest.json literally: each entry provides replacements, append text and before/after SHA-256. Only the three listed earlier specs and three earlier guides change; their historical counts and original review/progress reports stay historical. For earlier guides, this authorizes a mechanical text replacement from the manifest without reading their spot checks. Do not open this phase's verification guide. This bounded authorization overrides the generic prohibition only for these historical replacement operations. No changes to acceptance/parser tools or manifests from earlier phases.

These are mechanical moves, not a rewrite. Source test bodies remain exact; new executable logic is limited to the small coder-owned historical-selector runtime checks. No new dependency.

## Requirements

1. **Four canonical modules:** move each listed continuation into its canonical module and delete the retired file. Keep function names, decorators, parameter values/IDs, assertions, helpers, fixture definitions and synthetic constants unchanged. Import union and non-import AST inventory must match the manifest exactly. File order may change; executable nodes may not. Given: four structural cases.
2. **Case and section preservation:** collect exactly 78 mapped family cases, with no missing, duplicate, skipped or xfailed case. All remain in core using unchanged tests/sections.toml. Only eight node IDs change file component; the other 70 remain exact. Given: four collection/section cases and the literal mapping oracle.
3. **Runtime fixture compatibility:** execute all eight moved cases in their canonical modules. Preserve function-scoped isolation, fake Keychain, temporary paths, explicit settings and fixed clock reads. In particular, the three newer-schema cases run under the canonical home autouse fixture without altering their own setup. Collection alone is insufficient. Given: four actual pytest execution cases; full checker executes all 78.
4. **Historical selectors:** apply only the manifest's six document migrations, including the earlier committed-file guard and given-file row for the moved newer-schema test. Historical commands must retain their original baseline selection sets; the four distinct pytest commands pin their projections onto all eight scoped files. The unchanged tests and registries outside these families complete the selection invariant. Do not replace a historical exact-count expectation with a looser minimum to hide drift. Given: six document fingerprints and four actual command-collection checks. Coder writes the two command-execution checks below.
5. **Frozen boundaries:** retain all 142 frozen byte fingerprints: every existing non-scoped test, source module, repository tool/script, old manifest, global guard, dependency/section/coverage config and review report. Keep both independent 100% gates and overall 90%. No real accounts/services/data, dependency installs or application behaviour changes. Given: frozen inventory guard and full acceptance.
6. **Bounded handoff:** the four selected families are the complete current implementation scope. Later product continuation modules and all tooling continuation modules remain untouched. Use the explicit coder-owned runtime filename below rather than adding another generic continuation. No global compatibility infrastructure or broad helper extraction.

7. **Progress entry** for `## Phase 2p: Product test consolidation (YYYY-MM-DD)` at the end of `docs/progress.md`.

## Given files

Already committed with this spec; never change them.

| File | What it is |
|---|---|
| `tests/product_consolidation_manifest.json` | Immutable 78-case mapping, exact bodies/import atoms, six document replacement plans, four selector sets and 142 frozen paths |
| `tests/product_consolidation_cases.py` | Given inventory, collection and runtime checks; no collected tests |
| `tests/unit/test_product_consolidation.py` | 24 tests from 7 functions (requirements 1–5) |
| `docs/verification/probe-02p.py` | The verifier's probe |

Given test count: **24** (7 functions). Baseline and names-only: 22 intended failures, 2 preservation/oracle guards.

## Tests to write

The given tests cover every requirement's main cases. This phase overrides the generic continuation-file convention: add only tests/unit/test_product_selector_runtime.py, with two offline command-level checks. Execute the migrated positive given selectors from the manifest (selections 1 and 3), using the project interpreter, controlled repository PYTHONPATH and captured output. Assert successful execution and literal counts 66 passed for Phase 1e and 24 passed for Phase 2d, with zero errors/skips. Use tests/product_consolidation_cases.py run_pytest or equivalent subprocess setup; never execute arbitrary document text through a shell. These checks establish execution as well as collection. The Phase 2d case includes its existing temporary loopback server and fake Keychain; no external connection. Existing product tests supply source coverage; no new product coverage promise or source patch is required.

## Scope

| Path | Change |
|---|---|
| `tests/unit/test_product_selector_runtime.py` | create |
| `tests/unit/test_settings_port.py` | edit: merge its listed continuation with exact body/import preservation |
| `tests/unit/test_settings_port_more.py` | delete after the exact move; no shim |
| `tests/integration/test_server.py` | edit: merge its listed continuation with exact body/import preservation |
| `tests/integration/test_server_more.py` | delete after the exact move; no shim |
| `tests/e2e/test_cli_serve.py` | edit: merge its listed continuation with exact body/import preservation |
| `tests/e2e/test_cli_serve_more.py` | delete after the exact move; no shim |
| `tests/e2e/test_cli_tasks.py` | edit: merge its listed continuation with exact body/import preservation |
| `tests/e2e/test_cli_tasks_more.py` | delete after the exact move; no shim |
| `docs/phases/phase-01e-adding-and-listing.md` | edit: only its literal manifest replacements and append text |
| `docs/verification/phase-01e-adding-and-listing.md` | edit: only its literal manifest replacements and append text |
| `docs/phases/phase-02a-keyed-intake.md` | edit: only its literal manifest replacements and append text |
| `docs/verification/phase-02a-keyed-intake.md` | edit: only its literal manifest replacements and append text |
| `docs/phases/phase-02d-serve.md` | edit: only its literal manifest replacements and append text |
| `docs/verification/phase-02d-serve.md` | edit: only its literal manifest replacements and append text |
| `docs/progress.md` | append your entry |

## Out of scope

- Remaining product continuation families (2q), tooling consolidation (2r), broad renaming or repartitioning, shared-support redesign, test rewrites, compatibility shims, pytest hooks, dependency/type-check work, product/API/schema changes and new features.
- Any change to a given file, `AGENTS.md` or the design docs.

## Rules that bite

- Keep synthetic inputs, fake Keychain and network guards. Do not read real data or use live services. Preserve every approval/refusal assertion and fixed clock/ID setup. Current given files are immutable; only the explicitly listed earlier given test modules and historical documents may change in the bounded manner above.
- **Time through the module**: `clock.now()`, never `datetime.now()`, and never `from docket.clock import now`.
- If you stop before finishing, still write the progress entry with a `Stopped:` first follow-up (`docs/phase-conventions.md`, "When you stop").
- Commands start with `.venv/bin/python`; no bare `python3`, `pytest` or `ruff`.

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_product_consolidation.py` (before you start) | `1295 passed` |
| `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1319 passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest tests/unit/test_product_consolidation.py --no-cov -q` | `24 passed` |
| `.venv/bin/python -m coverage report --include=src/docket/config.py,src/docket/server.py,src/docket/core.py,src/docket/store.py,docket_tools/reports.py,docket_tools/acceptance.py,docket_tools/spotcheck.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| `.venv/bin/python docs/verification/probe-02p.py` | last line `FAILURES 0` |
| `grep -c "^## Phase 2p: " docs/progress.md` | `1` |
| `.venv/bin/python scripts/check_reports.py --phase 2p` | `Reports OK.` |
| `git diff HEAD --stat -- tests/product_consolidation_manifest.json tests/product_consolidation_cases.py tests/unit/test_product_consolidation.py docs/verification/probe-02p.py` | no output |
| `git status --short` | only the Scope paths |

### Searches

Each prints nothing.

```zsh
git grep --untracked -n -E 'import (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)|from (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)' -- src docket_tools tests/product_consolidation_cases.py
git grep --untracked -n -E 'print\(|logging|logger|warnings\.warn' -- src docket_tools tests/product_consolidation_cases.py ':!src/docket/cli.py'
git grep --untracked -n -E 'datetime\.now|datetime\.utcnow|date\.today|time\.time\(|from docket\.(clock|ids) import' -- src docket_tools tests/product_consolidation_cases.py ':!src/docket/clock.py'
git grep --untracked -n -E '\.(insert_task|update_task|append_audit|insert_link|insert_request_key)\(' -- src docket_tools tests/product_consolidation_cases.py ':!src/docket/core.py' ':!src/docket/store.py'
git grep --untracked -n -E 'ollama|anthropic|openai|langchain' -- src docket_tools tests/product_consolidation_cases.py
git grep --untracked -n -E 'pragma: no cover|noqa' -- tests/product_consolidation_cases.py tests/unit/test_product_selector_runtime.py
```
