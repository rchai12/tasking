# Verification guide: Phase 3d (Daily digest)

Spec: `docs/phases/phase-03d-daily-digest.md`. Follow `docs/phase-conventions.md` ("For the verifier"). Never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor, never read the Keychain, and never open the real data folder.

## 1. Coder ran

Stop with FAIL ("the coder did not run") if any of these is missing:

- `src/docket/_store_digests.py`
- `tests/integration/test_daily_digest_edges.py`
- `grep -c "^## Phase 3d: " docs/progress.md` prints `1`

Stop with FAIL ("the coder stopped") if that entry's first `Follow-ups` line starts with `Stopped:`, as "A stopped coder" in `docs/phase-conventions.md` says. With no entry, `git status --short` tells "the coder did not run" (no Scope path changed) from "the coder broke off without reporting" (Scope paths changed; name them under `For the architect`).

Stop with FAIL ("the baseline is not committed") if `git ls-files --error-unmatch docs/phases/phase-03d-daily-digest.md src/docket/schema.py src/docket/notifier.py scripts/critical_modules.txt tests/notifier_cases.py tests/digest_cases.py tests/integration/test_daily_digest.py tests/integration/test_digest_store_contracts.py tests/integration/test_audit_link_key_contracts.py tests/integration/test_reference_coverage.py tests/integration/test_reference_migration.py tests/integration/test_reminder_storage_edges.py tests/integration/test_server.py tests/integration/test_store.py tests/integration/test_store_coordination.py tests/integration/test_store_links.py tests/integration/test_store_safety_coverage.py tests/startup_cases.py docs/verification/probe-02g.py docs/verification/probe-02i.py docs/verification/probe-03b.py docs/verification/probe-03c.py tests/product_consolidation_manifest.json tests/product_organization_manifest.json tests/product_support_manifest.json tests/tooling_boundary_manifest.json docs/verification/probe-03d.py` fails: the diff gates can only be judged against a committed spec and given files.

## 2. Gates

Run each from the repository root, in this order: `.venv/bin/python scripts/accept.py --phase 3d --guide` runs them and the searches, one line each. Given test count: 87.

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_daily_digest.py --ignore=tests/integration/test_digest_store_contracts.py` | at least 1558 passed, 0 failed (the coder's `*_more.py` tests add to the count) |
| G2 | `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1645 passed, 0 failed, 0 skipped |
| G3 | `.venv/bin/python -m pytest tests/integration/test_daily_digest.py tests/integration/test_digest_store_contracts.py --no-cov -q` | `87 passed` |
| G4 | `.venv/bin/python -m coverage report --include=src/docket/_store_digests.py,src/docket/store.py,src/docket/reminders.py,src/docket/schema.py,docket_tools/reports.py,docket_tools/acceptance.py,docket_tools/spotcheck.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| G5 | `.venv/bin/python docs/verification/probe-03d.py` | last line `FAILURES 0` |
| G6 | `grep -c "^## Phase 3d: " docs/progress.md` | `1` |
| G7 | `.venv/bin/python scripts/check_reports.py --phase 3d` | `Reports OK.` |
| G8 | `git diff HEAD --stat -- src/docket/schema.py src/docket/notifier.py scripts/critical_modules.txt tests/notifier_cases.py tests/digest_cases.py tests/integration/test_daily_digest.py tests/integration/test_digest_store_contracts.py tests/integration/test_audit_link_key_contracts.py tests/integration/test_reference_coverage.py tests/integration/test_reference_migration.py tests/integration/test_reminder_storage_edges.py tests/integration/test_server.py tests/integration/test_store.py tests/integration/test_store_coordination.py tests/integration/test_store_links.py tests/integration/test_store_safety_coverage.py tests/startup_cases.py docs/verification/probe-02g.py docs/verification/probe-02i.py docs/verification/probe-03b.py docs/verification/probe-03c.py tests/product_consolidation_manifest.json tests/product_organization_manifest.json tests/product_support_manifest.json tests/tooling_boundary_manifest.json docs/verification/probe-03d.py` | no output |
| G9 | `git status --short` | only the Scope paths |
| G10 | `.venv/bin/python -m pip list --format=freeze \| wc -l` | `39` (unchanged; no dependency added) |

## 3. Spot checks

For a module under `src/`, write the change as an exact old and new text in the module the coder wrote and run `.venv/bin/python scripts/spot_check.py <module> --old '<old>' --new '<new>' --test '<deciding test>' --row S<n>`; it restores the module and prints one line. For any other file:
1. Copy the module outside the repository.
2. Make the change described in the module the coder wrote.
3. Run the deciding test with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest '<test>' --no-cov -q --tb=line`, and confirm it fails with the "Broken" value; rerun with `-vv` only when it doesn't.
4. Restore the module from your copy, delete `src/docket/__pycache__`, and confirm `git diff` is as before.

