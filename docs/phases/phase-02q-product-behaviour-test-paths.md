# Phase 2q: Product behaviour test paths

## Goal

Finish the later product continuation-file cleanup from audit finding 7. Give five modules stable behaviour names through byte-identical moves, preserve all 27 cases and migrate their historical path references and the Phase 2p frozen inventory. Tooling organization remains Phase 2r; dependency-gated static checking remains Phase 2s. No product behaviour, fixture design or test logic changes.

Sections: `core`. The `tooling` section runs in the full check.

Follow `docs/phase-conventions.md`. N is 1321, the tests the previous phase left passing.

Start: `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_product_organization.py` must show `1321 passed`. The ignored files import names you create.

## Facts

Checked 2026-11-18 against committed baseline c9897bd:

- Phase 2p is independently PASS at 1,321 tests, with no findings, deviations or follow-ups. The full baseline checker passes product and tooling 100% coverage and overall 90%.
- The five continuation modules collect 27 cases: respectively 7 creation, 9 domain-adapter, 4 task-SQL, 5 audit/link/key and 2 support-runtime cases. They are already separate behaviour groups; merging them into earlier large given modules would add fixture/selector work without improving their subject boundaries. Rename them within their existing directories and retain every byte.
- These modules contain no self-filename lookup or imports of their old module names. A repository search found references in ten historical specs/guides and five frozen keys of tests/product_consolidation_manifest.json. No probe imports, global pytest hooks or section registry edits are needed. Phase 2n/2o inventories do not pin these five paths.
- The move inventory pins every old/new node ID, source byte hashes, ten literal document migrations, the exact resulting Phase 2p manifest hash and 145 unchanged paths. The earlier manifest migration changes only five frozen keys; every value and every other field remains unchanged. Its given helper and tests remain byte-identical and continue to run.
- Baseline and names-only given runs collect 28 cases from seven functions: 26 intended missing-move/reference/manifest failures and two frozen/oracle guards. The probe oracle checks literal 27-case bijection and per-file counts before checking the candidate. Discarded one-file-at-a-time moves passed all 15 given move/collection/runtime cases and executed all 27 consumers; each move was restored before the next. Ten literal document checks, the exact five-key manifest check and the frozen guard passed separately. All six deliberate regressions failed their deciding tests. No full reference phase is built.

## Owner's decisions

No new owner decision. Naming and bounded file organization are architect choices within the approved audit remediation; API, storage, policy, dependency and privacy contracts are unchanged.

## Architect's decisions

Use the exact mapping below. Keep module contents byte-identical, not only AST-equivalent. The new names are independent behaviour suites, with no compatibility shim, imported-test re-export or new global registration. Existing main given modules are unchanged.

| Retired file | Behaviour file | Cases |
|---|---|---|
| tests/integration/test_shared_creation_more.py | tests/integration/test_creation_transactions_and_retries.py | 7 |
| tests/integration/test_shared_rules_more.py | tests/integration/test_domain_adapter_contracts.py | 9 |
| tests/integration/test_task_boundary_more.py | tests/integration/test_task_sql_contracts.py | 4 |
| tests/integration/test_store_boundaries_more.py | tests/integration/test_audit_link_key_contracts.py | 5 |
| tests/unit/test_product_test_support_more.py | tests/unit/test_product_support_runtime.py | 2 |

Only the file component of each mapped node ID changes; signatures, function names, parameter values/IDs, fixture dependencies and directory ancestry remain exact. All 27 cases stay in core through the existing registry. No old-path forwarding file, symlink or duplicate collection.

The documents entries of tests/product_organization_manifest.json are literal replacements plus append text. Apply these to the ten listed earlier specs/guides, retaining historical counts, test decisions and original reviews/progress. This phase authorizes mechanical replacement in these earlier guides from the manifest without reading their spot checks; do not open this phase's guide. That bounded exception is the only change to the usual guide boundary.

Migrate tests/product_consolidation_manifest.json by parsing its JSON and replacing precisely the five frozen dictionary keys old-path to new-path, preserving order and original hash values. Serialize with json.dumps(data, indent=2) plus a final newline. Preserve all other keys, case mappings, import/body fingerprints, document hashes and selector rows. The new given manifest pins the complete expected result; never refresh old fingerprints from modified files. No other earlier given file may change.

