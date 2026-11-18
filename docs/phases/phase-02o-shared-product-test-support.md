# Phase 2o: Shared product test support

## Goal

Centralize repeated product-test database fixtures and the strict CoreError refusal helper in tests/support.py without moving files or changing any existing case, assertion, seed value or command reference. This is the first bounded part of audit finding 7’s test-organization work. Product and tooling file consolidation remain separate later phases because historical selectors and manifests require explicit migrations.

Sections: `core`. The `tooling` section runs in the full check.

Follow `docs/phase-conventions.md`. N is 1261, the tests the previous phase left passing.

Start: `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_product_test_support.py` must show `1261 passed`. The ignored file specifies this phase; it imports the support module but checks the new names inside tests. Existing consumers remain unchanged until implementation, so this Start retains their original cases.

## Corrections (2026-11-18)

This correction takes precedence over the original path-dependency design and its collection-only validation. It responds to the committed coder stop at f0c9972; keep that implementation and apply these bounded changes.

- **Cause:** test_core_references parametrizes path with plain/keyed/link. Pytest resolves those labels into the old shared store(path) dependency, causing 27 setup errors. The coder followed the specified contract. Do not rename the pinned parameters, case IDs or assertions.
- **Fix:** store depends directly on builtin tmp_path and opens tmp_path / "docket.sqlite3". The separate path fixture remains available to consumers, but is not a dependency of store. No application code or global fixture registration changes.
- **Fixture export:** declare __all__ = ["base_store"] in the seeded consumer instead of the no-op lambda decorator; keep its sole original @pytest.fixture decorator and exact seed body. The given normalizer exempts only that exact export declaration in that file. Use the same conventional export in the coder-owned synthetic consumer.
- **Given correction:** lifetime checks call the wrapped fixture with a directory and pin its tmp_path signature. The new regression actually executes all 28 existing reference cases, including the 27 path-parameter cases. The probe now executes them too; successful collection/identity checks alone cannot establish fixture compatibility. The given manifest itself stays byte-identical.
- **Live acceptance:** after this corrected handoff is committed, rerun every Acceptance row and search, including a fresh check.py --first core before the coverage report. A1 is a minimum of 1,261 with zero failures/errors on resume because coder-owned cases already exist; the original exact count was the pre-implementation baseline. Givens are now exactly 32; full suite minimum is 1,293. Keep one progress entry and replace its Stopped follow-up only after the complete acceptance passes. No verifier PASS is implied by these corrections.
- **Validation:** in a disposable copy of the existing implementation, the two-line dependency fix and explicit exports passed all 304 migrated consumer cases, 32 corrected givens and two coder checks (338 total), plus the corrected probe and Ruff. The main checkout’s coder-owned implementation is preserved for its rerun; no full reference phase was built.

## Facts

Checked 2026-11-18 against baseline `b858f96`:

- Phase 2n is committed and independently PASS: 1,261 tests, no findings/follow-ups. Its only approved variation is parenthesized imports whose AST matches the manifest. Product and tooling coverage remain separate 100% gates; no dependency changes.
- Eight integration modules own seven equivalent empty-store fixtures and one seeded link-store fixture. test_store.py and test_store_links.py also repeat the same path fixture. Core and keyed-core refusal helpers overlap; the original core version checks both CoreError.code and str(error), whereas the keyed version checks code only.
- tests/support.py already owns run, fixed_times, fixed_ids and load_script. Their ASTs and existing runner configuration are pinned unchanged. No shared pytest plugin or conftest change is needed: explicit fixture imports register locally in consumer modules.
- Installed pytest fixture discovery uses the imported attribute name when the fixture decorator has no explicit name. A synthetic alias spike passed: a fixture imported as base_store supplies a seeded local store wrapper and shares the same path fixture. A self-alias import also preserves intentional fixture re-export for Ruff.
- The given manifest records all 304 existing node IDs in the eight modules, every non-migrating AST body, the exact seeded setup and 38 untouched source/config/global-guard paths. Files and node IDs do not move in this phase, so prior selectors remain valid; Phase 2n tooling AST pins are unaffected.
- A discarded shared-path/store-only patch plus one intake consumer passed 59 targeted cases. Five refusal cases passed using the already-verified strict core helper as a stand-in. No complete migration or new refusal implementation was built. Six mutations exposed lost closure, weakened refusal text/type checks, altered test assertions, changed seeds and lost case IDs.
- Baseline and names-only given runs collect 31 cases from nine functions: 16 intended missing-helper/binding failures and 15 preservation guards. The probe oracle passes; baseline fails bindings/refusal/lifetime and passes the 304-case preservation check. Full baseline checker passed 1,261 tests.

