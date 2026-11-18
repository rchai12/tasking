# Verification guide: Phase 2l (Audit, link and request-key boundaries)

Spec: `docs/phases/phase-02l-audit-link-and-key-boundaries.md`. Follow `docs/phase-conventions.md` ("For the verifier"). Never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor, never read the Keychain, and never open the real data folder.

## 1. Coder ran

Stop with FAIL ("the coder did not run") if any of these is missing:

- `src/docket/_store_audit.py`
- `src/docket/_store_links.py`
- `src/docket/_store_keys.py`
- `tests/integration/test_audit_link_key_contracts.py`
- `grep -c "^## Phase 2l: " docs/progress.md` prints `1`

Stop with FAIL ("the coder stopped") if that entry's first `Follow-ups` line starts with `Stopped:`, as "A stopped coder" in `docs/phase-conventions.md` says. With no entry, `git status --short` tells "the coder did not run" (no Scope path changed) from "the coder broke off without reporting" (Scope paths changed; name them under `For the architect`).

Stop with FAIL ("the baseline is not committed") if `git ls-files --error-unmatch docs/phases/phase-02l-audit-link-and-key-boundaries.md tests/store_boundary_cases.py tests/integration/test_store_table_boundaries.py scripts/critical_modules.txt docs/verification/probe-02l.py` fails: the diff gates can only be judged against a committed spec and given files.

## 2. Gates

Run each from the repository root, in this order: `.venv/bin/python scripts/accept.py --phase 2l --guide` runs them and the searches, one line each. Given test count: 18.

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_store_table_boundaries.py` | at least 1170 passed, 0 failed (the coder's `*_more.py` tests add to the count) |
| G2 | `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1188 passed, 0 failed, 0 skipped |
| G3 | `.venv/bin/python -m pytest tests/integration/test_store_table_boundaries.py --no-cov -q` | `18 passed` |
| G4 | `.venv/bin/python -m coverage report --include=src/docket/_store_audit.py,src/docket/_store_links.py,src/docket/_store_keys.py,src/docket/store.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| G5 | `.venv/bin/python docs/verification/probe-02l.py` | last line `FAILURES 0` |
| G6 | `grep -c "^## Phase 2l: " docs/progress.md` | `1` |
| G7 | `.venv/bin/python scripts/check_reports.py --phase 2l` | `Reports OK.` |
| G8 | `git diff HEAD --stat -- tests/store_boundary_cases.py tests/integration/test_store_table_boundaries.py scripts/critical_modules.txt docs/verification/probe-02l.py` | no output |
| G9 | `git status --short` | only the Scope paths |
| G10 | `.venv/bin/python -m pip list --format=freeze \| wc -l` | `39` (unchanged; no dependency is added) |

## 3. Spot checks

Inspect the ownership boundary before mutations: only normal audit/link/key SQL moves. Public records, validation, transaction state, encoding/decoding, task SQL, setup and migration preflight stay in Store. No helper imports docket modules or creates/closes/replaces a connection. Every helper entry receives the original connection, and every facade write checks its original guards before delegation. No second creation path, new error mapping, schema or source capability is added.

Run mutations in a clean disposable checkout containing the planning baseline and implementation under review, with PYTHONPATH=src:. directed at that checkout. Do not mutate the owner's live checkout. S2–S7 were confirmed against the old facade query bodies or names-only helpers before extraction; translate the identical SQL/policy mutation to its final owner. S1 is a paper check of the new key reader. No complete reference extraction was built.

For a module under `src/`, write the change as an exact old and new text in the module the coder wrote and run `.venv/bin/python scripts/spot_check.py <module> --old '<old>' --new '<new>' --test '<deciding test>' --row S<n>`; it restores the module and prints one line. For any other file:
1. Copy the module outside the repository.
2. Make the change described in the module the coder wrote.
3. Run the deciding test with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest '<test>' --no-cov -q --tb=line`, and confirm it fails with the "Broken" value; rerun with `-vv` only when it doesn't.
4. Restore the module from your copy, delete `src/docket/__pycache__`, and confirm `git diff` is as before.

A different failure from the "Broken" column is a note, not a finding; a pass is a finding.

