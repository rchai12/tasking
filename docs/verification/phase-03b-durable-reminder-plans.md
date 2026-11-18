# Verification guide: Phase 3b (Durable reminder plans)

Spec: `docs/phases/phase-03b-durable-reminder-plans.md`. Follow `docs/phase-conventions.md` ("For the verifier"). Never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor, never read the Keychain, and never open the real data folder.

## 1. Coder ran

Stop with FAIL ("the coder did not run") if any of these is missing:

- `src/docket/_store_reminders.py`
- `tests/integration/test_reminder_storage_edges.py`
- `grep -c "^## Phase 3b: " docs/progress.md` prints `1`

Stop with FAIL ("the coder stopped") if that entry's first `Follow-ups` line starts with `Stopped:`, as "A stopped coder" in `docs/phase-conventions.md` says. With no entry, `git status --short` tells "the coder did not run" (no Scope path changed) from "the coder broke off without reporting" (Scope paths changed; name them under `For the architect`).

Stop with FAIL ("the baseline is not committed") if `git ls-files --error-unmatch docs/phases/phase-03b-durable-reminder-plans.md tests/reminder_storage_cases.py tests/preservation_cases.py tests/integration/test_durable_reminders.py tests/integration/test_reminder_store_contracts.py tests/unit/test_feature_preservation.py docs/verification/probe-02g.py docs/verification/probe-02i.py scripts/critical_modules.txt src/docket/schema.py src/docket/views.py src/docket/domain.py tests/integration/test_audit_link_key_contracts.py tests/integration/test_reference_coverage.py tests/integration/test_reference_migration.py tests/integration/test_server.py tests/integration/test_store.py tests/integration/test_store_coordination.py tests/integration/test_store_links.py tests/integration/test_store_safety_coverage.py tests/product_consolidation_cases.py tests/product_consolidation_manifest.json tests/product_organization_cases.py tests/product_organization_manifest.json tests/product_support_manifest.json tests/startup_cases.py tests/tooling_boundary_manifest.json tests/unit/test_product_test_support.py docs/verification/probe-03b.py` fails: the diff gates can only be judged against a committed spec and given files.

## 2. Gates

