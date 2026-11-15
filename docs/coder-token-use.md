# Coder token use

Notes from the coding agent after Phases 1c through 2d (2026-11-14). The cost was repeated reading and full test transcripts. The code itself was small next to that.

## What cost the most

**The same four documents, every phase.** `AGENTS.md`, `docs/architecture.md`, `docs/testing.md`, and `docs/phase-conventions.md` do not change between phases. `docs/architecture.md` is also stale: its status line still says Phase 1 is next. Each phase spec already points at those files for the rules that matter. Reading them again added context and no new decisions.

**`scripts/check.py` output.** A core-first check prints a dot for every test, twice (the section run, then the full run), plus a full coverage table. Acceptance then asks for a second coverage report and a third run of the given tests. For Phase 2d that was 703 tests, then 732, then the 24 given tests. The report only needed `All checks passed.`, the `Sections:` table, `TOTAL 100%`, and `24 passed`.

**Pip.** Phase 2c and 2d pasted the full resolver log. The useful lines were the package names and versions.

**Progress edits.** `docs/progress.md` ends every phase with the same `Follow-ups:` block, so a short replace hit several entries and had to be retried with a larger quote of the previous phase. The file was read again only to copy a form that `scripts/check_reports.py` already enforces.

**Probe failures.** On Phase 2a the probe printed `new != unknown-task` and nothing about `t99` already existing. Diagnosing that meant reading the probe and simulating the walk. The Corrections section later said the same thing in one paragraph. A failure line that includes the reason would have made the stop immediate.

## What to change

**Shorten the phase prompt.** Point at the phase spec and `docs/progress.md`. State that `AGENTS.md`, `docs/testing.md`, and the coder half of `docs/phase-conventions.md` are unchanged unless the spec says otherwise. Skip `docs/architecture.md` unless that phase edits it.

The prompt in [the docs index](README.md) is currently:

> Read AGENTS.md, docs/architecture.md, docs/testing.md, docs/phase-conventions.md, docs/progress.md, and docs/phases/phase-NN-*.md. Implement only that phase. Do not read docs/verification/ except to run the probe named in Acceptance, do not verify your own work, and do not write a review. Run every command under "Acceptance" before you report, and write the progress entry.

A shorter one:

> Read docs/phases/phase-NN-*.md and docs/progress.md. AGENTS.md, docs/testing.md, and the coder half of docs/phase-conventions.md are unchanged. Implement only that phase. Do not read docs/verification/ except to run the probe named in Acceptance, do not verify your own work, and do not write a review. Run `scripts/accept.py --phase NN` and write the progress entry from its output.

**Add one acceptance script** that runs the spec's commands and prints only the lines the report quotes. Keep the full logs on disk.

```text
start: 703 passed
check: All checks passed.
sections: tooling 59 passed, core 673 passed
coverage: TOTAL 100%
given: 24 passed
probe: FAILURES 0
searches: silent
diff: empty
status:
 M docs/progress.md
 ...
```

The model should see this block, not the dot matrices.

**Quiet installs.** `.venv/bin/python -m pip install -q -e '.[dev]'`, then one line such as `uvicorn 0.54.0`. The spec can require that form.

**Append the progress entry with a script.** Something like `scripts/progress.py --phase 2d --tests 703:732 --given 24` that checks the field order the way `scripts/check_reports.py` does. That removes the read-and-replace of the whole log.

**Make the probe's failure line sufficient.** Include the step, the expected code, the actual code, and the fact that made them differ (`t99 already stored`, `cleared 5 < 15`). The coder can stop from that line and should not need the probe source.

**On a correction that says the code was right, rerun the failed command plus `scripts/check_reports.py`.** Phase 2a kept the code and still re-ran lint, both test suites, and coverage. The spec can say which commands are live again. A probe-only fix does not need another full check when the previous check already passed.

## What should stay

Reading the given tests in full is the cheap part. Those files are the real spec, and skipping them is how a phase gets implemented against a guess.

Running `scripts/check.py` itself should stay. Hiding its log is the saving. The searches are already cheap because they print nothing.

The final report's requirement-to-test list is small next to a pytest transcript. A compact acceptance script would make that report a fill-in, and the model would not need the transcripts in context to write it.
