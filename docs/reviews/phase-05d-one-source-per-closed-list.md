# Review: Phase 5d

- Verdict: PASS
- Passed: 1936
- Findings: 0
- Approved deviations: None
- For the architect: the coder's work was already committed (87b3a06) when I ran, so the HEAD-based diff gates were judged against the spec commit 475398d, as the guide allows. `core.add_link` still passes the source `"email"` to `_check_reference`, which the spec allows.

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none

G1: 1909 passed
G2: All checks passed, 1936 passed (core 1790, tooling 146), tests (core): passed
G3: 27 passed
G4: TOTAL 100%
G5: FAILURES 0
G6: 1
G7: Reports OK
G8: empty (against 475398d)
G9: 0 added, 8 deleted (against 475398d)
G10: only the Scope paths changed since 475398d
G11: 52
S1 fails: STATES[:2] spelled
S2 fails: 200 characters refused
S3 fails: web answers 422 not 400
S4 fails: digest key check missed
S5 fails: late list not derived from domain
S6 fails: core.py kinds literal listed
S7 fails: clients.py names the email client
S8 fails: _REPLAY is _CREATED - 1
S9 fails: source read through _text
S10 fails: docket.config duplicates a limit
searches: silent