Run each from the repository root, in this order: `.venv/bin/python scripts/accept.py --phase 3b --guide` runs them and the searches, one line each. Given test count: 83.

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_durable_reminders.py --ignore=tests/integration/test_reminder_store_contracts.py --ignore=tests/unit/test_feature_preservation.py` | at least 1382 passed, 0 failed (the coder's `*_more.py` tests add to the count) |
| G2 | `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1465 passed, 0 failed, 0 skipped |
| G3 | `.venv/bin/python -m pytest tests/integration/test_durable_reminders.py tests/integration/test_reminder_store_contracts.py tests/unit/test_feature_preservation.py --no-cov -q` | `83 passed` |
| G4 | `.venv/bin/python -m coverage report --include=src/docket/_store_reminders.py,src/docket/core.py,src/docket/store.py,src/docket/reminders.py,src/docket/schema.py,docket_tools/reports.py,docket_tools/acceptance.py,docket_tools/spotcheck.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| G5 | `.venv/bin/python docs/verification/probe-03b.py` | last line `FAILURES 0` |
| G6 | `grep -c "^## Phase 3b: " docs/progress.md` | `1` |
| G7 | `.venv/bin/python scripts/check_reports.py --phase 3b` | `Reports OK.` |
| G8 | `git diff HEAD --stat -- tests/reminder_storage_cases.py tests/preservation_cases.py tests/integration/test_durable_reminders.py tests/integration/test_reminder_store_contracts.py tests/unit/test_feature_preservation.py docs/verification/probe-02g.py docs/verification/probe-02i.py scripts/critical_modules.txt src/docket/schema.py src/docket/views.py tests/integration/test_audit_link_key_contracts.py tests/integration/test_reference_coverage.py tests/integration/test_reference_migration.py tests/integration/test_server.py tests/integration/test_store.py tests/integration/test_store_coordination.py tests/integration/test_store_links.py tests/integration/test_store_safety_coverage.py tests/product_consolidation_cases.py tests/product_consolidation_manifest.json tests/product_organization_cases.py tests/product_organization_manifest.json tests/product_support_manifest.json tests/startup_cases.py tests/tooling_boundary_manifest.json tests/unit/test_product_test_support.py src/docket/domain.py docs/verification/probe-03b.py` | no output |
| G9 | `git status --short` | only the Scope paths |
| G10 | `.venv/bin/python -m pip list --format=freeze \| wc -l` | `39` (unchanged; no dependency added) |

## 3. Spot checks

Use a clean disposable verification checkout, as the roadmap requires; a process termination can bypass the mutation runner's restoration. Judge the full diff from the committed planning baseline. The SQL/core/store mutations below are paper checks of the specified contracts, not a reference implementation built by the architect. Apply one local semantic change in the named function/SQL predicate, keeping its deciding input and restoring before the next.

Before judging code, inspect the planning-time given diff against d927fd9: migrations 1–3, old domain policy and view mappings remain exact; only migration 4, REMINDER_KINDS and one refusal entry are added. Current-version pins become 4 but failed-upgrade version 2, reference rebuild version 3 and unsupported version 99 stay literal. The old current-startup node ID is retained with input 4. Source freezes for core/store preserve 38/86 old nodes, four signatures and import atoms; only the specified method bodies are mutable. Every unrelated byte hash, case/selector/seed inventory and document contract remains effective. Verify that frozen-loop readers only delegate the same assertions to the shared reader, and that the new helper's mutation tests reject changed stable roles, signatures/imports and bytes. New private helpers are allowed; alterations to old unrelated methods or import meaning are findings.

Inspect all core approval/refusal branches as well as the new tests: new internal reminder writes do not create or approve a task. Keyed replays, no-op/title/start/link operations must not consume IDs or rewrite plans. Range refusals must not leak library text through either adapter. Upgrade backfill must be inside the version-3 transaction, not an initialization step run at every open. No new ordinary task-helper calls during backfill.

For a module under `src/`, write the change as an exact old and new text in the module the coder wrote and run `.venv/bin/python scripts/spot_check.py <module> --old '<old>' --new '<new>' --test '<deciding test>' --row S<n>`; it restores the module and prints one line. For any other file:
1. Copy the module outside the repository.
2. Make the change described in the module the coder wrote.
3. Run the deciding test with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest '<test>' --no-cov -q --tb=line`, and confirm it fails with the "Broken" value; rerun with `-vv` only when it doesn't.
4. Restore the module from your copy, delete `src/docket/__pycache__`, and confirm `git diff` is as before.

A different failure from the "Broken" column is a note, not a finding; a pass is a finding.

| # | Module | Change | Deciding test | Correct | Broken |
|---|---|---|---|---|---|
| S1 | `_store_reminders.py`, void_reminders | remove the sent_at IS NULL predicate from its UPDATE | `tests/integration/test_reminder_store_contracts.py::test_low_level_records_pending_voids_and_restart` | sent r1 remains unvoided | r1 has a void time |
| S2 | `core.py`, _insert_open_task | omit the new reminder synchronization call | `tests/integration/test_durable_reminders.py::test_approved_creation_persists_one_complete_plan[owner-False]` | nine literal rows | empty rows |
| S3 | `core.py`, edit_task | synchronize all kinds on a work-only edit | `tests/integration/test_durable_reminders.py::test_edits_replace_only_the_changed_pending_group[work]` | deadline rows r2–r10 remain unvoided | deadline rows voided/replaced |
| S4 | `core.py`, change_state | synchronize a new plan on start as well as reopen | `tests/integration/test_durable_reminders.py::test_unrelated_changes_and_retries_keep_reminder_ids_and_instants[start]` | identical original rows | changed rows/IDs |
| S5 | `store.py`, _apply_migration | change the version-3 backfill condition to version 99 | `tests/integration/test_durable_reminders.py::test_upgrade_backfills_active_tasks_once_using_stored_updated_at` | ten rows for t1 | empty rows |
| S6 | `core.py`, planner overflow conversion | re-raise the caught OverflowError instead of CoreError | `tests/integration/test_durable_reminders.py::test_overflow_is_a_safe_core_refusal_and_rolls_back[create]` | invalid_reminder_plan | OverflowError |
| S7 | `_store_reminders.py`, select_reminders | change ORDER BY number to ORDER BY number DESC | `tests/integration/test_durable_reminders.py::test_approved_creation_persists_one_complete_plan[owner-False]` | before first | final late first |
| S8 | `store.py`, the migration-4 backfill helper | pass task.created_at instead of task.updated_at to plan_reminders | `tests/integration/test_durable_reminders.py::test_backfill_uses_the_last_approved_instant_and_preserves_past_slots[due-soon]` | due_soon at 17:30 | before at 17:00 |
| S9 | `core.py`, check_title | replace title != title.strip() with False | `tests/unit/test_feature_preservation.py::test_unaffected_core_and_store_roles_keep_the_exact_feature_boundary` | stable baseline AST | AssertionError naming core.py:check_title |