## Owner's decisions

No new owner decision. Preserve all synthetic data, fake-service/privacy guards, test selectors, task behavior and coverage policy. Splitting helper reuse from product/tooling file consolidation is an architect scope decision, not a change to product policy.

## Architect's decisions

Add three contracts to tests.support, with public type hints:

- `path(tmp_path: Path) -> Path`: a default function-scoped pytest.fixture, no explicit decorator name, no parameters/autouse. Return tmp_path / "docket.sqlite3" with no settings/home/clock access or eager file creation.
- `store(tmp_path: Path) -> Iterator[Store]`: the same explicit default fixture contract; yield a fresh empty Store(tmp_path / "docket.sqlite3") from its context manager and close once on normal and exceptional exit. No task seed, clock/ID read, configuration lookup or extra connection.
- `refused(code: str, call: Callable[[], object]) -> None`: call exactly once inside pytest.raises(CoreError), then assert both raised.value.code and str(raised.value) equal code. A wrong exception type propagates, missing exception fails, and no value/text check is weakened.

Consumers explicitly import path as path and store as store; fixture decorators have no explicit name so pytest uses the exported aliases. No global plugin, pytest_plugins registration or conftest hook. The seven empty consumers delete their local store/path definitions. The seeded test_store_links.py instead imports the same store fixture as base_store and keeps a local function-scoped store(base_store: Store) adapter: original transaction/seed loop and yield remain, using base_store instead of opened, without owning/closing a second context. The seeded module declares __all__ = ["base_store"] for the imported fixture re-export; retain only its original @pytest.fixture decorator, with no no-op decorator.

Core and keyed-core import the same refused helper and delete their copies. Their test call sites do not change. All existing support functions, consumer bodies/cases and seeded values remain pinned; import cleanup/type imports and the fixture/helper removal/adapter are the only earlier-file changes. No new product public API.

The former all-test cleanup is staged as 2o shared support, 2p product-file consolidation and 2q tooling-file consolidation; unshipped type checking shifts from 2p to 2r. Those later specs must settle selector/manifests migration before moving files. Do not begin either consolidation here.

## Requirements

