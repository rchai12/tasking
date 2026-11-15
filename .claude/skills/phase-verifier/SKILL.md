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

- `scripts/check.py`: `.venv/bin/python scripts/check.py --first <sections> > "$TMPDIR/docket-check.log" 2>&1; tail -40 "$TMPDIR/docket-check.log"`. Coverage (the next gate) reads the data that run left.
- **Spot checks**: run the deciding test with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest '<test>' --no-cov -q --tb=line 2>&1 | tail -5`. The assertion line is enough when it shows the guide's "Broken" value. Rerun with `-vv` only for a row whose result differs from "Broken", or that passes.
- Make each spot check's change with an exact old and new text (one match), from a copy of the module kept outside the repository, and restore it from that copy, never with git. Check that `git diff --stat` is as before after each row.
- Searches print nothing when they pass; run them as written, with real `|` for the guide's `\|`.

## Judgment stays yours

A spot check whose result differs from its "Broken" value is a note; one that passes means either the code is wrong or the test can't see the change. Decide which, and say it in `For the architect` (Phase 2c's S8 passed because the test's helper counted a cross-thread SQLite error as a closed store). Decide whether each deviation in the progress entry is one the guide's "Reasonable variations" or the spec allows; one in an approval, idempotency or owner check must fail closed.

## Report

Write `docs/reviews/<the spec's file name>` in the form the conventions give: the five-line head, `## Findings`, the two `Parts that needed a repair` and `Built beyond the spec` lines. After them, a digest instead of prose:

- one line per gate (`G2: All checks passed, 732 passed`, `G5: FAILURES 0`, `G10: + click, uvicorn 0.54.0`);
- one line per spot check (`S7 fails: no proxy_headers`, `S8 differs: <what> (note)`);
- `searches: silent`.

Then `.venv/bin/python scripts/check_reports.py --phase <id>` must print `Reports OK.`