## 4. Probe

Run `.venv/bin/python docs/verification/probe-03b.py` from the repository root. It is a given file: do not edit it. Every line must end in `ok`; the last line must be `FAILURES 0`. A stop at the probe's own `assert` lines, before its self-check prints `ok`, is the probe's fault: report it under "For the architect", not as a finding. It touches no network, Keychain or real data folder.

The oracle pins all three shipped migration strings, schema version 4, STRICT columns and literal schedule sizes before touching a candidate. The checks use separate synthetic databases: populated upgrade/restart with clock/ID traps, then keyed replay, title preservation, Done/Reopen history and an injected post-insert rollback. The forced edit clears the deadline and changes work to a new nonempty start plan, guaranteeing the insert interruption is reached. This is persistence/retry safety, not a sender or double-loop delivery test. The given spawned-upgrader case supplies independent-process coverage. --oracle-only must pass; an oracle failure is an architect issue.

## 5. Searches

Each prints nothing. A match is a finding against the rule it names.

| # | Rule | Command |
|---|---|---|
| Q1 | no network code | `git grep --untracked -n -E 'import (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)\|from (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)' -- src` |
| Q2 | no output outside the CLI | `git grep --untracked -n -E 'print\(\|logging\|logger\|warnings\.warn' -- src ':!src/docket/cli.py'` |
| Q3 | time read only in clock.py, through the module | `git grep --untracked -n -E 'datetime\.now\|datetime\.utcnow\|date\.today\|time\.time\(\|from docket\.(clock\|ids) import' -- src ':!src/docket/clock.py'` |
| Q4 | only the core writes tasks, audit rows, links and keys | `git grep --untracked -n -E '\.(insert_task\|update_task\|append_audit\|insert_link\|insert_request_key)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'` |
| Q5 | no model client | `git grep --untracked -n -E 'ollama\|anthropic\|openai\|langchain' -- src` |
| Q6 | no coverage or lint exclusions in this phase's modules | `git grep --untracked -n -E 'pragma: no cover\|noqa' -- src/docket/_store_reminders.py src/docket/core.py src/docket/store.py` |
| Q7 | Internal reminder rows do not allocate generated outbound keys | `git grep --untracked -n -E 'ids\.new_id\(' -- src/docket/core.py src/docket/store.py src/docket/_store_reminders.py` |
| Q8 | Reminder plan writes remain in core or the Store startup/facade boundary | `git grep --untracked -n -E '\.(insert_reminders\|void_reminders)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'` |

(In the table, `\|` is a `|` in the command.)

## 6. Reasonable variations

These are correct even though the spec does not spell them out:

- Private helper names and parameterized SQL construction may vary while retaining the exact public signatures, shared domain.REMINDER_KINDS policy, one connection/transaction, immutable history and selective group semantics.
- Extra meaningful tests stay in tests/integration/test_reminder_storage_edges.py. No caller time/ID reads are added, no scoped freeze is widened, no old guard is regenerated and no sender, lease, key, digest, service or cleanup work is approved. The reserved metadata columns do not authorize those behaviours.

## 7. Verdict

Write `docs/reviews/phase-03b-durable-reminder-plans.md` in the form `docs/phase-conventions.md` gives (`# Review: Phase 3b`), then run `.venv/bin/python scripts/check_reports.py --phase 3b`; it must print `Reports OK.`