1. **Shared temporary path/store:** implement the fixture contracts above in tests/support.py, preserving the existing four helpers. The path is fresh per test under tmp_path; the yielded Store is empty, owns the sole fixture connection and closes exactly once on body success/error. No autouse or named-decorator registration. Given: path metadata/value and two lifetime cases; old support ASTs.
2. **Explicit consumer bindings:** all eight modules use support.path; seven use support.store directly, with no local replacement. test_store_links uses support.store as base_store and its one seeded adapter with the original seed transaction/values/order. Remove duplicated local empty fixtures and path fixtures; do not change conftest or global registration. Given: eight identity/binding cases, exact seed AST and installed-pytest alias spike.
3. **One strict refusal helper:** core and keyed-core use support.refused without changing call sites. Require CoreError, matching code AND string, and exactly one callback invocation. No-error must fail, mismatched code/text must fail, an unrelated exception with matching attributes/text must propagate unchanged. Strengthening the keyed helper to the original core contract is intentional and does not change real CoreError behavior. Given: five refusal cases and binding checks.
4. **Preserve tests and selectors:** all 304 existing scoped node IDs, parameters, test functions, assertions, helper bodies and seed values remain intact, in the same files and core section. Given normalization permits only imports, the listed fixture/refusal definitions and the exact seeded-module __all__ = ["base_store"] declaration to change; seeded adapter has its own exact body pin. Keep run/fixed_times/fixed_ids/load_script bodies unchanged. No test body rewrite or consolidation, renaming, skip, xfail, deletion or duplicate case. Given: eight body fingerprints, four helper fingerprints, seed and collection checks.
5. **Test-only boundaries:** every app module, repository utility/script, dependency/coverage/section registry, global conftest guard and Phase 2n preservation manifest in the given frozen inventory is byte-identical. Keep separate product/tooling 100% gates and overall 90%; no source or packaging changes, added dependency, real account/data/Keychain access or network operation. Given: frozen inventory and full checker.
6. **Finish the scoped migration:** new support contracts and consumer fixture identities must pass in ordinary pytest execution, not only direct wrapper tests. Retain the seeded adapter and existing successful/refused clock counts. New helper tests live in core via existing fallback section rules. No modifications to earlier specs, guides, probes, manifests, node IDs or tool interfaces are required. Coder writes the behavioral checks below.

7. **Progress entry** for `## Phase 2o: Shared product test support (YYYY-MM-DD)` at the end of `docs/progress.md`.

## Given files

Already committed with this spec; never change them.

| File | What it is |
|---|---|
| `tests/product_support_manifest.json` | Immutable eight-consumer ASTs, 304 node IDs, seed/support/runner pins and 38 frozen source/config paths |
| `tests/product_support_cases.py` | Given AST/inventory readers and scoped collection runner; no test cases |
| `tests/unit/test_product_test_support.py` | 32 tests from 10 functions (requirements 1–5) |
| `docs/verification/probe-02o.py` | The verifier's probe |

Given test count: **32** (10 functions), including the corrected runtime-collision regression. The original handoff had 31; its historical baseline evidence above is retained. Against stopped implementation f0c9972, the corrected givens fail on the old store dependency, missing explicit re-export and real reference-case execution. No original test ID, body, seed or manifest digest is changed; full acceptance is at least 1,293 cases.

## Tests to write

Write tests/unit/test_product_test_support_more.py:

- Use a conventional __all__ = ["base_store"] re-export where the seeded fixture alias would otherwise be unused; remove no-op decorators in both the real adapter and the synthetic consumer.
- Import the actual shared fixtures into a synthetic temporary pytest consumer; show two tests receive distinct empty stores/paths and the first connection is closed before the second test. Keep the synthetic runner offline and use no real settings/data.
- Exercise the seeded base_store alias through normal pytest with the original two rows/IDs/timestamps, and confirm teardown closes once. Do not duplicate the seeded adapter in this project’s real consumers.
- The shared refused helper invokes its callback once and preserves the same unexpected exception object; no-return/no-error and mismatched-text remain failures. Do not broaden its catch.
- Confirm importing/registering fixtures does not open a Store or read a clock; opening is lazy on fixture use. Existing fixtures still do not look up settings or read the owner’s data.
- Add only deciding test-support behavior checks in this one new file. No runtime, tooling, global guard or coverage configuration changes; all earlier consumer test bodies stay immutable.

## Scope

| Path | Change |
|---|---|
| `tests/unit/test_product_test_support_more.py` | create |
| `tests/support.py` | edit: add shared path/store fixtures and strict refusal helper; preserve four existing helper bodies |
| `tests/integration/test_core.py` | edit: shared fixture imports and removal of local copies only; body AST pinned; shared refused import/removal |
| `tests/integration/test_core_keyed.py` | edit: shared fixture imports and removal of local copies only; body AST pinned; shared refused import/removal |
| `tests/integration/test_core_identity.py` | edit: shared fixture imports and removal of local copies only; body AST pinned |
| `tests/integration/test_core_references.py` | edit: shared fixture imports and removal of local copies only; body AST pinned |
| `tests/integration/test_intake.py` | edit: shared fixture imports and removal of local copies only; body AST pinned |
| `tests/integration/test_intake_identity.py` | edit: shared fixture imports and removal of local copies only; body AST pinned |
| `tests/integration/test_store.py` | edit: shared fixture imports and removal of local copies only; body AST pinned |
| `tests/integration/test_store_links.py` | edit: shared base_store/path imports and seeded adapter only; seed body pinned; explicit __all__ fixture re-export |
| `docs/progress.md` | append your entry |

