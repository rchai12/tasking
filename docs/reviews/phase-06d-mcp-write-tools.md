# Review: Phase 6d

- Verdict: PASS
- Passed: 1775
- Findings: 0
- Approved deviations: None
- For the architect: the coder's work was already committed (e016c34) when I ran, so the HEAD-based diff gates were judged against the spec commit 2b49d4f, as the guide allows.

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none

G1: 1708 passed
G2: All checks passed, 1775 passed (core 1629, tooling 146), tests (core): passed
G3: 67 passed
G4: TOTAL 100%
G5: FAILURES 0
G6: 1
G7: Reports OK
G8: empty (against 2b49d4f)
G9: 0 added, 8, 7 and 7 deleted (against 2b49d4f)
G10: only the Scope paths changed since 2b49d4f
G11: 52
S1 fails: AssertionError
S2 fails: IntegrityError
S3 fails: assert None is not None
S4 fails: audit actor owner
S5 fails: DID NOT RAISE
S6 fails: DID NOT RAISE
S7 fails: invalid_key instead of unknown_task
S8 fails: AssertionError naming cancel_task
S9 fails: text carries the exception repr
searches: silent
