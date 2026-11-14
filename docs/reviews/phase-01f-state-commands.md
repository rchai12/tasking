# Review: Phase 1f

- Verdict: PASS
- Passed: 466
- Findings: 0
- Approved deviations: start, done, cancel and reopen share one helper that checks the zone, opens the store, and calls change_state with actor owner
- For the architect: S6 cannot print "There is no task t1.": that test gives clock.now() no value, and change_state reads the clock before it looks the task up

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none

Coder ran: `grep -c "^## Phase 1f: " docs/progress.md` printed `1`. The first follow-up is `None`, not `Stopped:`. `git ls-files --error-unmatch` found the spec, `tests/unit/test_views_changes.py`, `tests/e2e/test_cli_states.py`, and `docs/verification/probe-01f.py`.

G1 `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_views_changes.py --ignore=tests/e2e/test_cli_states.py`: `414 passed`, 0 failed. There is no `*_more.py` for this phase.

G2 `.venv/bin/python scripts/check.py --first core` ended with `All checks passed.` Summary: lint passed, format passed, `tests (core): passed`, tests passed, critical coverage passed. The tests step passed 466, 0 failed, 0 skipped, and printed no warnings summary.

```
Sections:
  core          407 passed    0 failed    0 skipped
Sections:
  tooling        59 passed    0 failed    0 skipped
  core          407 passed    0 failed    0 skipped
```

G4, run immediately after G2: exit 0, `TOTAL` 100% (`cli.py` 115 statements and 18 branches, `views.py` 79 statements and 30 branches, 0 missing).

G3: `52 passed`.

G5: `oracle: ok`, `600 random state commands follow the table, sentences and audit: ok`. Last line: `FAILURES 0`.

G6: `1`.

G8: no output.

G9, before this report: `docs/progress.md`, `src/docket/cli.py`, and `src/docket/views.py`. Those are the Scope paths.

G10: the freeze list is unchanged (annotated-doc 0.0.6 through typing-inspection 0.4.5, including docket 0.1.0, typer 0.29.1, rich 15.0.0, ruff 0.17.5). No new dependency.

Q1 through Q8 printed nothing (`git grep` exit 1).

Spot checks, each restored from `/tmp/phase01f-verify-copies` before the next. Hashes matched afterwards (`cli.py` `366df74c8cae269a7bce07771c31497de5684bb8`, `views.py` `447d2ffff53fa16550fe2f934bd69c6f48ada6fe`), `src/docket/__pycache__` was absent, and `git diff HEAD` for those two files was the phase diff again.

- S1 failed: `'Done t3: Pay rent'`.
- S2 failed: `'t3 is already open.'`.
- S3 failed: last audit row `('start', 'agent')`.
- S4 failed: exit 1.
- S5 failed: `'That task has ended; reopen it first.'`.
- S6 failed differently, so this is a note, not a finding. Skipping `_home()` made the deciding test exit 1 with stdout `''` and stderr `''`, not `'There is no task t1.'`. The test calls `fixed_times` with no moment, and `change_state` reads the clock before it loads the task, so that read raises `StopIteration` before an unknown-task sentence can be printed.
- S7 failed: exit 1, `Result StopIteration()`.
- S8 failed: exit 1, stdout `''`.
- S9 failed: stdout `'There is no task t9.\n'`.
