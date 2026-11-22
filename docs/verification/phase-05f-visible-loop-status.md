# Verification guide: Phase 5f (Visible loop status)

Spec: `docs/phases/phase-05f-visible-loop-status.md`. Follow `docs/phase-conventions.md` ("For the verifier"). Never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor, never read the Keychain, and never open the real data folder.

## 1. Coder ran

Stop with FAIL ("the coder did not run") if any of these is missing:


- `grep -c "^## Phase 5f: " docs/progress.md` prints `1`

Stop with FAIL ("the coder stopped") if that entry's first `Follow-ups` line starts with `Stopped:`, as "A stopped coder" in `docs/phase-conventions.md` says. With no entry, `git status --short` tells "the coder did not run" (no Scope path changed) from "the coder broke off without reporting" (Scope paths changed; name them under `For the architect`).

Stop with FAIL ("the baseline is not committed") if `git ls-files --error-unmatch docs/phases/phase-05f-visible-loop-status.md src/docket/schema.py tests/integration/test_loop_status.py tests/e2e/test_cli_status.py tests/integration/test_reminder_loop.py tests/integration/test_audit_link_key_contracts.py tests/integration/test_reference_coverage.py tests/integration/test_reference_migration.py tests/integration/test_reminder_storage_edges.py tests/integration/test_server.py tests/integration/test_store.py tests/integration/test_store_links.py tests/integration/test_store_migrate.py tests/integration/test_store_safety_coverage.py tests/integration/ tests/integration/test_store_coordination.py docs/verification/probe-05f.py` fails: the diff gates can only be judged against a committed spec and given files. If the coder's work is already committed (a commit after the spec's, and a clean tree), judge every `git diff HEAD` gate against the spec's commit instead (`git log --diff-filter=A --format=%h -1 -- docs/phases/phase-05f-visible-loop-status.md`), and the `git status --short` gate with `git diff <that commit> --name-status`.

## 2. Gates

Run each from the repository root, in this order: `.venv/bin/python scripts/accept.py --phase 5f --guide` runs them and the searches, one line each. Given test count: 48.

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_loop_status.py --ignore=tests/e2e/test_cli_status.py` | at least 1946 passed, 0 failed (the coder's `*_more.py` tests add to the count) |
| G2 | `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1994 passed, 0 failed, 0 skipped |
| G3 | `.venv/bin/python -m pytest tests/integration/test_loop_status.py tests/e2e/test_cli_status.py --no-cov -q` | `48 passed` |
| G4 | `.venv/bin/python -m coverage report --include=src/docket/_store_loop.py,src/docket/store.py,src/docket/serialization.py,src/docket/reminders.py,src/docket/domain.py,src/docket/views.py,src/docket/cli.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| G5 | `.venv/bin/python docs/verification/probe-05f.py` | last line `FAILURES 0` |
| G6 | `grep -c "^## Phase 5f: " docs/progress.md` | `1` |
| G7 | `.venv/bin/python scripts/check_reports.py --phase 5f` | `Reports OK.` |
| G8 | `git diff HEAD --stat -- src/docket/schema.py docs/verification/probe-05f.py tests/integration/test_reminder_loop.py tests/integration/test_audit_link_key_contracts.py tests/integration/test_reference_coverage.py tests/integration/test_reference_migration.py tests/integration/test_reminder_storage_edges.py tests/integration/test_server.py tests/integration/test_store.py tests/integration/test_store_coordination.py tests/integration/test_store_links.py tests/integration/test_store_migrate.py tests/integration/test_store_safety_coverage.py tests/loop_cases.py tests/notifier_cases.py tests/support.py tests/conftest.py tests/sections.toml docs/reviews AGENTS.md pyproject.toml scripts/check.py scripts/tooling_modules.txt src/docket/core.py src/docket/notifier.py` | no output |
| G9 | `git diff HEAD --numstat -- tests/integration/test_loop_status.py tests/e2e/test_cli_status.py` | `0	14	tests/integration/test_loop_status.py` and `0	3	tests/e2e/test_cli_status.py` (the markers, nothing else) |
| G10 | `git status --short` | only the Scope paths |
| G11 | `.venv/bin/python -m pip list --format=freeze \| wc -l` | `52` (no package is added) |

## 3. Spot checks

For a module under `src/`, write the change as an exact old and new text in the module the coder wrote and run `.venv/bin/python scripts/spot_check.py <module> --old '<old>' --new '<new>' --test '<deciding test>' --row S<n>`; it restores the module and prints one line. For any other file:
1. Copy the module outside the repository.
2. Make the change described in the module the coder wrote.
3. Run the deciding test with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest '<test>' --no-cov -q --tb=line`, and confirm it fails with the "Broken" value; rerun with `-vv` only when it doesn't.
4. Restore the module from your copy, delete `src/docket/__pycache__`, and confirm `git diff` is as before.

