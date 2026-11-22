# Phase 5b: Store migrations and task columns

## Goal

Move the store's migrations and the reminder backfill out of `Store` into a new private module, `src/docket/_store_migrate.py`, which `Store.__init__` calls once per open, and make the tasks SQL safe to change: `_store_tasks.insert_task` takes each column by name instead of a positional 14-tuple, and `_store_tasks.update_task` writes only the columns of one fixed allow-list, refusing any other. Every database upgrades to exactly the rows it did before, every task write lands in the same columns, and no public `Store` signature, `core` behaviour, schema or migration changes. Splitting the rest of `Store` into per-aggregate parts is Phase 5c and 5d.

Sections: `core`. The `tooling` section runs in the full check.

Follow `docs/phase-conventions.md`. N is 1876, the tests the previous phase left passing.

Start: `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_store_migrate.py` must show `1876 passed`. The ignored file is this phase's new given test file.

## Facts

- `Store._migrate` (`store.py:462`) is the only caller of `_apply_migration`, `_user_version`, `_migrate_references`, `_refuse_invalid_references`, `_refuse_reference` and `_backfill_reminders` (`store.py:515-578`); `Store.__init__` calls `self._migrate()` once, after the connection's pragmas. No test names any of the seven.
- The migration steps use `self._connection`, `self.transaction()`, `self._task_from` and `self._write_reminders`, and the module names `StoreError`, `SCHEMA_MESSAGE`, `_statements`, `MIGRATIONS`, `SCHEMA_VERSION`, `domain`, `valid_reference`, `MESSAGE_ID_MAX` and `LINK_MAX`. `_backfill_reminders` imports `docket.reminders` inside the function, because `reminders` imports `store`; that stays until Phase 5e.
- `tests/integration/test_reference_migration.py::test_failed_migration_rolls_back_closes_and_restores_foreign_keys` replaces `docket.store.MIGRATIONS` with `monkeypatch.setattr`, so the moved code must read `MIGRATIONS` from `docket.store` when it runs, not bind it at import. A throwaway draft that imported it from `docket.schema` failed that test.
- `docket.store` importing `docket._store_migrate`, which imports `docket.store` as a module (`from docket import store`), works in either import order: a spike showed `from package import module` returns the half-imported module, and attributes read inside functions are found at call time.
- `tests/integration/test_task_sql_contracts.py::test_legacy_upgrade_does_not_call_task_helpers` replaces every `_store_tasks` function with a fake that fails during a version 2 upgrade, so no migration step may call `_store_tasks`; the backfill keeps its own `SELECT`.
- `_store_tasks.update_task` today has eight `if "<column>" in fields:` blocks and silently ignores any other key while still setting `updated_at`.
- `tests/integration/test_task_sql_contracts.py::test_a_helper_failure_before_sql_leaves_every_table_unchanged` replaced `_store_tasks.insert_task` with a fake of two positional parameters; the spec commit changes that fake to `(*_args, **_kwargs)` (a given edit), which passes before and after this phase.
- Product critical coverage reads `scripts/critical_modules.txt`; a module missing from it is not held to 100%.
- A throwaway draft changed about 290 lines (`store.py` 18 added and 100 deleted, `_store_tasks.py` 52 and 26, a new 93-line `_store_migrate.py`); with it the full suite passed (1895, this phase's given tests included) and every `docket` module was covered at 100% with branches.

## Owner's decisions

- **Split (2026-11-21):** the roadmap's per-aggregate split is three phases: 5b (this one: migrations out, named task columns, the update allow-list), 5c and 5d (the per-aggregate parts). Import direction becomes 5e and visible reminder passes 5f.

## Architect's decisions

- The module's one public name is `migrate(store: Store) -> None`; it does what `Store._migrate` does today, step for step, with the same messages and the same transactions (each through `store.transaction()`, the reference rebuild with `PRAGMA foreign_keys` off and restored as today).
- The moved helpers are private module functions of `_store_migrate.py` that take the store; their names and signatures are the coder's. They use the store's private connection and its `_task_from` and `_write_reminders`, as the store parts do; no new public `Store` name.
- An unknown column given to `_store_tasks.update_task` raises `ValueError("unknown task column")` before any SQL runs. `_store_tasks` imports nothing from `docket` (an existing boundary test), so it cannot raise `StoreError`; `Store.update_task` only ever passes allowed names, so no caller sees the error.
- `insert_task` binds its values as named SQL parameters (`:title`), so a column and its value are written side by side; `update_task` keeps its signature `(connection, number, updated_at, fields)`.

## Requirements

1. **Migration module.** A new `src/docket/_store_migrate.py` defines `migrate(store)`, holding the seven steps that leave `Store`: `_migrate`, `_apply_migration`, `_user_version`, `_migrate_references`, `_refuse_invalid_references`, `_refuse_reference` and `_backfill_reminders`. `Store` keeps none of these names.
2. **Called through the module.** `Store.__init__` calls `_store_migrate.migrate(self)` (module attribute, read at call time) once per open, where it calls `self._migrate()` today; nothing else in `store.py` migrates.
3. **Same upgrades.** Every database at schema version 0 to 5 upgrades to version 6 with exactly the rows the code at the spec commit writes, the version 3 backfill included, and a newer version is refused with the existing `unsupported schema version: <n>` message. `MIGRATIONS` and `SCHEMA_VERSION` stay names of `docket.store`, and the migration code reads them from it when it runs (Facts).
4. **No connection of its own.** `_store_migrate.py` opens, closes, commits and rolls back no connection itself (`store.transaction()` does), reads no clock, and never names `_store_tasks`.
5. **Named insert columns.** `_store_tasks.insert_task(connection, *, title, state, deadline_at, deadline_zone, deadline_time_given, work_start, work_minutes, work_zone, source, provider, message_id, link, created_at, updated_at)` takes every column as a keyword-only argument, in that order, and binds each as a named parameter. A positional tuple is a `TypeError`. `Store.insert_task` passes them by name.
6. **Update allow-list.** `_store_tasks.update_task` sets `updated_at` and then each of `title`, `state`, `deadline_at`, `deadline_zone`, `deadline_time_given`, `work_start`, `work_minutes` and `work_zone` that `fields` holds, by looping over that one fixed tuple. Any other key raises the Architect's decision's `ValueError` before any SQL.
7. **Nothing public moves.** No public `Store` method's signature, record or message changes, `core.py` and `schema.py` are unchanged, and every existing test passes unchanged.
8. **Critical module.** `scripts/critical_modules.txt` gains the line `_store_migrate.py`, directly after `_store_digests.py`.
9. **Given markers**: `tests/integration/test_store_migrate.py` carries 9 strict `xfail` markers with reasons starting `Phase 5b given test: remove this marker`, one line each. Delete all 9 once requirements 1 to 8 are done, and nothing else in the file. A strict marker on a passing test fails the run, so `check.py` tells you when.
10. **Progress entry** for `## Phase 5b: Store migrations and task columns (YYYY-MM-DD)` at the end of `docs/progress.md`.

## Given files

Already committed with this spec; never change them, except the markers of requirement 9.

| File | What it is |
|---|---|
| `tests/integration/test_store_migrate.py` | `insert_task`'s keyword-only signature; a positional tuple refused with nothing written; fourteen distinct values each in its own column; a task written through `Store.insert_task` with a deadline zone and a work zone that differ lands column for column; every allowed update column written; `source`, `number` and `updated_at` refused as update columns before any write; none of the seven steps left on `Store`; `migrate` called once per open through the module; a store whose `migrate` is replaced does not migrate at all; `migrate` on a current store changes nothing; the module's source calls no `connect`, `close`, `commit`, `rollback`, `executescript` or `now` and never names `_store_tasks` |
| `tests/integration/test_task_sql_contracts.py` | given edit: the injected `insert_task` fake takes `(*_args, **_kwargs)` |
| `docs/verification/probe-05b.py` | The verifier's probe |

Given test count: **19** new (`test_store_migrate.py`: 11 functions, 19 tests). Before you start, the file shows 17 xfailed and 2 passed: `test_the_store_writes_each_task_field_to_its_own_column` and `test_every_allowed_update_column_is_written` guard behaviour that must not change.

## Tests to write

None are required: the given tests, the existing store, migration and reference tests, and the probe cover requirements 1 to 8 and every line and branch of the draft. If a private helper you add has a branch they miss, cover it in a new `tests/integration/test_store_migrate_more.py`, never by changing a given test.

## Scope

| Path | Change |
|---|---|
| `src/docket/_store_migrate.py` | create: requirements 1, 3 and 4 |
| `src/docket/store.py` | edit: requirements 1, 2, 3 and 5 |
| `src/docket/_store_tasks.py` | edit: requirements 5 and 6 |
| `scripts/critical_modules.txt` | edit: requirement 8 |
| `tests/integration/test_store_migrate.py` | delete the 9 markers only |
| `tests/integration/test_store_migrate_more.py` | create, only if you need it |
| `docs/progress.md` | append your entry |

## Out of scope

- Splitting `Store`'s other methods into per-aggregate parts (Phases 5c and 5d), or moving the backfill's `reminders` import to the top of a module (Phase 5e).
- Any public `Store` signature, a schema change or migration, `core.py`, `schema.py`, `reminders.py`, the other `_store_*.py` modules, or another module.
- A new error class, or catching the allow-list's `ValueError` in `Store`.
- Any change to a given file beyond the markers, `AGENTS.md` or the design docs.

## Rules that bite

- **Every change to a task goes through `docket.core`**: this phase moves code under `Store` and changes no path a write takes.
- **Error messages are constant text plus identifiers**: the moved refusals keep their exact text; the allow-list's error names no key.
- **Critical modules**: `store.py`, `_store_tasks.py` and the new `_store_migrate.py` are critical; every line and branch is covered, with no `pragma: no cover`.
- **Every existing test passes unchanged**, the two-process startup and legacy-upgrade tests included.
- If you stop before finishing, still write the progress entry with a `Stopped:` first follow-up (`docs/phase-conventions.md`, "When you stop").
- Commands start with `.venv/bin/python`; no bare `python3`, `pytest` or `ruff`.

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_store_migrate.py` (before you start) | `1876 passed` |
| `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1895 passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest tests/integration/test_store_migrate.py --no-cov -q` | `19 passed` |
| `.venv/bin/python -m coverage report --include=src/docket/store.py,src/docket/_store_migrate.py,src/docket/_store_tasks.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| `.venv/bin/python docs/verification/probe-05b.py` | last line `FAILURES 0` |
| `grep -c "^## Phase 5b: " docs/progress.md` | `1` |
| `.venv/bin/python scripts/check_reports.py --phase 5b` | `Reports OK.` |
| `git diff HEAD --stat -- docs/verification/probe-05b.py tests/integration/test_task_sql_contracts.py tests/support.py tests/conftest.py tests/reference_cases.py tests/startup_cases.py tests/sections.toml docs/reviews AGENTS.md pyproject.toml scripts/check.py scripts/tooling_modules.txt src/docket/core.py src/docket/schema.py src/docket/reminders.py` | no output |
| `git diff HEAD --numstat -- tests/integration/test_store_migrate.py` | `0	9	tests/integration/test_store_migrate.py` (the markers, nothing else) |
| `git diff HEAD --numstat -- scripts/critical_modules.txt` | `1	0	scripts/critical_modules.txt` |
| `git status --short` | only the Scope paths |

### Searches

Each prints nothing.

```zsh
git grep --untracked -n -E 'import (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)|from (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)' -- src
git grep --untracked -n -E 'print\(|logging|logger|warnings\.warn' -- src ':!src/docket/cli.py'
git grep --untracked -n -E 'datetime\.now|datetime\.utcnow|date\.today|time\.time\(|from docket\.(clock|ids) import' -- src ':!src/docket/clock.py'
git grep --untracked -n -E 'pragma: no cover|noqa' -- src/docket/store.py src/docket/_store_migrate.py src/docket/_store_tasks.py
git grep --untracked -n -E 'def (_migrate|_apply_migration|_user_version|_migrate_references|_refuse_invalid_references|_refuse_reference|_backfill_reminders)\(' -- src/docket/store.py
git grep --untracked -n -E '"[a-z_]+" in fields|VALUES \(\?' -- src/docket/_store_tasks.py
git grep --untracked -n -E '_store_tasks|from docket\.schema import' -- src/docket/_store_migrate.py
```
