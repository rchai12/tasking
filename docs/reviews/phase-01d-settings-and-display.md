# Review: Phase 1d

- Verdict: PASS
- Passed: 345
- Findings: 0
- Approved deviations: an empty time zone becomes None before the exact-name check; work_minutes uses Field bounds of 5 to 720 and get_settings maps that field's error to WORK_MINUTES_MESSAGE
- For the architect: None

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none

## Gate output

Coder ran: `src/docket/views.py` is present. `grep -c "^## Phase 1d: " docs/progress.md` printed `1`. `git ls-files --error-unmatch` found the spec, `tests/unit/test_settings.py`, `tests/unit/test_views.py`, and `docs/verification/probe-01d.py`.

G1 `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_settings.py --ignore=tests/unit/test_views.py`: `291 passed`. There is no `tests/unit/test_settings_more.py` or `tests/unit/test_views_more.py`.

G2 `.venv/bin/python scripts/check.py --first core` ended with `All checks passed.` Summary: lint passed, format passed, `tests (core): passed`, tests passed, critical coverage passed. The tests step passed 345, 0 failed, 0 skipped, and printed no warnings summary.

```
Sections:
  core          286 passed    0 failed    0 skipped
Sections:
  tooling        59 passed    0 failed    0 skipped
  core          286 passed    0 failed    0 skipped
```

G3: `54 passed`.

G4, run immediately after G2: exit 0, `TOTAL` 100% (`config.py` 57 statements and 12 branches, `views.py` 44 statements and 14 branches, 0 missing).

G5: every line ended in `ok`, including `oracle: ok`. Last line: `FAILURES 0`.

G6: `1`.

G8: no output.

G9 before this report: `docs/progress.md`, `src/docket/config.py`, and `src/docket/views.py`. After this report, that set plus `docs/reviews/phase-01d-settings-and-display.md`.

G10: the freeze list matches the packages present before this phase. No new dependency.

## Searches

Q1 through Q7 each printed nothing.

## Spot checks

Each deciding test failed with the guide's broken value. Both modules were copied outside the repository, restored from those copies, and `src/docket/__pycache__` was removed. `git status --short` and `git diff HEAD` matched the pre-check diff.

- S1: `'ven. nov. 20 17:00 EST'`.
- S2: `'Fri Jan 08 2027 17:00 EST'`.
- S3: `'Fri Jan 1 10:00 EST'`.
- S4: `'Thu Dec 31 2027 22:00 EST'`.
- S5: `'Fri Nov 20 17:00 EST'`.
- S6: `'Fri Nov 20 17:00 EST'`.
- S7: `'Fri Nov 20 14:00 EST to 15:00 EST'`.
- S8: `'Fri Nov 20 23:00 to 00:00 EST'`.
- S9: `'Sun Nov 1 00:30 to 02:30 EST'`.
- S10: `'done, overdue'`.
- S11: `ConfigError` (`TIME_ZONE_MESSAGE`).
- S12: `ConfigError` was not raised.
- S13: `'DOCKET_DATA_DIR must be an absolute path'`.
- S14: `ConfigError` was not raised.
- S15: `ConfigError` was not raised.
- S16: `WORK_MINUTES_MESSAGE`.
