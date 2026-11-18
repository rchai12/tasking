# Review: Phase 2p

- Verdict: PASS
- Passed: 1321
- Findings: 0
- Approved deviations: None
- For the architect: S1, S2, S4 and S5 fail by naming the changed path; those are the guide's inventory, case, fingerprint and frozen-byte checks

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none

G1: 1297 passed, 0 failed
G2: All checks passed, 1321 passed, tests (core): passed
G3: 24 passed
G4: TOTAL 100%
G5: FAILURES 0
G6: 1
G7: Reports OK.
G8: empty
G9: empty; 307c2b9 contains only the Scope paths
G10: 39
S1 fails: changed body inventory (note: assertion names the path)
S2 fails: missing case (note: assertion names the path)
S3 fails: selector not found
S4 fails: document fingerprint (note: assertion names the path)
S5 fails: frozen bytes (note: assertion names tests/support.py)
searches: silent