The architect's reusable move_inventory.py records facts and literal migration plans before implementation; it never moves files or applies patches. It is planning infrastructure, not a coder assignment or new product API.

## Requirements

1. **Five byte-identical moves:** create the exact behaviour paths above from their original contents and delete the retired files. Preserve imports, helpers, test bodies, decorators, parameters, synthetic data and embedded pytest scripts byte for byte. No shim, symlink, alias or global fixture/plugin changes. Given: five byte/presence cases.
2. **Case and section contracts:** collect exactly the 27 mapped cases, with unchanged suffixes and no duplicate, lost, renamed, skipped or xfailed case. Stay in the same directories and core section through the unchanged registry. Given: five collection/section cases and the literal bijection oracle.
3. **Execute real consumers:** all 27 cases pass in their new modules, including the product-support tests that launch synthetic pytest consumers. Preserve fake Keychain, temporary databases, clock queues, inherited fixtures and cleanup. Collection/identity alone is insufficient. Given: five command-level runtime cases; full checker executes the moved suites as well.
4. **Historical path migration:** apply exactly the ten document plans, including the earlier guide presence checks and spec test/Scope paths. Old review/progress entries and historical counts are immutable. No historical pytest selection command names these five coder-owned modules, so no positive/negative selector expansion is needed; the per-case mapping handles direct saved selectors. Given: ten complete document fingerprints.
5. **Preserve the earlier manifest:** make precisely the five frozen-key renames in the Phase 2p manifest as described above. No removed guard, regenerated hash, new exception, helper rewrite or change to its 78-case family mapping and historical selectors. Given: full expected manifest fingerprint; existing Phase 2p givens/probe remain mandatory through the full checker and acceptance.
6. **Frozen boundaries:** retain all 145 frozen byte fingerprints, including all other existing tests, source/tooling/scripts, shared support, earlier manifests, review reports, dependencies and section/coverage configuration. Both independent 100% gates and overall 90% remain enforced. No dependency install, real account/data/Keychain access or new network operation. Given: frozen inventory and full checker.

7. **Progress entry** for `## Phase 2q: Product behaviour test paths (YYYY-MM-DD)` at the end of `docs/progress.md`.

## Given files

Already committed with this spec; never change them.

| File | What it is |
|---|---|
| `tests/product_organization_manifest.json` | Immutable five-file hashes, 27 old/new node IDs, ten document plans, expected older manifest hash and 145 frozen paths |
| `tests/product_organization_cases.py` | Given inventory and execution checks; reuses the existing collection runner |
| `tests/unit/test_product_organization.py` | 28 tests from 7 functions (requirements 1–6) |
| `docs/verification/probe-02q.py` | The verifier's probe |

Given test count: **28** (7 functions). Baseline/names-only: 26 intended failures and 2 frozen/oracle guards.

## Tests to write

No additional test file is required for this byte-identical relocation. The coder implements the five moves and eleven literal reference/inventory migrations; existing behaviour tests and the new given runtime cases provide executable coverage. Do not add another generic continuation or rewrite a pinned test to pass. A failure that requires changing a moved byte, fixture or immutable given file is a stop to report, not permission to broaden the phase.

## Scope

