# Review: Phase 1b

- Verdict: PASS
- Passed: 202
- Findings: 0
- Approved deviations: migration SQL is split with sqlite3.complete_statement; a task id is re.fullmatch of t plus a non-zero ASCII number
- For the architect: probe-01b.py prints a reached count line that does not end in ok; the check lines ended ok and FAILURES 0

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none

## Gate output

Coder ran: `src/docket/store.py` is present. `grep -c "^## Phase 1b: " docs/progress.md` printed `1`. `git ls-files --error-unmatch` found the spec, `src/docket/schema.py`, `tests/integration/test_store.py`, `scripts/critical_modules.txt`, and `docs/verification/probe-01b.py`.

G1 `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_store.py`: `152 passed`. There is no `tests/integration/test_store_more.py`.

G2 `.venv/bin/python scripts/check.py --first core` ended with `All checks passed.` Summary: lint passed, format passed, `tests (core): passed`, tests passed, critical coverage passed. The tests step passed 202, 0 failed, 0 skipped, and printed no warnings summary.

```
Sections:
  core          143 passed    0 failed    0 skipped
Sections:
  tooling        59 passed    0 failed    0 skipped
  core          143 passed    0 failed    0 skipped
```

G3: `50 passed`.

G4, run immediately after G2: exit 0, `TOTAL` 100% (`schema.py` 3 statements, `store.py` 193 statements and 46 branches, 0 missing).

G5: check lines ended in `ok`, including `oracle: ok`. Last line: `FAILURES 0`. The walk also printed `  reached {'insert': 156, 'update': 171, 'audit': 82, 'rolled-back': 156, 'restart': 35}` before its ok line.

G6: `1`.

G8: no output.

G9 before this report: `docs/progress.md` and `src/docket/store.py`. After this report, that set plus `docs/reviews/phase-01b-task-store.md`.

G10: the freeze list matches the packages present before this phase. No new dependency.

## Searches

Q1 through Q8 each printed nothing.

## Spot checks

Each deciding test failed with the guide's broken value. The module was copied outside the repository, restored from that copy, and `src/docket/__pycache__` was removed. `git status --short` and `git diff HEAD` matched the pre-check diff.

- S1: `task` returned the `Task` `t1`.
- S2: `OperationalError` was not raised.
- S3: `tasks()` was `[Task t1]`.
- S4: `StoreError` was not raised.
- S5: `found == []`. The broken run also emitted `PytestUnhandledThreadExceptionWarning` for the waiting thread, which the guide calls a note.
- S6: mode was `420` (`0o644`).
- S7: stored deadline text was `'2026-11-20T22:00:00+00:00'`.
- S8: stored audit JSON was `'{"state": "open"}'`.
- S9: the deadline and work time stayed as they were.
- S10: `StoreError` was not raised.
- S11: `StoreError` was not raised.
- S12: `tasks(set())` returned all four tasks.
- S13: `sqlite3.OperationalError` (`cannot start a transaction within a transaction`).
- S14: `sqlite3.OperationalError` (`unable to open database file`).
