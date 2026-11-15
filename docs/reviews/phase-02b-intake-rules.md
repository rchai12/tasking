# Review: Phase 2b

- Verdict: PASS
- Passed: 634
- Findings: 0
- Approved deviations: accept_task and accept_link share the key check and the map from a core code to a status
- For the architect: S3 raises _BadDeadline rather than TypeError, because _text refuses a non-string before the core compares the provider

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none

The baseline is commit `258e449`. `git ls-files --error-unmatch` found the spec, `tests/integration/test_intake.py`, `scripts/critical_modules.txt`, and `docs/verification/probe-02b.py`. `git diff HEAD` for those given files is empty. `grep -c "^## Phase 2b: " docs/progress.md` printed `1`. The first follow-up is `None`, not `Stopped:`. This report replaces the earlier fail review from the run where the coder had not started.

G1 `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_intake.py`: `579 passed`, 0 failed. There is no `*_more.py` for this phase.

G2 `.venv/bin/python scripts/check.py --first core` ended with `All checks passed.` Summary: lint passed, format passed, `tests (core): passed`, tests passed, critical coverage passed. The tests step passed 634, 0 failed, 0 skipped, and printed no warnings summary.

```
Sections:
  core          575 passed    0 failed    0 skipped
Sections:
  tooling        59 passed    0 failed    0 skipped
  core          575 passed    0 failed    0 skipped
```

G4, run immediately after G2: exit 0, `TOTAL` 100% (`intake.py` 94 statements and 28 branches, 0 missing).

G3: `55 passed`.

G5: `oracle: ok`, `1500 fuzzed task and link bodies get exactly the rules' answers: ok`, `300 valid deadlines are stored as make_deadline makes them: ok`. Last line: `FAILURES 0`.

G6: `1`.

G8: no output against `HEAD`.

G9, before this report replaced the earlier fail review: `docs/progress.md` and `src/docket/intake.py`, the Scope paths, plus that earlier review. Changed files in the progress entry is 2.

G10: the freeze list is unchanged (annotated-doc 0.0.6 through typing-inspection 0.4.5, including docket 0.1.0, typer 0.29.1, rich 15.0.0, ruff 0.17.5). No new dependency.

Q1 through Q7 printed nothing (`git grep` exit 1).

Spot checks, each restored from `/tmp/phase02b-verify-copies` before the next. The hash matched afterwards (`intake.py` `c972b9085802a6d2e2b079090171f84bc806f1d6`), `src/docket/__pycache__` was absent, and the file matched the copy.

- S1 failed: `Answer(422, {'error': 'invalid_key'})`.
- S2 failed: `StopIteration`.
- S3 failed with a different error: `_BadDeadline`, not `TypeError`. A note, not a finding.
- S4 failed: `StopIteration`.
- S5 failed: `StopIteration`.
- S6 failed: `'invalid_title'` against `'invalid_deadline'`.
- S7 failed: `Answer(201, {'id': 't1'})`.
- S8 failed: `Answer(422, {'error': 'key_reused'})`.
- S9 failed: `Answer(422, {'error': 'invalid_body'})` as the first answer.
- S10 failed: `StopIteration`.
- S11 failed: an answer body had a second key.
- S12 failed: the stored request lacked `deadline`.
