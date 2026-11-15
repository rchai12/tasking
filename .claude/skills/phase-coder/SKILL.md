---
name: phase-coder
description: >-
  Implement one named tasks app (docket) phase from its spec in docs/phases/,
  as the coder. Use only when the owner invokes it with a phase id
  (/phase-coder 2e). Never verifies, never reads the verification guide.
disable-model-invocation: true
---

# Phase coder (tasks app)

You implement exactly one phase, the one the owner names (`$ARGUMENTS`). A second agent verifies it in another session.

## Read, in this order

1. The spec: `docs/phases/phase-<NNx>-*.md` (the id zero-padded to two digits), **its Corrections section first** if it has one.
2. The spec's given test files, in full. They are the contract; skipping them means building against a guess.
3. `docs/phase-conventions.md`, "For the coder". It holds the rules every spec relies on: the Start command, sections, Scope, the progress entry and "When you stop".
4. The last entry of `docs/progress.md` (by range, from its `## Phase` heading), for the previous phase's names and deviations.
5. The code the spec names, by range, only where you change it or a given test depends on it.

`AGENTS.md` is already in your context through `CLAUDE.md`; don't read it again. Read `docs/architecture.md` or `docs/testing.md` only when the spec points to a section of them.

Never open `docs/verification/` except to run the probe by the path Acceptance gives, and never open `docs/reviews/`.

## Keep output small

- A single test file or section: `.venv/bin/python -m pytest <files> --no-cov -q --tb=line 2>&1 | tail -15`. Read a full traceback only for a failure the line doesn't explain.
- `scripts/check.py`: send its output to a file outside the repository and read the end:
  `.venv/bin/python scripts/check.py --first <sections> > "$TMPDIR/docket-check.log" 2>&1; tail -40 "$TMPDIR/docket-check.log"`.
  Open the log by range only when a step failed.
- An install step: `.venv/bin/python -m pip install -q -e '.[dev]'`, then `.venv/bin/python -m pip list 2>/dev/null | grep -i -E '^(<the packages the spec names>) '`.
- Searches print nothing when they pass; run them as written.

## Report

- **Append** your entry to the end of `docs/progress.md` in the form the conventions give: one write at the end of the file, never a replace of text that other entries share (every entry ends with the same `Follow-ups` block). On a rerun after a stop, change only your own phase's entry, locating it by its `## Phase <id>: ` heading.
- Then `.venv/bin/python scripts/check_reports.py --phase <id>` must print `Reports OK.`
- **On a rerun with a Corrections section**, run the commands the correction names as live again, plus `check_reports.py`. When it names none, run the whole Acceptance table.
- Your final message, short and literal:
  - the `Sections:` table and the last lines of `check.py` (`All checks passed.`);
  - one line per other acceptance command (`given: 24 passed`, `coverage: TOTAL 100%`, `probe: FAILURES 0`, `searches: silent`, `diff: empty`, the `git status --short` lines);
  - for each requirement, the test or probe line that covers it;
  - if you stopped, the `Stopped:` lines.
