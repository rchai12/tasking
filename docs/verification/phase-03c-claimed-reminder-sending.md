# Verification guide: Phase 3c (Claimed reminder sending)

Spec: `docs/phases/phase-03c-claimed-reminder-sending.md`. Follow `docs/phase-conventions.md` ("For the verifier"). Never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor, never read the Keychain, and never open the real data folder.

## 1. Coder ran

Stop with FAIL ("the coder did not run") if any of these is missing:

- `src/docket/_store_posts.py`
- `tests/integration/test_reminder_sending_edges.py`
- `grep -c "^## Phase 3c: " docs/progress.md` prints `1`

Stop with FAIL ("the coder stopped") if that entry's first `Follow-ups` line starts with `Stopped:`, as "A stopped coder" in `docs/phase-conventions.md` says. With no entry, `git status --short` tells "the coder did not run" (no Scope path changed) from "the coder broke off without reporting" (Scope paths changed; name them under `For the architect`).

Stop with FAIL ("the baseline is not committed") if `git ls-files --error-unmatch docs/phases/phase-03c-claimed-reminder-sending.md src/docket/schema.py src/docket/notifier.py scripts/critical_modules.txt tests/notifier_cases.py tests/integration/test_reminder_sending.py tests/integration/test_post_store_contracts.py tests/integration/test_audit_link_key_contracts.py tests/integration/test_reference_coverage.py tests/integration/test_reference_migration.py tests/integration/test_reminder_storage_edges.py tests/integration/test_server.py tests/integration/test_store.py tests/integration/test_store_coordination.py tests/integration/test_store_links.py tests/integration/test_store_safety_coverage.py tests/startup_cases.py docs/verification/probe-02g.py docs/verification/probe-02i.py docs/verification/probe-03b.py tests/product_consolidation_manifest.json tests/product_organization_manifest.json tests/product_support_manifest.json tests/tooling_boundary_manifest.json docs/verification/probe-03c.py` fails: the diff gates can only be judged against a committed spec and given files.

## 2. Gates

