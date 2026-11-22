# Review: Phase 5b

- Verdict: PASS
- Passed: 1896
- Findings: 0
- Approved deviations: None
- For the architect: the coder's work was already committed (e185995) when I ran, so the HEAD-based diff gates were judged against the spec commit 75e22fb, as the guide allows. The moved code reads `MIGRATIONS`, `SCHEMA_VERSION` and `StoreError` through `docket.store` at run time, a guide-listed variation.

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none

G1: 1877 passed
G2: All checks passed, 1896 passed (core 1750, tooling 146), tests (core): passed
G3: 19 passed
G4: TOTAL 100%
G5: FAILURES 0
G6: 1
G7: Reports OK
G8: empty (against 75e22fb)
G9: 0 added, 9 deleted (against 75e22fb)
G10: 1 added, 0 deleted (against 75e22fb)
G11: only the Scope paths changed since 75e22fb
G12: 52
S1 fails: DID NOT RAISE ValueError
S2 fails: two migrate calls per open
S3 fails: IndexError
S4 fails: backfill rows empty
S5 fails: wrong zone in column 4
S6 fails: ValueError unknown task column
S7 fails: message names the key
S8 fails: wrong zone in column 4
searches: silent
