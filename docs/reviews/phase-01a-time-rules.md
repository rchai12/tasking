# Review: Phase 1a

- Verdict: PASS
- Passed: 152
- Findings: 0
- Approved deviations: zone names are cached with functools.cache; make_work_time uses WorkTime's length check, and the message order stays time, zone, length, midnight, deadline
- For the architect: None

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none

## Gate output

Coder ran: `src/docket/deadlines.py` is present. `grep -c "^## Phase 1a: " docs/progress.md` printed `1`. `git ls-files --error-unmatch` found the spec, `tests/unit/test_deadlines.py`, `scripts/critical_modules.txt`, and `docs/verification/probe-01a.py`.

G1 `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_deadlines.py`: `96 passed`. There is no `tests/unit/test_deadlines_more.py`.

G2 `.venv/bin/python scripts/check.py --first core` ended with `All checks passed.` Summary: lint passed, format passed, `tests (core): passed`, tests passed, critical coverage passed. The tests step passed 152, 0 failed, 0 skipped, and printed no warnings summary.

```
Sections:
  core           93 passed    0 failed    0 skipped
Sections:
  tooling        59 passed    0 failed    0 skipped
  core           93 passed    0 failed    0 skipped
```

G3: `56 passed`.

G4, run immediately after G2: exit 0, `src/docket/deadlines.py` `TOTAL` 100% (77 statements, 18 branches, 0 missing).

G5: every probe line ended in `ok`, including `oracle: ok`. Last line: `FAILURES 0`.

G6: `1`.

G8: no output.

G9 before this report: `docs/progress.md` and `src/docket/deadlines.py`. After this report, that set plus `docs/reviews/phase-01a-time-rules.md`.

G10: the freeze list matches the packages present before this phase. No new dependency.

## Searches

Q1 through Q6 each printed nothing.

## Spot checks

Each deciding test failed with the guide's broken value. The module was copied outside the repository, restored from that copy, and `src/docket/__pycache__` was removed. `git status --short` and `git diff HEAD` matched the pre-check diff.

- S1: `at` was 06:30 UTC.
- S2: `at` was 2026-11-21 04:59 UTC.
- S3: `time_given` was True.
- S4: `DeadlineError` was not raised.
- S5: status was `'due'`.
- S6: status was `'upcoming'`.
- S7: `DeadlineError` (`WORK_DAY_MESSAGE`).
- S8: a `WorkTime` was returned (its end is the start plus 720 minutes, 04:30 UTC).
- S9: a `WorkTime` was returned.
- S10: message was `WORK_DEADLINE_MESSAGE`.
- S11: `Deadline` raised no exception.
- S12: no exception.
- S13: no exception.