A different failure from the "Broken" column is a note, not a finding; a pass is a finding.

| # | Module | Change | Deciding test | Correct | Broken |
|---|---|---|---|---|---|
| S1 | `reminders.py`, `next_status` | count only `failed` for the reminders half (drop the skip test) | `tests/integration/test_loop_status.py::test_next_status_counts_each_half[a-skip-fails-reminders]` | `reminders_failures=1` | `assert LoopStatus(pa...ipped=('t2',)) == LoopStatus(pa...ipped=('t2',))` |
| S2 | `reminders.py`, `next_status` | keep the previous digest count on a digest success instead of 0 | `tests/integration/test_loop_status.py::test_next_status_counts_each_half[ok-resets]` | `digest_failures=0` | `assert LoopStatus(pa...4, skipped=()) == LoopStatus(pa...0, skipped=())` |
| S3 | `reminders.py`, the recording | start each pass from no previous status (never read the row) | `tests/integration/test_loop_status.py::test_the_counts_carry_on_across_a_restart` | `digest_failures=3` after the restart | `assert LoopStatus(pa...1, skipped=()) == LoopStatus(pa...3, skipped=())` |
| S4 | `reminders.py`, the recording | catch only `StoreError` around the write | `tests/integration/test_loop_status.py::test_a_failed_status_write_never_stops_the_loop` | 3 passes, waits `[30, 30, 30]` | `tests.notifier_cases.SyntheticBug` |
| S5 | `reminders.py`, the recording | catch `BaseException` around the write | `tests/integration/test_loop_status.py::test_a_crash_while_recording_is_not_caught` | `Killed` raised | `Failed: DID NOT RAISE Killed` |
| S6 | `reminders.py`, the recording | treat only `KeyError` from the read as no row | `tests/integration/test_loop_status.py::test_a_bad_stored_status_starts_the_counts_again` | the counts start again | `docket.store.StoreError: invalid stored loop status` |
| S7 | `store.py`, `save_loop_status` | drop the check that `digest` is a `bool` | `tests/integration/test_loop_status.py::test_a_bad_status_is_refused_before_it_is_written[int-digest]` | `StoreError: invalid loop status` | `Failed: DID NOT RAISE StoreError` |
| S8 | `store.py`, `loop_status` | accept any string in the stored `skipped` | `tests/integration/test_loop_status.py::test_a_bad_stored_status_raises_a_constant_error[not-a-task-id]` | `StoreError: invalid stored loop status` | `Failed: DID NOT RAISE StoreError` |
| S9 | `views.py`, `loop_status_lines` | call exactly 5 minutes stale (`>` becomes `>=`) | `tests/integration/test_loop_status.py::test_loop_status_lines[five-minutes]` | `running` | `assert ['Reminder lo... 'Digest: ok'] == ['Reminder lo... 'Digest: ok']` |
| S10 | `views.py`, `loop_status_lines` | always write `passes`, even for 1 | `tests/integration/test_loop_status.py::test_loop_status_lines[failing]` | `failing for 1 pass` | `assert ['Reminder lo...asks: t2, t5'] == ['Reminder lo...asks: t2, t5']` |
| S11 | `cli.py`, `status` | print the no-pass line whatever is stored | `tests/e2e/test_cli_status.py::test_status_prints_the_stored_row[running]` | the stored row's four lines | `assert (0, 'Reminder...ed yet\n', '') == (0, 'Reminder...ks: t4\n', '')` |
| S12 | `reminders.py`, `run_loop` | run each pass without recording it | `tests/integration/test_loop_status.py::test_the_loop_records_each_pass_after_it_runs` | a row after each pass | `assert [None, None, None] == [LoopStatus(p..., skipped=())]` |

