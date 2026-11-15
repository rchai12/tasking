# Review: Phase 2a

- Verdict: PASS
- Passed: 579
- Findings: 0
- Approved deviations: create_task_once writes the task and its create audit row itself, so the key is recorded in that same transaction; a link id is l followed by a non-zero number, the same shape as a task id
- For the architect: the verification guide says 56 given tests (G2 floor 578, G3 `56 passed`); the spec says 57 and 579, and the run matches the spec. S1's default json.dumps escapes Café, and S8 raises KeyError 'l1' because the repeat still loads links of the named task

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none

The placeholder `<spec commit>` was unfilled. The baseline is `594cf1a`, the commit that contains the Corrections section. `git ls-files --error-unmatch` found the spec, `tests/integration/test_store_links.py`, `tests/integration/test_core_keyed.py`, `src/docket/schema.py`, `tests/integration/test_store.py`, `tests/e2e/test_cli_tasks_more.py`, and `docs/verification/probe-02a.py`. `git diff HEAD` for those given files is empty. `grep -c "^## Phase 2a: " docs/progress.md` printed `1`. The first follow-up is `None`, not `Stopped:`.

G1 `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_store_links.py --ignore=tests/integration/test_core_keyed.py`: `522 passed`, 0 failed. There is no `*_more.py` for this phase.

G2 `.venv/bin/python scripts/check.py --first core` ended with `All checks passed.` Summary: lint passed, format passed, `tests (core): passed`, tests passed, critical coverage passed. The tests step passed 579, 0 failed, 0 skipped, and printed no warnings summary. That meets the spec's floor of 579 and the guide's floor of 578.

```
Sections:
  core          520 passed    0 failed    0 skipped
Sections:
  tooling        59 passed    0 failed    0 skipped
  core          520 passed    0 failed    0 skipped
```

G4, run immediately after G2: exit 0, `TOTAL` 100% (`core.py` 190 statements and 86 branches, `store.py` 250 statements and 54 branches, 0 missing).

G3: `57 passed`. The spec requires 57. The guide's `56 passed` is one short of the spec, so the spec wins.

G5: `oracle: ok`, `700 keyed creates and links follow the model of the keys: ok`, `two senders of one key at once make one task: ok`. Last line: `FAILURES 0`.

G6: `1`.

G8: no output against `HEAD`.

G9, before this report: `docs/progress.md`, `src/docket/core.py`, and `src/docket/store.py`, the Scope paths. Changed files in the progress entry is 3.

G10: the freeze list is unchanged (annotated-doc 0.0.6 through typing-inspection 0.4.5, including docket 0.1.0, typer 0.29.1, rich 15.0.0, ruff 0.17.5). No new dependency.

Q1 through Q6 printed nothing (`git grep` exit 1).

Spot checks, each restored from `/tmp/phase02a-verify-copies` before the next. Hashes matched afterwards (`core.py` `210fd8dc1c4ead593c698cb86c327d79fb8a6783`, `store.py` `9446294dd422be5b207fd11f30ff1c34ca5f79b2`), `src/docket/__pycache__` was absent, and `git diff HEAD` for those two files was the phase diff again (275 insertions, 1 deletion).

- S1 failed with a different text: `'{"title": "Caf\\u00e9", "deadline": null, "a": [1, 2]}'`, not the guide's unescaped Café. Default `json.dumps` escapes non-ASCII. A note, not a finding.
- S2 failed: `sqlite3.IntegrityError: FOREIGN KEY constraint failed`.
- S3 failed: `[l3, l1]` against `[l1, l3]`.
- S4 failed: `CoreError: key_reused`.
- S5 failed: `StopIteration`.
- S6 failed: `StopIteration`.
- S7 failed: `changed` True against False.
- S8 failed with a different error: `KeyError: 'l1'`. Dropping the task comparison still reads `store.links` for the task named in the call, so `l1` is not in that list. A note, not a finding.
- S9 failed: `unknown_task` against `key_reused`.
- S10 failed: `StopIteration`.
- S11 failed: tasks `['t1', 't2']` against `['t1']`.
- S12 failed: `sqlite3.IntegrityError` on the audit action CHECK.
- S13 failed: `CoreError: task_ended`.
