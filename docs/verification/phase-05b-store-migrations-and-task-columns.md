# Verification guide: Phase 5b (Store migrations and task columns)

Spec: `docs/phases/phase-05b-store-migrations-and-task-columns.md`. Follow `docs/phase-conventions.md` ("For the verifier"). Never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor, never read the Keychain, and never open the real data folder.

## 1. Coder ran

Stop with FAIL ("the coder did not run") if any of these is missing:


- `grep -c "^## Phase 5b: " docs/progress.md` prints `1`

Stop with FAIL ("the coder stopped") if that entry's first `Follow-ups` line starts with `Stopped:`, as "A stopped coder" in `docs/phase-conventions.md` says. With no entry, `git status --short` tells "the coder did not run" (no Scope path changed) from "the coder broke off without reporting" (Scope paths changed; name them under `For the architect`).

Stop with FAIL ("the baseline is not committed") if `git ls-files --error-unmatch docs/phases/phase-05b-store-migrations-and-task-columns.md tests/integration/test_store_migrate.py tests/integration/test_task_sql_contracts.py docs/verification/probe-05b.py` fails: the diff gates can only be judged against a committed spec and given files. If the coder's work is already committed (a commit after the spec's, and a clean tree), judge every `git diff HEAD` gate against the spec's commit instead (`git log --diff-filter=A --format=%h -1 -- docs/phases/phase-05b-store-migrations-and-task-columns.md`), and the `git status --short` gate with `git diff <that commit> --name-status`.

## 2. Gates

Run each from the repository root, in this order: `.venv/bin/python scripts/accept.py --phase 5b --guide` runs them and the searches, one line each. Given test count: 19.

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_store_migrate.py` | at least 1876 passed, 0 failed (the coder's `*_more.py` tests add to the count) |
| G2 | `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1895 passed, 0 failed, 0 skipped |
| G3 | `.venv/bin/python -m pytest tests/integration/test_store_migrate.py --no-cov -q` | `19 passed` |
| G4 | `.venv/bin/python -m coverage report --include=src/docket/store.py,src/docket/_store_migrate.py,src/docket/_store_tasks.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| G5 | `.venv/bin/python docs/verification/probe-05b.py` | last line `FAILURES 0` |
| G6 | `grep -c "^## Phase 5b: " docs/progress.md` | `1` |
| G7 | `.venv/bin/python scripts/check_reports.py --phase 5b` | `Reports OK.` |
| G8 | `git diff HEAD --stat -- docs/verification/probe-05b.py tests/integration/test_task_sql_contracts.py tests/support.py tests/conftest.py tests/reference_cases.py tests/startup_cases.py tests/sections.toml docs/reviews AGENTS.md pyproject.toml scripts/check.py scripts/tooling_modules.txt src/docket/core.py src/docket/schema.py src/docket/reminders.py` | no output |
| G9 | `git diff HEAD --numstat -- tests/integration/test_store_migrate.py` | `0	9	tests/integration/test_store_migrate.py` (the markers, nothing else) |
| G10 | `git diff HEAD --numstat -- scripts/critical_modules.txt` | `1	0	scripts/critical_modules.txt` |
| G11 | `git status --short` | only the Scope paths |
| G12 | `.venv/bin/python -m pip list --format=freeze \| wc -l` | `52` (no package added) |

## 3. Spot checks

For a module under `src/`, write the change as an exact old and new text in the module the coder wrote and run `.venv/bin/python scripts/spot_check.py <module> --old '<old>' --new '<new>' --test '<deciding test>' --row S<n>`; it restores the module and prints one line. For any other file:
1. Copy the module outside the repository.
2. Make the change described in the module the coder wrote.
3. Run the deciding test with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest '<test>' --no-cov -q --tb=line`, and confirm it fails with the "Broken" value; rerun with `-vv` only when it doesn't.
4. Restore the module from your copy, delete `src/docket/__pycache__`, and confirm `git diff` is as before.

A different failure from the "Broken" column is a note, not a finding; a pass is a finding.