## 4. Probe

Run `.venv/bin/python docs/verification/probe-05f.py` from the repository root. It is a given file: do not edit it. Every line must end in `ok`; the last line must be `FAILURES 0`. A stop at the probe's own `assert` lines, before its self-check prints `ok`, is the probe's fault: report it under "For the architect", not as a finding. It touches no network, Keychain or real data folder.

The probe runs three seeded walks of 40 loop passes in four separate processes (three restarts), with random failures in each half, forced digest failures at passes 14 to 16, skipped tasks at passes 5 to 9 and 25 to 27, and the stored row corrupted before the third process. It checks that every notice, digest and row but `loop_status` matches the spec commit's code, that each pass's stored row equals the probe's own count of consecutive failures and the sends it saw, and that `docket status` run in another process prints the row as running 30 seconds later and not running 301 seconds later.

## 5. Searches

Each prints nothing. A match is a finding against the rule it names.

| # | Rule | Command |
|---|---|---|
| Q1 | no network code | `git grep --untracked -n -E 'import (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)\|from (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)' -- src` |
| Q2 | no output outside the CLI | `git grep --untracked -n -E 'print\(\|logging\|logger\|warnings\.warn' -- src ':!src/docket/cli.py'` |
| Q3 | time read only in clock.py, through the module | `git grep --untracked -n -E 'datetime\.now\|datetime\.utcnow\|date\.today\|time\.time\(\|from docket\.(clock\|ids) import' -- src ':!src/docket/clock.py'` |
| Q4 | no coverage or lint exclusions in this phase's modules | `git grep --untracked -n -E 'pragma: no cover\|noqa' -- src/docket/_store_loop.py src/docket/store.py src/docket/serialization.py src/docket/reminders.py src/docket/domain.py src/docket/views.py src/docket/cli.py` |
| Q5 | skipped is written by the one JSON writer | `git grep --untracked -n -E 'json\.dumps' -- src ':!src/docket/serialization.py'` |
| Q6 | the loop status is read and written only through the store, the loop, the view and the command | `git grep --untracked -n -E 'loop_status' -- src ':!src/docket/_store_loop.py' ':!src/docket/schema.py' ':!src/docket/store.py' ':!src/docket/reminders.py' ':!src/docket/views.py' ':!src/docket/cli.py'` |
| Q7 | the 5-minute bound lives only in domain.py | `git grep --untracked -n -E 'minutes=5\)\|LOOP_STALE_MINUTES = ' -- src ':!src/docket/domain.py'` |

(In the table, `\|` is a `|` in the command.)

## 6. Reasonable variations

These are correct even though the spec does not spell them out:

- Writing the row with `INSERT OR REPLACE` or an upsert, and decoding it through any private helper.
- Recording through any private helper in `reminders.py`, as long as the read and the write share one transaction and only `Exception` is dropped.
- Building `<health>` and the lines with any private helper in `views.py`; the lines are exact.
- Private helpers inside the Scope modules, and extra behaviour tests in `*_more.py` files.

## 7. Verdict

Write `docs/reviews/phase-05f-visible-loop-status.md` in the form `docs/phase-conventions.md` gives (`# Review: Phase 5f`), then run `.venv/bin/python scripts/check_reports.py --phase 5f`; it must print `Reports OK.`
