# Phase 2j: Shared creation and serialization

## Goal

Remove the copied task insertion/create-audit block and the copied canonical JSON writer identified by audit finding 4. Keep public creation, validation, retry and transaction behaviour unchanged. Shared parsing and domain constants remain Phase 2k work.

Sections: `core`. The `tooling` section runs in the full check.

Follow `docs/phase-conventions.md`. N is 1042, the tests the previous phase left passing.

Start: `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_canonical_json.py --ignore=tests/integration/test_shared_creation.py` must show `1042 passed`. The ignored files specify this phase; the unit file imports the new writer.

## Facts

Checked 2026-11-17 against baseline `0f4fedf`:

- Phase 2i is committed and independently PASS: 1,042 tests, no findings, deviations or architect follow-ups. Its startup gate, migrations and task-read policy stay unchanged.
- `core.create_task` and `core.create_task_once` duplicate the insert/open-state and create-audit snapshot. Both validate and read `clock.now()` before entering their own transaction; keyed creation checks the request key inside that transaction.
- `store._json` and `core._canonical` call `json.dumps` with the same three options: sort_keys=True, ensure_ascii=False, separators=(",", ":"). Store uses its writer for audit before/after and saved requests; core compares both sides of task and link replays. Store still needs json.loads.
- Nine literal codec cases exercise standard-library output and failure propagation, including existing non-finite float defaults. This phase does not define a stricter JSON language. HTTP parsing rules remain in their existing layer.
- Baseline integration tests: 14 behaviour guards pass; the shared-module routing and single-private-creation-path checks fail for the intended missing consolidation. The unit file cannot import the new module. Names-only stubs collect 25 cases from nine functions: 11 fail, 14 guards pass.
- A discarded, small serializer-routing patch passed 24 targeted cases; the structural creation check was deliberately excluded. No shared creation implementation or full reference phase was built. Probe oracle passes; baseline reports exactly the missing codec and duplicate creation site, while restart/replay and rollback guards pass.

## Owner's decisions

No new owner decision. The approved roadmap already calls for this internal consolidation. Earlier explicit-client, reference-limit, upgrade-refusal and startup-lock choices remain unchanged.

## Architect's decisions

- Add one public pure utility: `docket.serialization.canonical_json(value: dict[str, object]) -> str`. It is the established standard-library writer, with no new validation, normalization, exception mapping or settings.
- Core and store import the module and call `serialization.canonical_json(...)`, so saving and comparing depend on the same replaceable function. Keep decoding in store; do not introduce a serializer class or JSON dependency.
- The coder chooses the private creation helper's name and signature. It receives already validated values and the caller's timestamp, inserts the open task, appends its create audit row and returns the Task. It owns no transaction, key lookup/insertion, validation or clock read.
- Add serialization.py to the given critical-module list: mismatched retry encodings can duplicate or reject approved work. It must have 100% line and branch coverage like core/store.

## Requirements

1. **Canonical writer:** implement the exact public utility above using the existing dumps options. Preserve nested sorting, compact separators, unescaped Unicode, null/boolean/numeric distinctions, escaping and all other standard-library defaults. Do not mutate input. Existing TypeError and ValueError propagate. Given: all nine unit cases.
2. **One JSON dependency:** use that utility for both audit snapshots, saving every request-key body and comparing both sides of task and link retries. Remove the duplicate writer implementations; private forwarding helpers may be retained only when they contain no encoding policy. No json.dumps call remains in core.py or store.py. Given: routing test, exact raw rows and codec cases.
3. **One creation body:** both public create functions directly call one private helper for insertion plus the complete create audit snapshot. There is exactly one insert_task call site in core, inside that helper, and one append_audit call in that helper. Preserve source-to-actor mapping, state open, all reference fields, absent times, deadline time_given and full work snapshots. Given: structural check, six source/path snapshots and two time snapshots.
4. **Caller-owned control:** retain every existing public signature, validation rule and refusal order in the public entry points. Each valid invocation still reads clock.now once before its single Store.transaction context, including repeats/conflicts; validation failures retain their existing clock behaviour. The private creation helper reads no clock, validates nothing and opens no transaction. Key lookup, task/audit creation and key insertion remain inside the keyed caller's one transaction. Do not call create_task from create_task_once or add a second transaction. Given: bounded fixed clocks, five after-write rollback cases and prior core tests; coder adds the transaction/validation tests below.
5. **Retry and storage compatibility:** a replay with reordered nested keys writes nothing and returns the current task, including an ended task. A changed JSON body conflicts with key_reused even when Python compares true and 1 as equal, or a null field is omitted. Link replays use the same writer without gaining an audit entry. Preserve raw canonical bytes, IDs, timestamps, no-deadline/work nulls and existing stored keys across reopen. A failure after task, audit or key insertion rolls everything back; retry after rollback can allocate t1. Given: replay, rollback and raw-row tests; restart property in the probe.
6. **Boundaries and coverage:** no migration, schema/version change, dependency, network operation, public core/store API change or new error message. Keep task state changes in core, existing startup/read safeguards and all earlier tests. serialization.py, core.py and store.py remain at 100% line and branch coverage.

