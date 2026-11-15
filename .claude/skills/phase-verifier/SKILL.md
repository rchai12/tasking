---
name: phase-verifier
description: >-
  Verify one named tasks app (docket) phase against its verification guide,
  as the verifier, and write the review. Use only when the owner invokes it
  with a phase id (/phase-verifier 2e). Never changes the implementation.
disable-model-invocation: true
---

# Phase verifier (tasks app)

You verify exactly one phase, the one the owner names (`$ARGUMENTS`), against the uncommitted work of a coder in another session. The only file you write is the review.

## Read, in this order

1. The spec: `docs/phases/phase-<NNx>-*.md`, **its Corrections section first** if it has one.
2. The guide: `docs/verification/phase-<NNx>-*.md`. Its section 1 can end the review early; do it before anything else.
3. `docs/phase-conventions.md`, "For the verifier", when it changed since your last review (`git log -1 --format=%cd -- docs/phase-conventions.md`) or you haven't read it in this project before.
4. The coder's progress entry for this phase (by range, from its `## Phase` heading).
5. The code the coder wrote, by range, only to place each spot check's edit; the gates already run the tests.

`AGENTS.md` is already in your context through `CLAUDE.md`; don't read it again.

## Stop early

- No progress entry and no Scope path changed: the coder didn't run. Write the FAIL review with `Passed: 0` and stop; run no gates.
- An entry whose first `Follow-ups` line starts with `Stopped:`: write the FAIL review the conventions describe, run the given test files once for `Passed`, and stop.

A FAIL for a coder who did not run looks like this whole report:

```markdown
# Review: Phase 2e

- Verdict: FAIL
- Passed: 0
- Findings: 1
- Approved deviations: None
- For the architect: the coder did not run (no progress entry, no Scope path changed)

## Findings

Coder ran | docs/progress.md:1 | expected a `## Phase 2e: ` entry | found none, and git status --short lists no Scope path

Parts that needed a repair: none

Built beyond the spec: none
```

## Keep output small

- **Gates and searches in one command**: `.venv/bin/python scripts/accept.py --phase <id> --guide`. It runs the guide's gates in order and then its searches, and prints one line per row (`G2: All checks passed.` with the Sections table, `Q3: empty`, or the matching lines). Each row's full output is in the log folder it names. Compare each line with the guide's "Must show"; the script doesn't judge it.
- **Spot checks on a module under `src/`**: write the row's change as an exact old and new text (one match in the module the coder wrote), then `.venv/bin/python scripts/spot_check.py <module> --old '<old>' --new '<new>' --test '<deciding test>' --row S<n>`. It changes the module, runs the test, always restores the module, and prints one line (`S7 fails: ...`, `S8 passes`, `S9 no test ran`). Rerun the test by hand with `-vv` only for a row whose line isn't the guide's "Broken" value.
- **Spot checks on a file outside `src/`** (a script): copy it outside the repository, make the change, run the test with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest '<test>' --no-cov -q --tb=line 2>&1 | tail -5`, and restore it from the copy, never with git.
- After the spot checks, `git diff --stat` must be as it was before them.

## Judgment stays yours

A spot check whose result differs from its "Broken" value is a note; one that passes means either the code is wrong or the test can't see the change. Decide which, and say it in `For the architect` (Phase 2c's S8 passed because the test's helper counted a cross-thread SQLite error as a closed store). Decide whether each deviation in the progress entry is one the guide's "Reasonable variations" or the spec allows; one in an approval, idempotency or owner check must fail closed.

## Report

Write `docs/reviews/<the spec's file name>` in the form the conventions give: the five-line head, `## Findings`, the two `Parts that needed a repair` and `Built beyond the spec` lines. After them, a digest instead of prose:

- one line per gate (`G2: All checks passed, 732 passed`, `G5: FAILURES 0`, `G10: + click, uvicorn 0.54.0`);
- one line per spot check (`S7 fails: no proxy_headers`, `S8 differs: <what> (note)`);
- `searches: silent`.

Then `.venv/bin/python scripts/check_reports.py --phase <id>` must print `Reports OK.`
