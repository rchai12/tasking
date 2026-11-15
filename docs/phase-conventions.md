# Phase conventions

Every phase spec and verification guide follows this document. A spec states only what is particular to its phase and points here for the rest. Where a spec says something different, the spec wins.

The coder works through the `phase-coder` skill (`/phase-coder <id>`) and the verifier through `phase-verifier` (`/phase-verifier <id>`); they say what to read and how to keep output small. This document holds the rules.

## Phase ids and files

A phase id is a number with an optional letter: `0`, `1`, `1a`, `12b`. Files use the id zero-padded to two digits: `docs/phases/phase-01a-tasks-store.md`, with its guide at `docs/verification/` and its review at `docs/reviews/` under the same file name. Headings use the id as written: `## Phase 1a: ...`, `# Review: Phase 1a`.

## For the coder

### Before you start

- The spec and its given files are committed and the tree is clean: `git status --short` prints nothing. If it prints anything, stop before writing any code and report the paths it lists; do not work around it.
- The spec states **N**: the number of tests the previous phase left passing (in Phase 0, N is 0). From Phase 1 on, the spec's given tests are committed before you start and fail until you build the phase, so `scripts/check.py` cannot pass yet. Instead run the spec's "Start" command: it sets aside the given test files that cannot import yet, and must show the count the spec names, 0 failed.

### Sections

The tests are grouped into the sections of `tests/sections.toml`. Each spec names its own under "Sections", for example `core`.

- While you work, run a section alone: `.venv/bin/python scripts/check.py --section core` (no coverage, seconds).
- Your check is `.venv/bin/python scripts/check.py --first <the spec's sections>`: its sections' tests run first, and the full run, coverage, and gates follow only once they all pass. Fix a failing section before anything else.
- **When coverage falls short**, a behaviour has no test. Write a test that checks what the uncovered line or branch does, from the spec, not one that only runs it. If the line can never run, or the spec does not need it, remove it and say so in your progress entry. Never add `# pragma: no cover` (unless the spec allows one) and never change a given test to reach the number.
- A new test file belongs in the section of the code it tests. If `core` would take it otherwise, add a pattern to `tests/sections.toml`, and list that file in your Scope.

### Scope

- Change only the paths in the spec's Scope table. You may add private helpers inside them. Any other production file, existing test, or given file stays as it is unless the spec lists it.
- **Given files are already in the repository**, committed with the spec. Never change them. If a given test fails, the code is wrong. If you believe a given file itself is wrong, stop and report; do not edit it.
- Build nothing from "Out of scope", even when it would be easy.

### Rules that hold in every phase

- **You are not the verifier.** A second agent verifies in its own session. Do not open the verification guide or `docs/reviews/`, and do not run spot checks or write a review; from `docs/verification/` you only run the probe, by the path Acceptance gives. Your work ends with the progress entry and your final message. "For the verifier" below is not for you.

- **Commands** start with `.venv/bin/python` (or `.venv/bin/docket`). Never type `python`, `python3`, `ruff`, or `pytest` on their own. Do not activate the virtual environment, and do not create one after Phase 0. Install packages only when the spec has a step for it, with `pip install -q`.
- **Git.** Do not commit. Never run `git restore`, `git checkout`, `git reset`, `git stash`, or `git clean`.
- **Real systems.** Do not connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor, do not run the EventKit helper against real calendars, and do not read the Keychain or the data folder. Tests replace them. The owner runs the real thing after verification.
- **Tests** use synthetic data only, touch no network, and read time and ids only through replaced `docket.clock.now` and `docket.ids.new_id`.
- Everything in `AGENTS.md` applies.

### Acceptance

`.venv/bin/python scripts/accept.py --phase <id>` runs the whole table below and the spec's searches, and prints one line per row; compare each with "Must show". Unless the spec adds more, the table is:

| Command | Must show |
|---|---|
| `.venv/bin/python scripts/check.py --first <the spec's sections>` | last line `All checks passed.`; the summary lists `tests (<sections>): passed`; in the `tests` step 0 failed, 0 skipped, 0 xfailed, no warnings summary, and at least N plus the spec's given test count passed; every line of the `Sections:` table shows 0 failed |
| `.venv/bin/python -m pytest <the given test files> --no-cov` | exactly the spec's given test count passed |
| the spec's coverage command | exit 0 and its `TOTAL` line at `100%`, run right after `check.py` on the data that run left |
| each of the spec's searches | no output, or exactly the lines the spec names |
| `git diff HEAD --stat -- <the given files>` | no output |
| `git status --short` | only the paths in the Scope table |
| `.venv/bin/python scripts/check_reports.py --phase <the spec's phase id>`, after writing the progress entry | `Reports OK.` |

### Report