7. **Progress entry** for `## Phase 2j: Shared creation and serialization (YYYY-MM-DD)` at the end of `docs/progress.md`.

## Given files

Already committed with this spec; never change them.

| File | What it is |
|---|---|
| `tests/unit/test_canonical_json.py` | 9 tests from 3 functions (requirement 1) |
| `tests/integration/test_shared_creation.py` | 16 tests from 6 functions (requirements 2–5) |
| `scripts/critical_modules.txt` | Given critical gate addition for serialization.py |
| `docs/verification/probe-02j.py` | The verifier's probe |

Given test count: **25** (9 functions). Fourteen unchanged-behaviour guards pass on baseline and the names-only serializer stub; 11 cases fail on the stub. The two architectural checks prevent a behaviour-preserving no-op from satisfying this refactoring phase.

## Tests to write

Write `tests/integration/test_creation_transactions_and_retries.py` without changing earlier tests:

- Spy on transaction entry: one context for unkeyed create, keyed create, replay and conflict; insertion, create audit and key recording run inside it. The private helper never opens a nested context.
- Combine invalid inputs to preserve existing refusal order: bad client before key/title, bad key before title, bad title before source/reference and wrong source before reference/work. Assert no writes and no added clock read on these refusals.
- A saved link key cannot be replayed as a task create, or a saved task key as a link; conflicts leave the current task, audit and keys unchanged. Existing tests remain deciding guards too.
- Read/replay a synthetic pre-existing key with nested Unicode/null JSON after reopening, with no rewriting of its stored bytes.
- Cover any remaining branch with a deciding assertion. Do not add exclusions or edit a given file.

## Scope

| Path | Change |
|---|---|
| `src/docket/serialization.py` | create |
| `tests/integration/test_creation_transactions_and_retries.py` | create |
| `src/docket/core.py` | edit: shared private insertion/create-audit helper and module-based canonical comparisons |
| `src/docket/store.py` | edit: use shared JSON writer for audit snapshots and request keys; retain decoding |
| `docs/progress.md` | append your entry |

## Out of scope

- Sharing validation, date/time parsers, lists, limits or zones; changing settings error mapping (Phase 2k).
- Table-module extraction, tooling moves or test consolidation (Phases 2l–2n).
- New serialization grammar, normalization, strict non-finite-number rejection, JSON error mapping or historic-row rewrites.
- Schema/migration changes, new task fields, reminders, calendar/Discord integration, MCP/API/CLI changes, startup/read-policy changes or new dependencies.
- Reading the real data folder, Keychain or any account/service.
- Any change to a given file, `AGENTS.md` or the design docs.

## Rules that bite

- **Approval and retry safety:** validation stays in its established public boundary; source/client checks cannot be bypassed by the shared helper. A retry never creates another task or audit row.
- **Atomicity:** the caller owns the transaction. Never commit the helper's writes separately from the request key.
- **Privacy:** no logging, output, model, network call or error text derived from request/title/library text is added.
- **Determinism:** preserve the caller's one timestamp and every literal snapshot; synthetic temporary databases only.
- **Time through the module**: `clock.now()`, never `datetime.now()`, and never `from docket.clock import now`.
- If you stop before finishing, still write the progress entry with a `Stopped:` first follow-up (`docs/phase-conventions.md`, "When you stop").
- Commands start with `.venv/bin/python`; no bare `python3`, `pytest` or `ruff`.

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_canonical_json.py --ignore=tests/integration/test_shared_creation.py` (before you start) | `1042 passed` |
| `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1067 passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest tests/unit/test_canonical_json.py tests/integration/test_shared_creation.py --no-cov -q` | `25 passed` |
| `.venv/bin/python -m coverage report --include=src/docket/serialization.py,src/docket/core.py,src/docket/store.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| `.venv/bin/python docs/verification/probe-02j.py` | last line `FAILURES 0` |
| `grep -c "^## Phase 2j: " docs/progress.md` | `1` |
| `.venv/bin/python scripts/check_reports.py --phase 2j` | `Reports OK.` |
| `git diff HEAD --stat -- tests/unit/test_canonical_json.py tests/integration/test_shared_creation.py scripts/critical_modules.txt docs/verification/probe-02j.py` | no output |
| `git status --short` | only the Scope paths |

### Searches

Each prints nothing.

```zsh
git grep --untracked -n -E 'import (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)|from (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)' -- src
git grep --untracked -n -E 'print\(|logging|logger|warnings\.warn' -- src ':!src/docket/cli.py'
git grep --untracked -n -E 'datetime\.now|datetime\.utcnow|date\.today|time\.time\(|from docket\.(clock|ids) import' -- src ':!src/docket/clock.py'
git grep --untracked -n -E '\.(insert_task|update_task|append_audit|insert_link|insert_request_key)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'
git grep --untracked -n -E 'ollama|anthropic|openai|langchain' -- src
git grep --untracked -n -E 'pragma: no cover|noqa' -- src/docket/serialization.py src/docket/core.py src/docket/store.py
```

## Test path migration (Phase 2q)

The product continuation paths above now use behaviour names. This is a byte-identical file move; function names, parameter IDs, counts and original implementation history are unchanged. The phase's immutable move inventory records every old/new selector.