| # | Module | Change | Deciding test | Correct | Broken |
|---|---|---|---|---|---|
| S1 | _store_keys.py, key reader | Replace its lookup result with None | `tests/integration/test_store_table_boundaries.py::test_facade_keeps_literal_records_json_and_per_client_keys_after_reopen` | saved RequestKey after reopen | None |
| S2 | _store_links.py, per-task list SQL | Replace WHERE task = ? with WHERE ? IS NOT NULL, retaining its one parameter | `tests/integration/test_store_table_boundaries.py::test_reads_keep_task_filtering_order_and_missing_results` | t1 links l1,l3 | l1,l2,l3 |
| S3 | _store_links.py, list ordering | Change ORDER BY number to ORDER BY number DESC | `tests/integration/test_store_table_boundaries.py::test_reads_keep_task_filtering_order_and_missing_results` | l1,l3 | l3,l1 |
| S4 | _store_audit.py, list ordering | Change ORDER BY number to ORDER BY number DESC | `tests/integration/test_store_table_boundaries.py::test_reads_keep_task_filtering_order_and_missing_results` | create,retitle | retitle,create |
| S5 | store.py, Store.transaction exception branch | Change its ROLLBACK statement to COMMIT | `tests/integration/test_store_table_boundaries.py::test_sql_failure_rolls_back_all_tables_and_sequences_together[create-after-audit]` | empty baseline rows/sequences preserved | partial task/audit/sequences committed |
| S6 | store.py, JSON encoding | Replace serialization.canonical_json(value) with json.dumps(value) | `tests/integration/test_store_table_boundaries.py::test_facade_keeps_literal_records_json_and_per_client_keys_after_reopen` | exact compact sorted Unicode snapshot | altered raw audit JSON |
| S7 | store.py, append_audit | Remove its _require_write(at) call | `tests/integration/test_store_table_boundaries.py::test_facade_refuses_writes_before_any_table_helper_is_called[audit]` | a write needs a transaction | wrong refusal order; unknown task instead |

## 4. Probe

Run `.venv/bin/python docs/verification/probe-02l.py` from the repository root. It is a given file: do not edit it. Every line must end in `ok`; the last line must be `FAILURES 0`. A stop at the probe's own `assert` lines, before its self-check prints `ok`, is the probe's fault: report it under "For the architect", not as a finding. It touches no network, Keychain or real data folder.

The probe independently checks the table/module map, then records actual execute callers on one connection, reopens and repeats both task/link requests without changing any row or sequence, and forces post-audit/post-key failures across reopen. Each case has a fresh synthetic folder. `--oracle-only` must show FAILURES 0. Baseline prints missing-module and wrong-SQL-owner failures while replay/rollback guards pass; imports do not crash the run. The repository-root helper import is explicitly configured and checked using the published command.

## 5. Searches

Each prints nothing. A match is a finding against the rule it names.

| # | Rule | Command |
|---|---|---|
| Q1 | no network code | `git grep --untracked -n -E 'import (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)\|from (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)' -- src` |
| Q2 | no output outside the CLI | `git grep --untracked -n -E 'print\(\|logging\|logger\|warnings\.warn' -- src ':!src/docket/cli.py'` |
| Q3 | time read only in clock.py, through the module | `git grep --untracked -n -E 'datetime\.now\|datetime\.utcnow\|date\.today\|time\.time\(\|from docket\.(clock\|ids) import' -- src ':!src/docket/clock.py'` |
| Q4 | only the core writes tasks, audit rows, links and keys | `git grep --untracked -n -E '\.(insert_task\|update_task\|append_audit\|insert_link\|insert_request_key)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'` |
| Q5 | no model client | `git grep --untracked -n -E 'ollama\|anthropic\|openai\|langchain' -- src` |
| Q6 | no coverage or lint exclusions in this phase's modules | `git grep --untracked -n -E 'pragma: no cover\|noqa' -- src/docket/_store_audit.py src/docket/_store_links.py src/docket/_store_keys.py src/docket/store.py` |

(In the table, `\|` is a `|` in the command.)

## 6. Reasonable variations

These are correct even though the spec does not spell them out:

- Private function names, signatures after the first connection parameter, typed Row/scalar return details and local helpers. Entry functions still receive connection first and execute through that connection; Store calls via each module.
- Returning an inserted row number or raw SQLite result to Store, which constructs the same public record. Records, error types, sentinels and conversion policy never move.
- Keeping existing facade private helpers as delegators, or inlining their delegation into facade methods; link existence/readback SQL still belongs to _store_links.
- SQL whitespace changes that retain bound parameters, columns, filters and ordering. Migration and preflight query text stays unchanged; no query redesign.
- Private helpers inside the Scope modules, and extra behaviour tests in `*_more.py` files.

## 7. Verdict

Write `docs/reviews/phase-02l-audit-link-and-key-boundaries.md` in the form `docs/phase-conventions.md` gives (`# Review: Phase 2l`), then run `.venv/bin/python scripts/check_reports.py --phase 2l`; it must print `Reports OK.`

## Test path migration (Phase 2q)

The product continuation paths above now use behaviour names. This is a byte-identical file move; function names, parameter IDs, counts and original implementation history are unchanged. The phase's immutable move inventory records every old/new selector.
