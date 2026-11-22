# Phase 5a: Shared store decoding

## Goal

Make every stored row the store reads go through one checked decoder, so a malformed audit, link or request-key row gives a constant `StoreError` naming its id, as tasks, reminders, posts and digests already do, and never a library's `ValueError` or `JSONDecodeError`. One private id parser and one private time decoder replace the five parsers and four time decoders in `store.py`, and `queue_post` and `queue_digest` share one retry-key check. A new database file is `0600` before SQLite opens it, leftover `-wal` and `-shm` files are made `0600`, and `.gitignore` covers the store's side files. This phase changes no public `Store` signature, no `core` behaviour, no schema and no migration, and moves no migration code (Phase 5b).

Sections: `core`. The `tooling` section runs in the full check.

Follow `docs/phase-conventions.md`. N is 1850, the tests the previous phase left passing.

Start: `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_store_decoding.py` must show `1850 passed`. The ignored file is this phase's new given test file.

## Facts

- `Store.audit` (`store.py:368`), `Store.request_key` (`store.py:439`) and `Store._link_from` (`store.py:657`) call `datetime.fromisoformat` and `json.loads` on stored text directly, so a malformed row raises the library's exception with its text, and a naive or non-UTC time is returned as it is. Every other reader already raises `StoreError("invalid stored <kind> time: <id>")` with no cause.
- `_number`, `_link_number`, `_reminder_number`, `_post_number` and `_digest_number` (`store.py:169-196`) differ only in their letter and regex; `_reminder_time`, `_post_time` and `_digest_time` are identical apart from their message, and `_task_from` decodes its two record times inline.
- `queue_post` and `queue_digest` each check `isinstance(key, str) and 1 <= len(key) <= domain.REQUEST_KEY_MAX`, refusing with `"invalid post key"` and `"invalid digest key"`.
- `datetime.fromisoformat` gives `tzinfo is UTC` for both `+00:00` and `Z`; stored times are TEXT in STRICT tables, so a decoder only ever sees a string or `NULL`. `json.loads` accepts `[]`, `null`, `7` and `"text"`, none of which is a dict.
- SQLite (3.54.1 here) creates a new database file with the process umask (`0644` under `022`) at `sqlite3.connect`, which `Store.__init__` narrows with `path.chmod(0o600)` afterwards. It creates new `-wal` and `-shm` files with the database file's mode, so those are already `0600`; a non-empty `-wal` or `-shm` left from a run before the database was `0600` keeps its old mode.
- Another process's last close deletes `-wal` and `-shm`, so a side file can vanish between any check and its `chmod`. A throwaway draft that tested `exists()` first failed `tests/integration/test_store_coordination.py::test_two_processes_initialize_the_same_database_once[v2]` in 2 of 8 runs.
- Every digest read selects its row by a day the store formatted from a Python `date`, or checks only that the row exists, so a stored day Python cannot parse (`0000-01-01` passes the table's CHECK) is never decoded: a check on it would be a branch no test can reach.
- `tests/integration/test_task_table_boundary.py::test_corrupt_task_refusals_stay_at_the_facade_without_repair` requires `__suppress_context__` on every stored-row refusal, so a refusal raised outside an `except` (a naive time, JSON that is not an object) still needs `from None`.
- A throwaway draft changed about 170 lines in `store.py` and `.gitignore` (73 added, 95 deleted); with it the full suite passed (1875) and covered `store.py` at 100%.

## Owner's decisions

- **File modes (2026-11-21):** create the database file with `os.open(..., 0o600)` before `sqlite3.connect`, and `chmod` any existing `-wal` and `-shm` to `0600` on open. No process-wide `os.umask`.
- **Migration move (2026-11-21):** moving the migrations and the reminder backfill to `_store_migrate.py` belongs to Phase 5b, the layout phase, not here.
- **Messages (2026-11-21):** one message per row type: `invalid stored audit entry: <task id>`, `invalid stored link: <link id>` and `invalid stored request key: <task id>`. The key row names its task, never the client-supplied key text.
- **Digest day (2026-11-21):** the owner chose to check a stored digest day too; the architect found it unreachable (Facts) and left it out, as recorded in `docs/decisions.md`.

## Architect's decisions

- A malformed row is one whose stored time is unparseable, naive or not UTC, or whose stored JSON is not valid JSON or not an object. Each is refused with its row type's message, as the given tests hold them.
- `links(task_id)` refuses with the id of the first bad link in id order, the order it returns links in.
- A database file that cannot be created (an `OSError` from `os.open`) is refused with the existing constant `StoreError("store startup unavailable")`, with no cause, before `sqlite3.connect` is called, and the startup gate is released as for any failed start.
- A side file that is missing when its `chmod` runs is not an error; any other `OSError` from that `chmod` is handled as the database file's `chmod` is today.
- The two helpers are private names of `store.py`; their exact signatures are the coder's, as long as each is one function used by every reader.

## Requirements

1. **One id parser.** A private `_row_number(prefix, value)` in `store.py` returns the row number of an id with that one-letter prefix (`t`, `l`, `r`, `p`, `d`) and a number from 1 with no leading zero, or `None` for anything else. It replaces `_number`, `_link_number`, `_reminder_number`, `_post_number` and `_digest_number` and their five regexes, with no change in what any public method accepts.
2. **One time decoder.** A private `_utc(value, label, identifier)` returns `None` for `None`, the UTC `datetime` for a stored UTC instant, and otherwise raises `StoreError(f"invalid stored {label}: {identifier}")` from `None` on every path. It replaces `_reminder_time`, `_post_time` and `_digest_time`, and `_task_from` decodes all four of its times (`deadline_at`, `work_start`, `created_at`, `updated_at`) through it, with the label `task time`. Every existing message stays word for word.
3. **Audit rows.** `Store.audit(task_id)` decodes `at` through `_utc` and `before` and `after` as JSON objects; any malformed field raises `StoreError("invalid stored audit entry: <task id>")` from `None`, with no library text. Requirements 4 and 5 raise the same way.
4. **Link rows.** Every `Link` the store returns decodes `created_at` through `_utc`; a malformed one raises `StoreError("invalid stored link: <link id>")`.
5. **Request-key rows.** `Store.request_key(client, key)` decodes `request` as a JSON object and `created_at` through `_utc`; a malformed one raises `StoreError("invalid stored request key: <task id>")`. A keyed `core` write over such a row raises that error and writes nothing.
6. **One retry-key check.** `queue_post` and `queue_digest` check their key through one private helper, keeping the messages `invalid post key` and `invalid digest key`.
7. **A private new database.** `Store.__init__` creates a missing database file with mode `0600` (`os.open` with `O_CREAT`) before it calls `sqlite3.connect`, after taking the startup gate; an `OSError` there is the Architect's decision's constant refusal. The existing `path.chmod(0o600)` stays for an existing wider file.
8. **Private side files.** On open, after the database file's `chmod`, an existing `<database>-wal` and `<database>-shm` are made `0600`; a missing one is skipped without a check-then-act race (Facts).
9. **`.gitignore`** gains the lines `*.sqlite3-wal`, `*.sqlite3-shm` and `*.startup.lock`, beside the existing service-state patterns.
10. **Given markers**: `tests/integration/test_store_decoding.py` carries 8 strict `xfail` markers with reasons starting `Phase 5a given test: remove this marker`, one line each. Delete all 8 once requirements 1 to 9 are done, and nothing else in the file. A strict marker on a passing test fails the run, so `check.py` tells you when.
11. **Progress entry** for `## Phase 5a: Shared store decoding (YYYY-MM-DD)` at the end of `docs/progress.md`.

## Given files

Already committed with this spec; never change them, except the markers of requirement 10.

| File | What it is |
|---|---|
| `tests/integration/test_store_decoding.py` | Malformed audit rows (three bad times, bad JSON in `before` and `after`, a list, null and a string), link rows (three bad times, second link named) and request-key rows (three bad times, bad JSON, a list, null and a number) refused with their constant message, no cause and nothing written; a keyed `core` create over a bad key row writes nothing; good rows (a `Z` time included) still decode; a new database `0600` before SQLite opens it under umask `022`; leftover non-empty `-wal` and `-shm` made `0600`; a side file that vanishes before its `chmod` is not an error; a database that cannot be created gives the constant startup error; the three `.gitignore` lines |
| `docs/verification/probe-05a.py` | The verifier's probe |

Given test count: **25** new (`test_store_decoding.py`: 10 functions, 25 tests). Before you start, the file shows 23 xfailed and 2 passed: `test_good_audit_link_and_key_rows_still_decode` and `test_a_side_file_that_vanishes_before_its_chmod_is_not_an_error` guard behaviour that must not change.

## Tests to write

None are required: the given tests and the existing store tests cover requirements 1 to 9 and every new line and branch of the draft. If you add a private helper with a branch they miss, cover it in a new `tests/integration/test_store_decoding_more.py`, never by changing a given test.

## Scope

| Path | Change |
|---|---|
| `src/docket/store.py` | edit: requirements 1 to 8 |
| `.gitignore` | edit: requirement 9 |
| `tests/integration/test_store_decoding.py` | delete the 8 markers only |
| `tests/integration/test_store_decoding_more.py` | create, only if you need it |
| `docs/progress.md` | append your entry |

## Out of scope

- Moving the migrations or the reminder backfill to `_store_migrate.py`, splitting `Store`, or changing `_store_tasks.insert_task` or `update_task` (Phase 5b).
- Checking a stored digest day (Facts).
- Any public `Store` signature, a schema change or migration, `core.py`, `intake.py`, `writes.py`, the `_store_*.py` modules, or another module.
- `os.umask`, or any change to the startup gate's lock file.
- Any change to a given file beyond the markers, `AGENTS.md` or the design docs.

## Rules that bite

- **Error messages are constant text plus identifiers**: a refusal names its row type and an id; no stored text, key, title or library message reaches it, and it carries no `__cause__`.
- **Nothing changes on a read**: a refused read writes nothing and repairs nothing.
- **Critical modules**: `store.py` is critical; every new line and branch is covered, with no `pragma: no cover`.
- **Every existing store test passes unchanged**, the two-process startup test included; run it more than once if you touch the side-file `chmod`.
- If you stop before finishing, still write the progress entry with a `Stopped:` first follow-up (`docs/phase-conventions.md`, "When you stop").
- Commands start with `.venv/bin/python`; no bare `python3`, `pytest` or `ruff`.

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_store_decoding.py` (before you start) | `1850 passed` |
| `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1875 passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest tests/integration/test_store_decoding.py --no-cov -q` | `25 passed` |
| `.venv/bin/python -m coverage report --include=src/docket/store.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| `.venv/bin/python docs/verification/probe-05a.py` | last line `FAILURES 0` |
| `grep -c "^## Phase 5a: " docs/progress.md` | `1` |
| `.venv/bin/python scripts/check_reports.py --phase 5a` | `Reports OK.` |
| `git diff HEAD --stat -- docs/verification/probe-05a.py tests/support.py tests/conftest.py tests/reference_cases.py tests/sections.toml docs/reviews AGENTS.md pyproject.toml scripts src/docket/core.py src/docket/schema.py` | no output |
| `git diff HEAD --numstat -- tests/integration/test_store_decoding.py` | `0	8	tests/integration/test_store_decoding.py` (the markers, nothing else) |
| `git status --short` | only the Scope paths |

### Searches

Each prints nothing.

```zsh
git grep --untracked -n -E 'import (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)|from (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)' -- src
git grep --untracked -n -E 'print\(|logging|logger|warnings\.warn' -- src ':!src/docket/cli.py'
git grep --untracked -n -E 'datetime\.now|datetime\.utcnow|date\.today|time\.time\(|from docket\.(clock|ids) import' -- src ':!src/docket/clock.py'
git grep --untracked -n -E 'pragma: no cover|noqa' -- src/docket/store.py
git grep --untracked -n -E '(datetime\.fromisoformat|json\.loads)\(row|def _(link|reminder|post|digest)_number|def _(reminder|post|digest)_time|re\.compile\(r"[tlrpd]\[' -- src/docket/store.py
git grep --untracked -n -E 'umask' -- src
```