## Out of scope

- Moving/merging/renaming test files or IDs, rewriting assertions/fixtures/data, combining continuation files, changing sections or historical command references (later consolidation phases).
- Tooling test changes, edits to the Phase 2n manifest or older probes/specs/guides, dynamic path aliases, compatibility collection hooks or global fixture plugins.
- Product/runtime/source/schema/settings/ID behavior, new dependencies, coverage gates/floors, global fake/privacy guards, services or real data.
- New seed policies, helper settings/clock access or changes to existing run/fixed_times/fixed_ids/load_script behavior.
- Any change to a given file, `AGENTS.md` or the design docs.

## Rules that bite

- **Preservation:** share setup/assertion helpers while retaining cases, selectors, seeded data and every test-body assertion. Stronger refusal text checking matches the existing core helper.
- **Isolation/privacy:** explicit function-scoped fixtures use only tmp_path; no eager/global connection, owner data, Keychain, account, service, telemetry or network.
- **Determinism/resources:** helpers add no clock/ID reads; each fixture owns one temporary Store and closes it once, including exception exit. Seed adapters borrow it.
- **Boundaries:** test-only code, no product/tooling implementation or global guard changes, and no reduction of either coverage gate.
- **Time through the module**: `clock.now()`, never `datetime.now()`, and never `from docket.clock import now`.
- If you stop before finishing, still write the progress entry with a `Stopped:` first follow-up (`docs/phase-conventions.md`, "When you stop").
- Commands start with `.venv/bin/python`; no bare `python3`, `pytest` or `ruff`.

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_product_test_support.py` | `1261` or more passed, 0 failed, 0 errors |
| `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1293 passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest tests/unit/test_product_test_support.py --no-cov -q` | `32 passed` |
| `.venv/bin/python -m coverage report --include=src/docket/core.py,src/docket/store.py,docket_tools/reports.py,docket_tools/acceptance.py,docket_tools/spotcheck.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| `.venv/bin/python docs/verification/probe-02o.py` | last line `FAILURES 0` |
| `grep -c "^## Phase 2o: " docs/progress.md` | `1` |
| `.venv/bin/python scripts/check_reports.py --phase 2o` | `Reports OK.` |
| `git diff HEAD --stat -- tests/product_support_manifest.json tests/product_support_cases.py tests/unit/test_product_test_support.py docs/verification/probe-02o.py` | no output |
| `git status --short` | only the Scope paths |

### Searches

Each prints nothing.

```zsh
git grep --untracked -n -E 'import (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)|from (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)' -- src docket_tools tests/support.py
git grep --untracked -n -E 'print\(|logging|logger|warnings\.warn' -- src docket_tools tests/support.py ':!src/docket/cli.py'
git grep --untracked -n -E 'datetime\.now|datetime\.utcnow|date\.today|time\.time\(|from docket\.(clock|ids) import' -- src docket_tools tests/support.py ':!src/docket/clock.py'
git grep --untracked -n -E '\.(insert_task|update_task|append_audit|insert_link|insert_request_key)\(' -- src docket_tools tests/support.py ':!src/docket/core.py' ':!src/docket/store.py'
git grep --untracked -n -E 'ollama|anthropic|openai|langchain' -- src docket_tools tests/support.py
git grep --untracked -n -E 'pragma: no cover|noqa' -- tests/support.py
```