A different failure from the "Broken" column is a note, not a finding; a pass is a finding.

| # | Module | Change | Deciding test | Correct | Broken |
|---|---|---|---|---|---|
| S1 | `_store_digests.py`, the claim UPDATE | drop the condition on an existing claim, so any unsent digest of the day with a live member is claimed | `tests/integration/test_daily_digest.py::test_a_second_pass_during_a_digest_send_sends_nothing` | inner pass [False] | inner pass [True] |
| S2 | `_store_digests.py`, the claim UPDATE | change the stale comparison from strictly before to at or before | `tests/integration/test_daily_digest.py::test_a_crash_mid_digest_resends_once_with_the_same_key_after_five_minutes[before-send]` | passes [False, True, False] | passes [True, False, False] |
| S3 | `_store_digests.py`, the claim UPDATE | drop the condition that a member is still open with a deadline at or before overdue_before | `tests/integration/test_digest_store_contracts.py::test_a_claim_takes_only_that_days_unsent_digest_with_a_task_still_overdue[all-ended]` | None | d1 |
| S4 | `reminders.py`, the overdue rule | compare the deadline plus 720 minutes with the pass's now instead of the slot, wherever the rule is applied | `tests/integration/test_daily_digest.py::test_a_missed_seven_o_clock_goes_out_on_the_first_pass_that_home_day_only[back-that-afternoon]` | t2, t7, t1, t3 | t2, t7, t1, t3, t4 |
| S5 | `reminders.py`, the overdue rule | change at or before the slot to strictly before | `tests/integration/test_daily_digest.py::test_one_digest_a_day_lists_tasks_past_their_last_late_reminder_in_deadline_order` | task_ids t1, t2, t3, t7 | task_ids t1, t2, t7 |
| S6 | `reminders.py`, digest_heading | always write `tasks` | `tests/integration/test_daily_digest.py::test_the_heading_counts_the_tasks_it_lists[one]` | Still open past their deadlines: 1 task. | Still open past their deadlines: 1 tasks. |
| S7 | `reminders.py`, digest_slot | take the day from now in UTC instead of in the zone | `tests/integration/test_daily_digest.py::test_the_slot_is_that_home_day_at_the_digest_time[home-day-behind-utc]` | 2026-11-20, 12:00 UTC | 2026-11-21, 12:00 UTC the next day |
| S8 | `reminders.py`, send_digest | on NotifierError, return False without releasing the claim | `tests/integration/test_daily_digest.py::test_a_refused_digest_is_retried_each_pass_with_the_same_key_without_ended_tasks` | claimed_at None | claimed_at 12:00 UTC |
| S9 | `reminders.py`, send_digest | send with a fresh ids.new_id() instead of the stored key | `tests/integration/test_daily_digest.py::test_a_refused_digest_is_retried_each_pass_with_the_same_key_without_ended_tasks` | keys k1, k1 | StopIteration on a second id |
| S10 | `reminders.py`, send_digest | order the lines by task number instead of by deadline, then number | `tests/integration/test_daily_digest.py::test_one_digest_a_day_lists_tasks_past_their_last_late_reminder_in_deadline_order` | lines t2, t7, t1, t3 | lines t1, t2, t3, t7 |
| S11 | `store.py`, queue_digest | skip the check that each task is open | `tests/integration/test_digest_store_contracts.py::test_digest_writes_refuse_before_any_sql_change[ended-task]` | StoreError task not open: t4 | no error raised |

## 4. Probe