| # | Module | Change | Deciding test | Correct | Broken |
|---|---|---|---|---|---|
| S1 | `_store_tasks.py`, `update_task` | drop the unknown-column refusal (let any key through) | `tests/integration/test_store_migrate.py::test_an_unknown_update_column_is_refused_before_any_write[source]` | `unknown task column` | `DID NOT RAISE ValueError` |
| S2 | `store.py`, `Store.__init__` | call `_store_migrate.migrate(self)` twice | `tests/integration/test_store_migrate.py::test_each_open_migrates_once_through_the_module` | one call per open | `assert [<docket.stor... 0x...>] == [<docket.stor... 0x...>]` |
| S3 | `_store_migrate.py`, the version 2 rebuild | read `MIGRATIONS` from `docket.schema` instead of `docket.store` | `tests/integration/test_reference_migration.py::test_failed_migration_rolls_back_closes_and_restores_foreign_keys` | `sqlite3.OperationalError` from the patched script | `IndexError: tuple index out of range` |
| S4 | `_store_migrate.py`, the version 3 step | skip the reminder backfill (compare the version with 99) | `tests/integration/test_durable_reminders.py::test_upgrade_backfills_active_tasks_once_using_stored_updated_at` | ten rows for t1 | `assert [] == [['start', '2...+00:00'], ...]` |
| S5 | `store.py`, `Store.insert_task` | pass `work_zone` as `deadline_zone` | `tests/integration/test_store_migrate.py::test_the_store_writes_each_task_field_to_its_own_column` | `America/New_York` in column 4 | `assert [(1, 'Synthet...don', 1, ...)] == [(1, 'Synthet...ork', 1, ...)]` |
| S6 | `_store_tasks.py`, the allow-list | drop `work_zone` from it | `tests/integration/test_store_migrate.py::test_every_allowed_update_column_is_written` | the row with `Europe/London` | `ValueError: unknown task column` |
| S7 | `_store_tasks.py`, `update_task` | name the refused key in the message | `tests/integration/test_store_migrate.py::test_an_unknown_update_column_is_refused_before_any_write[number]` | `unknown task column` | `assert 'unknown task column number' == 'unknown task column'` |
| S8 | `_store_tasks.py`, `insert_task` | bind `work_zone`'s value to the `deadline_zone` parameter | `tests/integration/test_store_migrate.py::test_each_named_column_lands_in_its_own_column` | `America/New_York` in column 4 | `assert (2, 'Syntheti...ndon', 1, ...) == (2, 'Syntheti...York', 1, ...)` |

## 4. Probe

Run `.venv/bin/python docs/verification/probe-05b.py` from the repository root. It is a given file: do not edit it. Every line must end in `ok`; the last line must be `FAILURES 0`. A stop at the probe's own `assert` lines, before its self-check prints `ok`, is the probe's fault: report it under "For the architect", not as a finding. It touches no network, Keychain or real data folder.

It extracts `src` from the spec commit with `git archive` and runs it and the current code side by side in child processes. It upgrades a version 1 and a version 2 database, each with four extra deadlines either side of the 2026-11-01 New York change, and checks that both trees leave the same dump (reminders backfilled included) and that a reopen changes nothing; it runs three seeded walks (seeds 11, 23, 37) of inserts and updates through the public `Store` methods in both trees and compares the dumps; last it checks that `Store` keeps none of the seven steps and that `update_task` refuses `source`, `created_at`, `updated_at`, `number` and `link` with nothing written. It needs the spec commit in the history: run it from a checkout that has that commit.

## 5. Searches

Each prints nothing. A match is a finding against the rule it names.

| # | Rule | Command |
|---|---|---|
| Q1 | no network code | `git grep --untracked -n -E 'import (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)\|from (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)' -- src` |
| Q2 | no output outside the CLI | `git grep --untracked -n -E 'print\(\|logging\|logger\|warnings\.warn' -- src ':!src/docket/cli.py'` |
| Q3 | time read only in clock.py, through the module | `git grep --untracked -n -E 'datetime\.now\|datetime\.utcnow\|date\.today\|time\.time\(\|from docket\.(clock\|ids) import' -- src ':!src/docket/clock.py'` |
| Q4 | no coverage or lint exclusions in this phase's modules | `git grep --untracked -n -E 'pragma: no cover\|noqa' -- src/docket/store.py src/docket/_store_migrate.py src/docket/_store_tasks.py` |
| Q5 | the seven migration steps are gone from store.py | `git grep --untracked -n -E 'def (_migrate\|_apply_migration\|_user_version\|_migrate_references\|_refuse_invalid_references\|_refuse_reference\|_backfill_reminders)\(' -- src/docket/store.py` |
| Q6 | the update loops over one allow-list, and the insert binds named parameters, not question-mark positions | `git grep --untracked -n -E '"[a-z_]+" in fields\|VALUES \(\?' -- src/docket/_store_tasks.py` |
| Q7 | migrations never call the tasks SQL, and read MIGRATIONS and SCHEMA_VERSION from docket.store at run time | `git grep --untracked -n -E '_store_tasks\|from docket\.schema import' -- src/docket/_store_migrate.py` |

(In the table, `\|` is a `|` in the command.)

## 6. Reasonable variations

These are correct even though the spec does not spell them out:

- The moved helpers' names, signatures and order, whether `migrate` takes the store positionally or by keyword, and whether `_store_migrate` imports `docket.store` at the top or inside its functions, as long as `MIGRATIONS` is read when the migration runs.
- The allow-list as a module tuple or a frozen set beside an ordered tuple, and whether the unknown-key check runs before or while the assignments are built, as long as it raises before any SQL.
- `insert_task` building its parameter dict from its arguments, or the SQL text written out in full, as long as every value is a named parameter.
- `MIGRATIONS` and `SCHEMA_VERSION` kept in `store.py` with an explicit re-export (`import X as X`) or used there, so that `ruff` keeps them.
- Private helpers inside the Scope modules, and extra behaviour tests in `*_more.py` files.

## 7. Verdict

Write `docs/reviews/phase-05b-store-migrations-and-task-columns.md` in the form `docs/phase-conventions.md` gives (`# Review: Phase 5b`), then run `.venv/bin/python scripts/check_reports.py --phase 5b`; it must print `Reports OK.`
