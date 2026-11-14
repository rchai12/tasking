# Review: Phase 1c

- Verdict: PASS
- Passed: 291
- Findings: 0
- Approved deviations: an email reference checks the message id and link before the provider, still as one invalid_reference; a non-email reference is refused unless provider, message id and link are all None
- For the architect: None

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none

## Gate output

Coder ran: `src/docket/core.py` is present. `grep -c "^## Phase 1c: " docs/progress.md` printed `1`. `git ls-files --error-unmatch` found the spec, `tests/integration/test_core.py`, `scripts/critical_modules.txt`, and `docs/verification/probe-01c.py`.

G1 `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_core.py`: `202 passed`. There is no `tests/integration/test_core_more.py`.

G2 `.venv/bin/python scripts/check.py --first core` ended with `All checks passed.` Summary: lint passed, format passed, `tests (core): passed`, tests passed, critical coverage passed. The tests step passed 291, 0 failed, 0 skipped, and printed no warnings summary.

```
Sections:
  core          232 passed    0 failed    0 skipped
Sections:
  tooling        59 passed    0 failed    0 skipped
  core          232 passed    0 failed    0 skipped
```

G3: `89 passed`.

G4, run immediately after G2: exit 0, `src/docket/core.py` `TOTAL` 100% (133 statements, 64 branches, 0 missing).

G5: every line ended in `ok`, including `oracle: ok`. Last line: `FAILURES 0`.

G6: `1`.

G8: no output.

G9 before this report: `docs/progress.md` and `src/docket/core.py`. After this report, that set plus `docs/reviews/phase-01c-task-rules.md`.

G10: the freeze list matches the packages present before this phase. No new dependency.

## Searches

Q1 through Q7 each printed nothing.

## Spot checks

Each deciding test failed. The module was copied outside the repository, restored from that copy, and `src/docket/__pycache__` was removed. `git status --short` and `git diff HEAD` matched the pre-check diff.

- S1: `CoreError` was not raised. The test stops in `refused` before it reads the state, so it does not print `in_progress`. Note, not a finding.
- S2: `changed` was True.
- S3: `CoreError` was not raised. Same note as S1: the test does not print the resulting state `done`.
- S4: `sqlite3.IntegrityError` from the actor CHECK.
- S5: `CoreError` was not raised.
- S6: `CoreError` was not raised.
- S7: `CoreError` was not raised. The test stops before it can show that the edit was stored. Note, not a finding.
- S8: audit rows were `retitle`, `deadline`, and `work_time`.
- S9: `CoreError` was not raised. The no-change return is what `refused` reports as no exception. Note, not a finding.
- S10: `StopIteration`.
- S11: the edit raised `CoreError` (`task_ended`).
- S12: `StopIteration`.
- S13: the deadline instant was `'2026-11-20T22:00:00+00:00'`.
- S14: audit actions were `retitle`, `work_time`, `deadline`.
