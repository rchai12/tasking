# Phase history

One line per phase: what was built, what went wrong, the lesson. Read to size a phase or find a precedent; the sibling projects' histories (`finances`, `emails`, `langgraph`) hold earlier lessons.

| Phase | Built | Result |
|---|---|---|
| 0 | Package, the email service's Phase 0 tooling and seams adapted (check scripts, report checker and its 59 tests, clock, ids, settings with a private data folder, Keychain reads); 96 given tests (59 tooling); the probe a given file from Phase 0 on (the email service embedded it until 1b) | specified; result pending. Fail check: 59 report tests pass, the other 4 files fail at import. A throwaway draft (the email service's Phase 0 modules, renamed) passed all 96 tests, `check.py`, and the probe (FAILURES 0, 59 ok); the probe on today's code prints FAILURES 1. S6 and S10 confirmed on the draft. The repository was not under git yet: the owner initialises and commits the baseline before the coder runs (the email service's Phase 0 FAIL on G7 came from an uncommitted baseline) |
