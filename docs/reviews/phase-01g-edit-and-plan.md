# Review: Phase 1g

- Verdict: PASS
- Passed: 522
- Findings: 0
- Approved deviations: edit and plan share one helper that opens the store and calls edit_task with actor owner; a length refusal and a midnight refusal are told apart by DeadlineError's text
- For the architect: None

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none

The baseline is commit `22fdbc3`. `git ls-files --error-unmatch` found the spec, `tests/unit/test_views_edits.py`, `tests/e2e/test_cli_edits.py`, and `docs/verification/probe-01g.py`. `git diff 22fdbc3` for those given files is empty. `grep -c "^## Phase 1g: " docs/progress.md` printed `1`. The first follow-up is `None`, not `Stopped:`.

G1 `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_views_edits.py --ignore=tests/e2e/test_cli_edits.py`: `466 passed`, 0 failed. There is no `*_more.py` for this phase.

G2 `.venv/bin/python scripts/check.py --first core` ended with `All checks passed.` Summary: lint passed, format passed, `tests (core): passed`, tests passed, critical coverage passed. The tests step passed 522, 0 failed, 0 skipped, and printed no warnings summary.

```
Sections:
  core          463 passed    0 failed    0 skipped
Sections:
  tooling        59 passed    0 failed    0 skipped
  core          463 passed    0 failed    0 skipped
```

G4, run immediately after G2: exit 0, `TOTAL` 100% (`cli.py` 167 statements and 36 branches, `views.py` 94 statements and 38 branches, 0 missing).

G3: `56 passed`.

G5: `oracle: ok`, `900 random edits and plans follow the order of checks and the model: ok`. Last line: `FAILURES 0`.

G6: `1`.

G8: no output against `HEAD` and against `22fdbc3`.

G9, before this report replaced the earlier stop review: `docs/progress.md`, `src/docket/cli.py`, and `src/docket/views.py`, the Scope paths. The untracked review file is this report.

G10: the freeze list is unchanged (annotated-doc 0.0.6 through typing-inspection 0.4.5, including docket 0.1.0, typer 0.29.1, rich 15.0.0, ruff 0.17.5). No new dependency.

Q1 through Q8 printed nothing (`git grep` exit 1).

Spot checks, each restored from `/tmp/phase01g-verify-copies` before the next. Hashes matched afterwards (`cli.py` `2433907c35660c372d0c13aba3021c53b2c607d6`, `views.py` `b5022822aa56a13fabe7898427f06bcb9c7eba3a`), `src/docket/__pycache__` was absent, and `git diff HEAD` for those two files was the phase diff again.

- S1 failed: `'Updated t3: Pay rent'`.
- S2 failed: `'Planned t3: Sun Mar 14 2027 03:30 to 04:30 EDT'`.
- S3 failed: `'Give --title, --due or --no-due.'`.
- S4 failed: exit 0, `'Updated t1: Pay rent, no deadline'`.
- S5 failed: exit 0, `'Nothing changed for t1.'`.
- S6 failed: exit 0, `'Planned t1: Fri Nov 20 23:30 EST to Sat Nov 21 00:30 EST'`.
- S7 failed: `'... 14:00 to 15:00 EST'`.
- S8 failed: exit 1, `Result StopIteration()`.
- S9 failed: `PLAN_TIME_MESSAGE` instead of `PLAN_DATE_MESSAGE`.
- S10 failed: last audit row `('retitle', 'agent')`.
- S11 failed: `MIDNIGHT_MESSAGE` instead of `MINUTES_MESSAGE`.
- S12 failed: `'That task has ended; reopen it first.'`.
