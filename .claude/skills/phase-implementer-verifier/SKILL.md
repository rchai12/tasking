---
name: phase-implementer-verifier
description: >-
  Implements one tasks app (docket) phase from its spec, then verifies that work
  against the matching verification guide. Use when the user asks to implement,
  build, check, or verify a phase, names a file under docs/phases or
  docs/verification, or asks the agent to act as the implementer, the verifier,
  or both. Implement only a phase the user names. If that spec is unclear, ask
  and do not write code.
---

# Phase implementer and verifier

You are both the implementer and the verifier.

- Implement based on the phases specified.
- Only implement when specified.
- Only implement the phases specified.
- Do not implement if the instructions in the phases are unclear.
- Ask questions if the instructions are unclear.
- Then verify the implementation against the verification docs.

## When to act

Wait until the user names a phase. Do not choose the next phase, and do not start a later phase because the current one passed.

If the user asks only to check or verify, do that and do not change the implementation.

## Before any code

Read, in this order:

1. `AGENTS.md`
2. `docs/architecture.md`
3. `docs/testing.md`
4. `docs/phase-conventions.md`
5. The named spec in `docs/phases/`
6. The matching guide in `docs/verification/`

If the spec or the verification guide is missing, stop and say so. If `git status --short` prints anything before you start, stop and report the paths (`docs/phase-conventions.md`, "Before you start").

Stop and ask when a requirement, file, signature, message, command, or acceptance check is ambiguous, contradictory, or impossible. Do not guess, and do not invent a workaround.

## Implement

- Build only what that spec lists. Do not add a later phase's behavior, a dependency the spec does not list, or a file the spec does not allow.
- The project's interpreter is `.venv/bin/python`. Never run bare `python`, `python3`, `ruff`, or `pytest`, and do not activate the virtual environment.
- Follow `AGENTS.md` on approval (no task without an approved source), retry safety, time (UTC instants plus a zone, through `docket.clock`), privacy (no real accounts, no Keychain, synthetic data only), and layering (every change through `docket.core`).
- Never change a given file. When the spec leaves a body for you to write, satisfy the numbered requirements and the tests.
- Append the progress entry the spec requires. Do not rewrite earlier entries.

## Verify

After the implementation, follow that phase's verification guide. Do not edit the spec, the guide, the probe or any given file to make a check pass.

While judging, do not change files except your report. Run each gate command on its own, exactly as the guide writes it.

- Compare given files with the committed versions (`git diff HEAD --stat -- <given files>`).
- Run the guide's searches and the probe (`.venv/bin/python docs/verification/probe-NNx.py`).
- For each spot check, copy the module outside the repository, make the one-line change, run the deciding test, restore from your copy (never `git checkout` or `git restore`), and clear `__pycache__`.
- Do not run the full pytest suite at the same time as a coverage command. They share `.coverage`.

Write the report to `docs/reviews/` in the form `docs/phase-conventions.md` gives, then run `.venv/bin/python scripts/check_reports.py --phase <id>`. Use `PASS`, or `FAIL` with one line per finding:

`<requirement id or section> | <file>:<line> | expected <...> | found <...>`

If the verdict is `FAIL`, fix only the failed requirements, then run the verification again. Repeat until `PASS`, or until the remaining miss means the spec is unclear. In that case, ask and stop.

Do not commit or push unless the user asks.
