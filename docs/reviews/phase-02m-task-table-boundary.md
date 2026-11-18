# Review: Phase 2m

- Verdict: PASS
- Passed: 1223
- Findings: 0
- Approved deviations: Private task SQL entry points are insert_task, update_task, select_task, select_tasks, select_tasks_in_states, and select_existence
- For the architect: None

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none

G1: 1197 passed, 0 failed
G2: All checks passed, 1223 passed, tests (core): passed
G3: 26 passed
G4: TOTAL 100%
G5: FAILURES 0
G6: 1
G7: Reports OK.
G8: empty
G9: empty; b977a74 contains only the Scope paths
G10: 39
S1 fails: t2
S2 fails: t3,t2,t1
S3 fails: old deadline retained
S4 fails: created 15:00, updated 14:00
S5 fails: partial task update persists
S6 fails: DID NOT RAISE StoreError
searches: silent