Write an entry at the end of `docs/progress.md` with `scripts/progress.py` (it appends, or replaces your own phase's entry on a rerun, and refuses one out of form) in exactly this form, whether you finished or stopped (see "When you stop"). Every field is one line, or `None`; the architect reads these fields instead of your final message, so keep them short and literal. `scripts/check_reports.py` checks this form: the fields in this order, each list with at least one `  - ` line, and nothing else in the entry.

```markdown
## Phase <id>: <the spec's title> (YYYY-MM-DD)
- Tests: <N> -> <passed after> (given <the spec's given count>)
- New public names: `<module>`: `<name>`, `<name>`; `<module>`: `<name>` (or None)
- Changed files: <how many paths git status --short lists>
- Deviations:
  - <one line each: a choice the spec left open, or anything the spec did not ask for> (or None)
- Follow-ups:
  - <one line each: something the next phase or the architect should know> (or None)
```

In your final message give the `Sections:` table and the last lines of `scripts/check.py`'s output, one line for each other acceptance command, and for each requirement the name of a test (or the probe line) that covers it.

### When you stop

Stop, rather than work around it, when a given test fails on code you believe the spec requires, when the spec is ambiguous or contradicts itself or another file, or when an acceptance command can't pass without changing a given file or a path outside the Scope. Stopping is a result, not a silence: the architect and the verifier read `docs/progress.md`, not your final message. Before you end, append your entry in the form above, with:

- `Tests:`, `New public names` and `Changed files` as they stand now;
- as the **first** `Follow-ups` line: `Stopped: <the acceptance command, requirement or given test> | <what you observed, in one line> | <what would let you finish>`, one such line per stop.

Then run `.venv/bin/python scripts/check_reports.py --phase <the spec's phase id>` (it must print `Reports OK.`) and end. Never change a given file to get past a stop, and don't write a review. In your final message, say that you stopped and repeat the `Stopped:` lines.

When you are run again after a stop or a FAIL (the spec then has a Corrections section), run the commands the correction names as live again, plus `check_reports.py`, or the whole Acceptance table when it names none. Update your entry for this phase in place: the counts, the files, and the `Follow-ups` without the `Stopped:` line once the stop is resolved. Never add a second entry for the same phase; earlier phases' entries stay untouched.

## For the verifier

- Do not modify any file in the repository, except to write your report (below). Report findings only. The work under review is uncommitted: "the diff" is `git status --short` plus `git diff HEAD` plus the untracked files, read before you write the report.
- Run the guide's gates exactly as written, from the repository root: `.venv/bin/python scripts/accept.py --phase <id> --guide` runs them all and the searches, one line each. The first gate is `scripts/check.py --first <the spec's sections>`; if a section fails, report it with the table's rerun command.
- **Scope audit**: `git status --short` shows only the spec's Scope paths; `git diff HEAD --stat -- <the given files>` prints nothing; no existing test or unlisted module changed.
- **The probe.** It is the given file `docs/verification/probe-<NNx>.py`, committed with the spec: run it from the repository root with `.venv/bin/python docs/verification/probe-<NNx>.py`, without editing it. Every line must end in `ok`; the last line must be `FAILURES 0`.
- **A stopped coder.** When the phase's progress entry exists and its first `Follow-ups` line starts with `Stopped:`, the coder stopped on purpose. Write a FAIL report with one finding per `Stopped:` line, `<the place it names> | docs/progress.md:<line> | expected the phase finished | found the coder stopped: <its observation>`, copy the first `Stopped:` line into `For the architect`, run the given test files once (`.venv/bin/python -m pytest <the given test files> --no-cov -q`) for `Passed`, and stop there.
- **No entry.** With no progress entry for the phase, look at `git status --short`: no Scope path changed means the coder did not run; changed Scope paths mean it broke off without reporting, so name those paths in `For the architect`.
- Judge code by what it does, never by resemblance to another way of writing it.
- **Coverage reached the wrong way is a finding**: a test that runs a line but asserts nothing about what it does, a `# pragma: no cover` the spec did not allow, or code the spec requires removed to close a gap.
- **Spot checks**: for each row of the guide's spot-check table, copy the module outside the repository first, make the named one-line change, run the deciding test (`-q --tb=line`; `-vv` only for a row whose result isn't the "Broken" value), and confirm it fails (`scripts/spot_check.py` does all of this for a module under `src/`); then restore the file from your copy (never with `git checkout` or `git restore`), clear `__pycache__`, and confirm `git diff` is as before.
- **Real systems**: like the coder, never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor, never run the EventKit helper against real calendars, and never read the Keychain.

### Report and verdict

Write your report to `docs/reviews/<the spec's file name>`. It is the only file you write; the owner commits it with the phase. It starts with this block, each field on one line:

```markdown
# Review: Phase <id>

- Verdict: PASS (or FAIL)
- Passed: <the count from the tests step>
- Findings: <how many>
- Approved deviations: <one line, or None>
- For the architect: <one line the architect should act on, or None>
```

Then, under `## Findings`, one line per finding in this form, or `None`:

`<requirement id or section> | <file>:<line> | expected <...> | found <...>`

Then, after the findings and an empty line, `Parts that needed a repair: <none, or the parts>`, an empty line, and `Built beyond the spec: <none, or what>`, and after that a digest: one line per gate, one per spot check, and the searches' result, not prose restating each row. The head keeps its exact lines: the heading on line 1, the five fields on lines 3 to 7, `## Findings` on line 9. When the report is written, run `.venv/bin/python scripts/check_reports.py --phase <the phase id>`; it must print `Reports OK.`. If it names your report, correct the report's form (only its form) and run it again.

If the verdict is FAIL, send the coder each finding as: the requirement, what was observed, and what is required. Do not prescribe the code.
