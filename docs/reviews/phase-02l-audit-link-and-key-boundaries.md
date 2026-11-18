# Review: Phase 2l

- Verdict: PASS
- Passed: 1193
- Findings: 0
- Approved deviations: Private SQL entry points are insert_audit/select_audit, insert_link/select_links/select_existence/select_link, and insert_request_key/select_request_key
- For the architect: None

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none

G1: 1175 passed, 0 failed
G2: All checks passed, 1193 passed, tests (core): passed
G3: 18 passed
G4: TOTAL 100%
G5: FAILURES 0
G6: 1
G7: Reports OK.
G8: empty
G9: empty; 82f6028 contains only the Scope paths
G10: 39
S1 fails: None
S2 fails: l1,l2,l3
S3 fails: l3,l1
S4 fails: retitle,create
S5 fails: partial task/audit/sequences committed
S6 fails: altered raw audit JSON
S7 fails: unknown task instead of a write needs a transaction
searches: silent