Run each from the repository root, in this order: `.venv/bin/python scripts/accept.py --phase 3c --guide` runs them and the searches, one line each. Given test count: 80.

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_reminder_sending.py --ignore=tests/integration/test_post_store_contracts.py` | at least 1472 passed, 0 failed (the coder's `*_more.py` tests add to the count) |
| G2 | `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1552 passed, 0 failed, 0 skipped |
| G3 | `.venv/bin/python -m pytest tests/integration/test_reminder_sending.py tests/integration/test_post_store_contracts.py --no-cov -q` | `80 passed` |
| G4 | `.venv/bin/python -m coverage report --include=src/docket/_store_posts.py,src/docket/_store_reminders.py,src/docket/store.py,src/docket/reminders.py,src/docket/schema.py,docket_tools/reports.py,docket_tools/acceptance.py,docket_tools/spotcheck.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| G5 | `.venv/bin/python docs/verification/probe-03c.py` | last line `FAILURES 0` |
| G6 | `grep -c "^## Phase 3c: " docs/progress.md` | `1` |
| G7 | `.venv/bin/python scripts/check_reports.py --phase 3c` | `Reports OK.` |
| G8 | `git diff HEAD --stat -- src/docket/schema.py src/docket/notifier.py scripts/critical_modules.txt tests/notifier_cases.py tests/integration/test_reminder_sending.py tests/integration/test_post_store_contracts.py tests/integration/test_audit_link_key_contracts.py tests/integration/test_reference_coverage.py tests/integration/test_reference_migration.py tests/integration/test_reminder_storage_edges.py tests/integration/test_server.py tests/integration/test_store.py tests/integration/test_store_coordination.py tests/integration/test_store_links.py tests/integration/test_store_safety_coverage.py tests/startup_cases.py docs/verification/probe-02g.py docs/verification/probe-02i.py docs/verification/probe-03b.py tests/product_consolidation_manifest.json tests/product_organization_manifest.json tests/product_support_manifest.json tests/tooling_boundary_manifest.json docs/verification/probe-03c.py` | no output |
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
| S1 | `_store_posts.py`, the claim UPDATE | drop the condition on an existing claim, so every unsent post with a live reminder is claimed | `tests/integration/test_reminder_sending.py::test_a_second_loop_during_a_send_sends_nothing` | inner pass sends 0 | inner pass sends 1 |
| S2 | `_store_posts.py`, the claim UPDATE | change the stale comparison from strictly before to at or before | `tests/integration/test_reminder_sending.py::test_a_crash_mid_send_resends_once_with_the_same_key_after_five_minutes[before-send]` | passes send [0, 1, 0] | passes send [1, 0, 0] |
| S3 | `_store_posts.py`, the claim UPDATE | drop the condition that the post still has an unvoided reminder | `tests/integration/test_reminder_sending.py::test_a_task_ended_after_a_crashed_send_is_not_resent[done]` | passes send [0, 0] | passes send [1, 0] |
| S4 | `reminders.py`, send_due | set missed to the number of rows in the group instead of the rows with fire_at after planned_at | `tests/integration/test_reminder_sending.py::test_slots_already_past_when_planned_are_not_counted_as_missed[created]` | This is late. | Missed while docket was offline: 5 reminders. |
| S5 | `reminders.py`, notice_text | change the missed threshold from 2 to 1 | `tests/integration/test_reminder_sending.py::test_notice_text_is_fixed_per_kind_with_a_missed_line_from_two[before]` | Are you working on this? | Missed while docket was offline: 1 reminders. |
| S6 | `reminders.py`, send_due | on NotifierError, go on to the next post without releasing the claim | `tests/integration/test_reminder_sending.py::test_a_failed_send_is_retried_next_pass_with_the_same_key` | claim cleared (None, None) | claim kept at 16:00 |
| S7 | `reminders.py`, send_due | build the notice with a fresh ids.new_id() instead of the post's key | `tests/integration/test_reminder_sending.py::test_a_failed_send_is_retried_next_pass_with_the_same_key` | keys k1, k1 | StopIteration on a second id |
| S8 | `reminders.py`, send_due | take the kind of the group's first row instead of its last | `tests/integration/test_reminder_sending.py::test_reminders_that_came_due_while_down_become_one_status_message` | ends This is late. | ends Are you working on this? |
| S9 | the sent mark in `_store_reminders.py` | drop the condition that the reminder is unvoided | `tests/integration/test_post_store_contracts.py::test_a_claim_takes_only_unsent_unclaimed_or_stale_posts_with_a_live_reminder[partly-voided]` | r2 (None, 16:00) | r2 sent at 16:30 |
| S10 | `store.py`, queue_post | skip the check that each reminder is pending | `tests/integration/test_post_store_contracts.py::test_post_writes_refuse_before_any_sql_change[claimed]` | StoreError reminder not pending: r1 | IntegrityError from the UNIQUE link |
| S11 | `reminders.py`, send_due | queue one post for all due rows instead of one per task | `tests/integration/test_reminder_sending.py::test_deadlines_one_two_and_three_minutes_out_fire_in_order_once` | sends [3, 1, 1, 1, 0] | StoreError reminder not pending: r10 |

## 4. Probe

Run `.venv/bin/python docs/verification/probe-03c.py` from the repository root. It is a given file: do not edit it. Every line must end in `ok`; the last line must be `FAILURES 0`. A stop at the probe's own `assert` lines, before its self-check prints `ok`, is the probe's fault: report it under "For the architect", not as a finding. It touches no network, Keychain or real data folder.

The oracle pins schema version 5, the post link columns and the notice texts before touching a candidate. A scripted walk then forces a failed send, a crash before and after delivery, two restarts, a task ended after its claim, a reopen and two offline messages. A seeded random walk mixes the same events. After every pass the probe checks that the clock was read once and one id was used per new post. At the end it checks that no reminder is in two posts, no key was delivered twice, every text and missed count matches the reminders, and nothing due is left unsent.

## 5. Searches

Each prints nothing. A match is a finding against the rule it names.

| # | Rule | Command |
|---|---|---|
| Q1 | no network code | `git grep --untracked -n -E 'import (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)\|from (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)' -- src` |
| Q2 | no output outside the CLI | `git grep --untracked -n -E 'print\(\|logging\|logger\|warnings\.warn' -- src ':!src/docket/cli.py'` |
| Q3 | time read only in clock.py, through the module | `git grep --untracked -n -E 'datetime\.now\|datetime\.utcnow\|date\.today\|time\.time\(\|from docket\.(clock\|ids) import' -- src ':!src/docket/clock.py'` |
| Q4 | only the core writes tasks, audit rows, links and keys | `git grep --untracked -n -E '\.(insert_task\|update_task\|append_audit\|insert_link\|insert_request_key)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'` |
| Q5 | no model client | `git grep --untracked -n -E 'ollama\|anthropic\|openai\|langchain' -- src` |
| Q6 | no coverage or lint exclusions in this phase's modules | `git grep --untracked -n -E 'pragma: no cover\|noqa' -- src/docket/_store_posts.py src/docket/store.py src/docket/reminders.py src/docket/_store_reminders.py` |
| Q7 | retry keys are made only by the engine, once per post | `git grep --untracked -n -E 'ids\.new_id\(' -- src ':!src/docket/reminders.py'` |
| Q8 | posts are queued, claimed and finished only by the engine | `git grep --untracked -n -E '\.(queue_post\|claim_posts\|release_post\|mark_post_sent)\(' -- src ':!src/docket/reminders.py' ':!src/docket/store.py'` |
| Q9 | nothing in this phase runs the sender on a schedule or from a command | `git grep --untracked -n -E 'send_due\(' -- src ':!src/docket/reminders.py'` |
| Q10 | no timer, thread or event loop in this phase | `git grep --untracked -n -E 'time\.sleep\(\|asyncio\|threading' -- src` |

(In the table, `\|` is a `|` in the command.)

## 6. Reasonable variations

These are correct even though the spec does not spell them out:

- SQL function names in both SQL modules, a single grouping query or Python grouping, and an UPDATE ... RETURNING or an equivalent single-statement claim, as long as the given SQL-ownership test passes and the claim stays one statement in one transaction.
- Extra behaviour tests in tests/integration/test_reminder_sending_edges.py. Anything that sends from a command, sleeps, backs off, or renders a card is not a variation.
- Private helpers inside the Scope modules.

## 7. Verdict

Write `docs/reviews/phase-03c-claimed-reminder-sending.md` in the form `docs/phase-conventions.md` gives (`# Review: Phase 3c`), then run `.venv/bin/python scripts/check_reports.py --phase 3c`; it must print `Reports OK.`
