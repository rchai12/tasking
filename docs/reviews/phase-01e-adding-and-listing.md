# Review: Phase 1e

- Verdict: PASS
- Passed: 414
- Findings: 0
- Approved deviations: list and show open the store before the one clock read; a date and a time share one fullmatch shape check before fromisoformat
- For the architect: S11's deciding test adds a task with no deadline, so replacing created_at with clock.now() on the due line does not run and that test still passes

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none

The baseline is commit `78f5408`, which has the Corrections section and the corrected given test. `git ls-files --error-unmatch` found the spec, `tests/unit/test_views_tasks.py`, `tests/e2e/test_cli_tasks.py`, and `docs/verification/probe-01e.py`. `grep -c "^## Phase 1e: " docs/progress.md` printed `1`. The uncommitted diff before this report was `docs/progress.md` only. The commands and `tests/e2e/test_cli_tasks_more.py` are in `78f5408`.

G1 `.venv/bin/python -m pytest --no-cov -q --ignore=tests/e2e/test_cli_tasks.py --ignore=tests/unit/test_views_tasks.py`: `348 passed` (345 plus the 3 schema tests), 0 failed.

G2 `.venv/bin/python scripts/check.py --first core` ended with `All checks passed.` Summary: lint passed, format passed, `tests (core): passed`, tests passed, critical coverage passed. The tests step passed 414, 0 failed, 0 skipped, and printed no warnings summary.

```
Sections:
  core          355 passed    0 failed    0 skipped
Sections:
  tooling        59 passed    0 failed    0 skipped
  core          355 passed    0 failed    0 skipped
```

G4, run immediately after G2: exit 0, `TOTAL` 100% (`cli.py` 95 statements and 18 branches, `views.py` 72 statements and 28 branches, 0 missing).

G3: `66 passed`.

G5: `oracle: ok`, `1500 random adds answer exactly as the rules say: ok`, `list and show match the store in four zones: ok`. Last line: `FAILURES 0`.

G6: `1`.

G8: no output.

G9, before this report: `M docs/progress.md` only, a Scope path.

G10: the freeze list is unchanged (annotated-doc 0.0.6 through typing-inspection 0.4.5, including docket 0.1.0, typer 0.29.1, rich 15.0.0, ruff 0.17.5). No new dependency.

Q1 through Q7 printed nothing (`git grep` exit 1).

`tests/e2e/test_cli_tasks_more.py` asserts that add, list, and show each exit 1 with empty stdout and `unsupported schema version: 2` on stderr. There is no `tests/unit/test_views_tasks_more.py`. No coverage pragma.

Spot checks, each restored from `/tmp/phase01e-verify-copies` before the next. Hashes matched afterwards, `src/docket/__pycache__` was absent, and `git diff HEAD` for `cli.py` and `views.py` was empty.

- S1 failed: exit 0, `Added t1: Pay rent, due Fri Nov 20 17:00 EST, no time given`.
- S2 failed: exit 0, `Added t1: Pay rent, due Fri Nov 20 17:00 EST`.
- S3 failed: exit 0, `Added t1: Pay rent`.
- S4 failed: `AT_MESSAGE` instead of `DUE_MESSAGE`.
- S5 failed: 6 lines instead of 4.
- S6 failed: first line `t1    open                  Call the dentist`.
- S7 failed: `['t2', 't3', 't1']`.
- S8 failed: `docket.sqlite3` exists (`assert not True`).
- S9 failed: stdout `'There is no task t9.\n'`.
- S10 failed: exit 0.
- S11 passed. The one-line swap is inside `if deadline is not None`, and `test_listing_and_showing_read_the_clock_once` runs `tasks add One more` with no `--due`, so that line does not run and there is no second clock read. The broken empty stdout does not occur. `add` still reads no clock of its own; the due text still uses `task.created_at`. This is recorded for the architect, not as a finding.
- S12 failed: `'t12345in progress, overdue  Pay rent  due Thu Nov 12 17:00 EST'`.
- S13 failed: 8 lines, including `Link: None`.
- S14 failed: `'There is no such task.'`.