| Path | Change |
|---|---|
| `tests/integration/test_creation_transactions_and_retries.py` | create |
| `tests/integration/test_domain_adapter_contracts.py` | create |
| `tests/integration/test_task_sql_contracts.py` | create |
| `tests/integration/test_audit_link_key_contracts.py` | create |
| `tests/unit/test_product_support_runtime.py` | create |
| `tests/integration/test_shared_creation_more.py` | delete after byte-identical move |
| `tests/integration/test_shared_rules_more.py` | delete after byte-identical move |
| `tests/integration/test_task_boundary_more.py` | delete after byte-identical move |
| `tests/integration/test_store_boundaries_more.py` | delete after byte-identical move |
| `tests/unit/test_product_test_support_more.py` | delete after byte-identical move |
| `docs/phases/phase-02j-shared-creation-and-serialization.md` | edit: only its literal manifest replacements and append text |
| `docs/verification/phase-02j-shared-creation-and-serialization.md` | edit: only its literal manifest replacements and append text |
| `docs/phases/phase-02k-shared-domain-rules-and-parsing.md` | edit: only its literal manifest replacements and append text |
| `docs/verification/phase-02k-shared-domain-rules-and-parsing.md` | edit: only its literal manifest replacements and append text |
| `docs/phases/phase-02l-audit-link-and-key-boundaries.md` | edit: only its literal manifest replacements and append text |
| `docs/verification/phase-02l-audit-link-and-key-boundaries.md` | edit: only its literal manifest replacements and append text |
| `docs/phases/phase-02m-task-table-boundary.md` | edit: only its literal manifest replacements and append text |
| `docs/verification/phase-02m-task-table-boundary.md` | edit: only its literal manifest replacements and append text |
| `docs/phases/phase-02o-shared-product-test-support.md` | edit: only its literal manifest replacements and append text |
| `docs/verification/phase-02o-shared-product-test-support.md` | edit: only its literal manifest replacements and append text |
| `tests/product_consolidation_manifest.json` | edit: rename only the five frozen keys, preserving every hash/value |
| `docs/progress.md` | append your entry |

## Out of scope

- Tooling consolidation (2r), type checking (2s), merges or repartitioning within these modules, fixture/helper redesign, broader renaming, compatibility aliases, product/API/schema changes, dependency installs and any additional feature.
- Any change to a given file, `AGENTS.md` or the design docs.

## Rules that bite

- Synthetic data and fake accounts/Keychain only. Keep all existing no-network and isolation guards, approval/refusal assertions and fixed clock/ID setups. Current given files are immutable; only the explicitly listed Phase 2p manifest and historical documents receive the exact authorized migrations.
- **Time through the module**: `clock.now()`, never `datetime.now()`, and never `from docket.clock import now`.
- If you stop before finishing, still write the progress entry with a `Stopped:` first follow-up (`docs/phase-conventions.md`, "When you stop").
- Commands start with `.venv/bin/python`; no bare `python3`, `pytest` or `ruff`.

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_product_organization.py` (before you start) | `1321 passed` |
| `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1349 passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest tests/unit/test_product_organization.py --no-cov -q` | `28 passed` |
| `.venv/bin/python -m coverage report --include=src/docket/core.py,src/docket/store.py,src/docket/domain.py,src/docket/parsing.py,docket_tools/reports.py,docket_tools/acceptance.py,docket_tools/spotcheck.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| `.venv/bin/python docs/verification/probe-02p.py` | last line `FAILURES 0` |
| `.venv/bin/python docs/verification/probe-02q.py` | last line `FAILURES 0` |
| `grep -c "^## Phase 2q: " docs/progress.md` | `1` |
| `.venv/bin/python scripts/check_reports.py --phase 2q` | `Reports OK.` |
| `git diff HEAD --stat -- tests/product_organization_manifest.json tests/product_organization_cases.py tests/unit/test_product_organization.py docs/verification/probe-02q.py` | no output |
| `git status --short` | only the Scope paths |

### Searches

Each prints nothing.

```zsh
git grep --untracked -n -E 'import (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)|from (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)' -- src docket_tools tests/product_organization_cases.py
git grep --untracked -n -E 'print\(|logging|logger|warnings\.warn' -- src docket_tools tests/product_organization_cases.py ':!src/docket/cli.py'
git grep --untracked -n -E 'datetime\.now|datetime\.utcnow|date\.today|time\.time\(|from docket\.(clock|ids) import' -- src docket_tools tests/product_organization_cases.py ':!src/docket/clock.py'
git grep --untracked -n -E '\.(insert_task|update_task|append_audit|insert_link|insert_request_key)\(' -- src docket_tools tests/product_organization_cases.py ':!src/docket/core.py' ':!src/docket/store.py'
git grep --untracked -n -E 'ollama|anthropic|openai|langchain' -- src docket_tools tests/product_organization_cases.py
git grep --untracked -n -E 'pragma: no cover|noqa' -- tests/product_organization_cases.py
```