Run `.venv/bin/python docs/verification/probe-03d.py` from the repository root. It is a given file: do not edit it. Every line must end in `ok`; the last line must be `FAILURES 0`. A stop at the probe's own `assert` lines, before its self-check prints `ok`, is the probe's fault: report it under "For the architect", not as a finding. It touches no network, Keychain or real data folder.

The oracle pins schema version 6, the 07:00 slots on both sides of the 2026-11-01 change and the heading before touching a candidate. A scripted walk across Oct 30 to Nov 5 in `America/New_York` then forces a refused send, a crash before and after delivery, two restarts, a day with nothing overdue, a day with no pass, a return late in the day, a member ended before a retry, and a digest whose only member ended. A seeded random walk mixes the same events with reopens, removed deadlines and new overdue tasks. Every attempt is checked when it is made: its home day and slot, and lines that are exactly its still-overdue members in deadline order. After every pass the probe checks one clock read and at most one new digest and id. After each healthy pass past the slot, it checks that a day has no digest only when nothing was overdue, and that a digest with a live member is sent. At the end it checks that no key or home day was delivered twice, and nothing is marked sent that was never delivered.

## 5. Searches

Each prints nothing. A match is a finding against the rule it names.

| # | Rule | Command |
|---|---|---|
| Q1 | no network code | `git grep --untracked -n -E 'import (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)\|from (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)' -- src` |
| Q2 | no output outside the CLI | `git grep --untracked -n -E 'print\(\|logging\|logger\|warnings\.warn' -- src ':!src/docket/cli.py'` |
| Q3 | time read only in clock.py, through the module | `git grep --untracked -n -E 'datetime\.now\|datetime\.utcnow\|date\.today\|time\.time\(\|from docket\.(clock\|ids) import' -- src ':!src/docket/clock.py'` |
| Q4 | only the core writes tasks, audit rows, links and keys | `git grep --untracked -n -E '\.(insert_task\|update_task\|append_audit\|insert_link\|insert_request_key)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'` |
| Q5 | no model client | `git grep --untracked -n -E 'ollama\|anthropic\|openai\|langchain' -- src` |
| Q6 | no coverage or lint exclusions in this phase's modules | `git grep --untracked -n -E 'pragma: no cover\|noqa' -- src/docket/_store_digests.py src/docket/store.py src/docket/reminders.py` |
| Q7 | retry keys are made only by the engine, once per digest or post | `git grep --untracked -n -E 'ids\.new_id\(' -- src ':!src/docket/reminders.py'` |
| Q8 | digests are queued, claimed and finished only by the engine | `git grep --untracked -n -E '\.(queue_digest\|claim_digest\|release_digest\|mark_digest_sent)\(' -- src ':!src/docket/reminders.py' ':!src/docket/store.py'` |
| Q9 | nothing in this phase sends the digest on a schedule or from a command | `git grep --untracked -n -E 'send_digest\(' -- src ':!src/docket/reminders.py' ':!src/docket/notifier.py'` |
| Q10 | the digest takes its zone and time from its caller, with no timer, thread or event loop | `git grep --untracked -n -E 'get_settings\|DIGEST_TIME\|time\.sleep\(\|asyncio\|threading' -- src/docket/reminders.py src/docket/store.py src/docket/_store_digests.py` |

(In the table, `\|` is a `|` in the command.)

## 6. Reasonable variations

These are correct even though the spec does not spell them out:

- SQL function names in `_store_digests`, and the claim as an `UPDATE ... RETURNING` or an equivalent single statement in one transaction, as long as the given SQL-ownership test passes.
- Choosing the overdue tasks in Python from `store.tasks` or with a new read-only Store query, as long as the rule is the spec's and is judged at the slot.
- Computing the slot with `deadlines.make_deadline` or with `zoneinfo` directly, as long as the given slot cases pass.
- Returning before opening a transaction when the pass is before the slot.
- Extra behaviour tests in `tests/integration/test_daily_digest_edges.py`. Anything that sends from a command, sleeps, reads settings, renders a card or lists proposals is not a variation.
- Private helpers inside the Scope modules, and extra behaviour tests in `*_more.py` files.

## 7. Verdict

Write `docs/reviews/phase-03d-daily-digest.md` in the form `docs/phase-conventions.md` gives (`# Review: Phase 3d`), then run `.venv/bin/python scripts/check_reports.py --phase 3d`; it must print `Reports OK.`
