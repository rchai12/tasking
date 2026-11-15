# Verification process

Notes from the verifier, 2026-11-14, after Phases 0 through 2d. The gates are the right checks. The token cost is in repeating stable text, printing full test logs, and pasting whole pytest diffs for spot checks.

## Where the tokens went

Each passing phase did the same shape of work. In order of cost:

1. **Spot checks.** The guide requires `pytest -vv` for every row. A phase has 10 to 16 rows, and `-vv` prints the full assertion diff: task objects, link lists, uvicorn keyword dicts, the FastAPI telemetry sentence. The verdict only needs the first differing line. Phase 2c's S16 result was about twenty lines to show one log string.
2. **`scripts/check.py`.** It prints two full pytest sessions (the section run, then the whole suite) plus a coverage table for every module. The review then copies the two `Sections:` lines and the pass count. The rest of that log is discarded.
3. **Reading source and tests before the gates.** For 2b, 2c, and 2d the new modules and the deciding tests were read in full so each mutation could be written by hand. The gates already execute those tests. The read is needed when a spot check fails in an unexpected way.
4. **Stable documents, every phase.** `docs/phase-conventions.md` and the guide's boilerplate (coder-ran rules, restore rules, report skeleton) stay the same between phases. The spec and the gate table change.

A few rounds were pure rework:

- **2b S6.** The first edit deleted the deadline assignment and left `deadline` undefined, so the test died with `NameError`. A second edit called the core first.
- **2c S1.** The first script dropped the host middleware and never put the check on the routes. A second script did.
- **2b, first turn.** The coder had not started. That stop was cheap and correct: no `check.py`, no probe, no spot checks. The second turn re-read the whole spec and guide, and neither had a Corrections section.

## What to script

One command, `scripts/verify_phase.py --phase 2d`, can own everything that is already mechanical:

- Coder-ran: progress heading count, first follow-up, `git ls-files` on the given files, scope paths present.
- Gates G1 through G6 and G8 through G10, in order, with G4 using the `.coverage` from G2.
- The search list, run with real `|`, reported as `empty` or the matching lines.
- `pip freeze` compared with `comm` to the previous phase's freeze file, so the result is the added names (`click`, `uvicorn==0.54.0`) rather than the full list.
- A digest of about fifteen lines: pass counts, section table, coverage `TOTAL`, probe last line, scope status.

`check.py` can grow a `--quiet` that prints the summary block and the `Sections:` table and leaves the dot progress in the junit file it already writes.

Spot checks can be a second command if the guide stores the edit as a literal old/new pair, which is what the shell scripts ended up containing. The runner copies the module to `/tmp`, applies one pair, runs the deciding test, restores, and prints one line: `S7 FAIL missing proxy_headers` or `S8 PASS`. `-vv` stays available behind `--row S8` when that one line is ambiguous.

## What to change in the guide and the prompt

- Ask the verifier to read the spec, its Corrections section, and the guide's gate and spot-check tables. Point at `docs/phase-conventions.md` for the report rules. Re-read conventions when that file changed.
- Default spot-check output to the assertion line. Keep `-vv` for a row whose result is not the Broken column. Phase 2a S1 (escaped `Café`) and S8 (`KeyError` instead of DID NOT RAISE), 2b S3 (`_BadDeadline` instead of `TypeError`), and 2c S8 (the close test still passed) were the only rows that needed the traceback.
- Shorten the review's detail. The parser requires the five-line head and `## Findings`. The rest can be the digest plus any note. Restating every spot check in prose duplicates the script output.
- Put a one-screen example of "coder did not run" in the conventions. The 2b fail report was patterned by searching an old transcript.

## What should stay as a person

The judgment calls are small and they caught real guide bugs: whether a different failure is a note, whether a recorded deviation is one the guide allows, and whether a passing spot check means the code is wrong or the test cannot see the change. Phase 2c S8 is the example. Leaving the store open still passed because `all_closed()` treats a cross-thread SQLite error as closed. A script would print `PASS` and stop. Someone has to decide that this is a note for the architect.

Stopping at section 1 when the progress entry is missing should also stay. That rule saved an entire `check.py`, probe, and spot-check run on the first 2b pass.
