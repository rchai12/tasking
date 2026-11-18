# Phase 3a: Deterministic reminder planning

## Goal

Implement the pure scheduling policy that the durable reminder engine will consume: a complete immutable UTC plan for a valid task at an explicitly supplied approved planning instant. Cover the one-hour warning, due-soon boundary, deadline, seven late slots and planned-work start. This is reminder functionality, not another cleanup phase. It adds no database table, send, loop, digest or live service; those are the next functional integration steps.

Sections: `core`. The `tooling` section runs in the full check.

Follow `docs/phase-conventions.md`. N is 1349, the tests the previous phase left passing.

Start: `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_reminder_plans.py` must show `1349 passed`. The ignored files import names you create.

## Facts

Checked 2026-11-18 against independently verified 5bafc08:

- Phase 2q is PASS at 1,349 tests with no findings/deviations. Baseline full checker passes both coverage gates. The only existing working-tree edits at planning start were this architect's authorized roadmap/history updates from that PASS; no coder work is overwritten.
- Task is the existing frozen docket.store.Task, with state, optional Deadline and optional WorkTime. Their instants already use canonical datetime.UTC; settings and wall-time parsing remain outside this planner. The existing time contract rejects ZoneInfo("UTC") as distinct from datetime.UTC.
- Standard-library timedelta calculations confirm seven late offsets in real minutes: 30, 60, 120, 180, 240, 480, 720. For 2026-11-20 18:00 UTC they end at 2026-11-21 06:00 UTC. The JSON examples store literal whole plans, not expected values computed by the planner.
- New York fold=0 on 2026-11-01 01:30 is 05:30 UTC; 2027-03-14 02:30 fold=0 maps to 07:30 UTC (03:30 local). Warning instants are 04:30 and 06:30 UTC respectively. Date-only 2026-11-20 17:00 New York is 22:00 UTC, with warning at 21:00 UTC. The probe's standard-library oracle checks both DST conversions.
- There are 30 given cases from six functions. An empty module fails all 30 for missing names; names-only data/constants plus a NotImplementedError planner fail 28 and pass the two representation/constant guards. This pure function is not prototyped: the literal arithmetic oracle is checked instead of building a reference implementation.
- Adding a critical module and reconciling AGENTS.md requires authorized planning-time updates to older preservation pins. Four given manifests are updated in dependency order, retaining their case inventories, entry counts and nonaffected fingerprints. No existing test function or source module is edited.

## Owner's decisions

Decided 2026-11-18: internal persistent rows use SQLite-assigned, never-reused IDs, including reminders r1, r2, and onward. Outbound retry keys come from docket.ids.new_id(), are persisted once and reused on retries. Existing task/link IDs remain unchanged. AGENTS.md and architecture.md are reconciled with this choice in the committed planning handoff. This pure planner allocates neither row IDs nor outbound keys.

Existing decisions remain: no quiet hours; 17:00 for date-only deadlines; deadline offsets use elapsed UTC time; late backoff is two half-hour slots, three hourly slots, two four-hour slots, then the later daily digest. No new dependency or live-service approval.

## Architect's decisions

The public contract is in src/docket/reminders.py:

- LATE_MINUTES is the tuple (30, 60, 120, 180, 240, 480, 720).
- PlannedReminder is a frozen dataclass with exactly kind then fire_at. kind is typed Literal["start", "before", "due_soon", "due", "late"]; fire_at is datetime. It is a typed value record, with no allocation, database identity or extra constructor validation.
- plan_reminders(task: Task, now: datetime) -> tuple[PlannedReminder, ...]. Inputs are a valid existing Task and a datetime. Require now.tzinfo is datetime.UTC before examining state; otherwise raise the existing DeadlineError with exact text "an instant must be in UTC", no chained exception. Other input types/malformed task records are outside this typed contract; do not reparse task text or reload it.

now means the instant of approved creation/replanning, supplied by the future caller through clock.now(). It is not the poll time. Restarting a sender will load persisted plans, not repeatedly call this function with a changing now.

An active task is open or in_progress; done/cancelled return (). An active task without deadline or work returns (). For a deadline at least one elapsed hour after now, include before at deadline minus one hour, including equality. For 0 < deadline-now < one hour, instead include due_soon at now, retaining microseconds. For a deadline at or before now, include neither warning. Every active deadline includes due at the original deadline and all seven late slots at the original offset instants, even when past. These past slots are evidence for the later single-status catch-up sender, not an instruction to send each overdue row separately. Do not advance, omit, cap or rewrite them.

An active task with work includes start at its original UTC start, even when past and even without a deadline. Work minutes and zones do not shift that instant. Return all rows sorted by fire_at ascending, with equal-time kind order start, before, due_soon, due, late. No coalescing of different kinds at the same instant. Each late slot is a separate row. No digest row, message, title, button, retry key or state change. Immutable tuples/rows and unchanged inputs make repeated planning deterministic.

Use only standard datetime arithmetic on the stored UTC instants; no local-zone conversion in product planning. At datetime's representable extremes, arithmetic follows the standard OverflowError rather than silently clipping a reminder. Future transactional integration must handle scheduling failure before committing a task change; this phase introduces no caller or persistence path.

Planning-time guard migration: append reminders.py to the critical registry and Phase 2n product_critical list. Update only frozen fingerprints for the authorized AGENTS.md/registry changes and their dependent manifests, in tooling_boundary, product_support, product_consolidation, product_organization order; in the last, update manifest.after_sha256 to the newly committed Phase 2p manifest. Preserve before_sha256 as historical, every map/body/selector/document pin, frozen key count and all unrelated values. These edits are given files, not permission for the coder to regenerate guards.

## Requirements

1. **Public representation:** implement the exact constant, frozen two-field record and typed plan_reminders signature above in reminders.py. Return a tuple whose elements are PlannedReminder with canonical UTC instants. Given: representation/constants and all plan cases.
2. **Warnings and deadline:** implement the exact one-hour branch, strict-future due_soon branch and original due instant. Preserve microseconds; never emit both warning kinds or a due-soon message for an already-due task. Given: ordinary, exact-hour, one-microsecond-under, due-soon, due-now and overdue cases.
3. **Finite late schedule:** include exactly the seven original elapsed offsets for every active deadline, without filtering already-past slots or adding an endless sequence/digest. Given: literal complete plans, the decided offsets and past-all-late case.
4. **Work and task state:** add original start independently of deadline. Suppress everything for done/cancelled, retain deadline reminders for in_progress, and return empty for active undated/unplanned work. Sort by instant and the specified tie order, without coalescing. Given: all state/no-deadline/work/tie/past-work cases.
5. **Time and refusal policy:** enforce canonical now before terminal-state handling; use existing DeadlineError/message with no chained data. Perform offsets in elapsed UTC time across DST and date-only inputs, independent of display/work zone. Given: six invalid-now cases, two DST checks and complete DST/date-only plans. Coder writes representable-range checks below.
6. **Purity and repeatability:** no clock/ID/settings read, I/O, store access, mutation, sending or global state. No task approval/state operation is introduced. Repeated identical inputs return equal immutable plans with no output. Existing task creation and HTTP/CLI behaviour stay unchanged because no caller is added. Given: repeated planning with clock/ID/settings/SQLite/Store traps and unchanged input assertions. Actual restart, claim and send retry tests belong to the durable integration; no delivery claim is made here.
7. **Critical coverage and preserved guards:** reminders.py joins the product 100% line/branch gate; keep separate 100% tooling and overall 90%. Preserve all earlier tests and given guard migrations exactly. No dependency, skipped test, coverage exclusion or tooling cleanup. Given: committed registry/manifests, full checker and the probe.

8. **Progress entry** for `## Phase 3a: Deterministic reminder planning (YYYY-MM-DD)` at the end of `docs/progress.md`.

## Given files

Already committed with this spec; never change them.

| File | What it is |
|---|---|
| `tests/reminder_plan_cases.json` | 19 literal whole-plan examples, including both DST changes |
| `tests/reminder_cases.py` | Synthetic task builder and result projection; no computed expected answers |
| `tests/unit/test_reminder_plans.py` | 30 tests from 6 functions (requirements 1–6) |
| `scripts/critical_modules.txt` | Given append of reminders.py to the existing product critical list |
| `tests/tooling_boundary_manifest.json` | Given product_critical append only |
| `tests/product_support_manifest.json` | Given authorized registry/dependent-manifest fingerprint migration only |
| `tests/product_consolidation_manifest.json` | Given authorized policy/registry/dependent-manifest fingerprint migration only |
| `tests/product_organization_manifest.json` | Given dependent frozen fingerprints and current Phase 2p result fingerprint only |
| `docs/verification/probe-03a.py` | The verifier's probe |

Given test count: **30** (6 functions). Empty-module baseline: 30 missing-name failures. Names-only stub: 28 NotImplementedError failures and 2 representation/constant guards.

## Tests to write

Write tests/unit/test_reminder_plan_edges.py using synthetic Task values and explicit UTC instants:

- A terminal task and an active undated task at datetime.max with tzinfo UTC return (); neither attempts warning/late arithmetic.
- A valid deadline at datetime.max with now one day earlier raises standard OverflowError when a late slot cannot be represented; no clipping or input mutation.
- Plan again after an approved snapshot change via dataclasses.replace: same task ID with a changed deadline/work value must not reuse a cached plan. Use literal expected warning/start instants. No database or live service.

Use this behaviour filename rather than another generic continuation. Add only meaningful additional checks needed for uncovered branches; never modify givens or production code outside Scope.

## Scope

| Path | Change |
|---|---|
| `src/docket/reminders.py` | create |
| `tests/unit/test_reminder_plan_edges.py` | create |
| `docs/progress.md` | append your entry |

## Out of scope

- Durable reminders/migrations, Store/core wiring, ID generation, claims, sending, fake/live notifier APIs, loop/service commands, catch-up coalescing, snooze, digest/proposals, Discord cards/buttons, calendar integration, type checker and test cleanup. These are not hidden requirements of this pure phase.
- Any change to a given file, `AGENTS.md` or the design docs.

## Rules that bite

- Pure deterministic planning: use only supplied task/time, preserve all approval/state boundaries, read no real data/accounts/Keychain, and call no service. No clock/IDs/settings/files/store/network reads in this module, and no title/error output. No dependency installs or existing source/test edits.
- **Time through the module**: `clock.now()`, never `datetime.now()`, and never `from docket.clock import now`.
- If you stop before finishing, still write the progress entry with a `Stopped:` first follow-up (`docs/phase-conventions.md`, "When you stop").
- Commands start with `.venv/bin/python`; no bare `python3`, `pytest` or `ruff`.

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_reminder_plans.py` (before you start) | `1349 passed` |
| `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1379 passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest tests/unit/test_reminder_plans.py --no-cov -q` | `30 passed` |
| `.venv/bin/python -m coverage report --include=src/docket/reminders.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| `.venv/bin/python docs/verification/probe-03a.py` | last line `FAILURES 0` |
| `grep -c "^## Phase 3a: " docs/progress.md` | `1` |
| `.venv/bin/python scripts/check_reports.py --phase 3a` | `Reports OK.` |
| `git diff HEAD --stat -- tests/reminder_plan_cases.json tests/reminder_cases.py tests/unit/test_reminder_plans.py scripts/critical_modules.txt tests/tooling_boundary_manifest.json tests/product_support_manifest.json tests/product_consolidation_manifest.json tests/product_organization_manifest.json docs/verification/probe-03a.py` | no output |
| `git status --short` | only the Scope paths |

### Searches

Each prints nothing.

```zsh
git grep --untracked -n -E 'import (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)|from (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)' -- src
git grep --untracked -n -E 'print\(|logging|logger|warnings\.warn' -- src ':!src/docket/cli.py'
git grep --untracked -n -E 'datetime\.now|datetime\.utcnow|date\.today|time\.time\(|from docket\.(clock|ids) import' -- src ':!src/docket/clock.py'
git grep --untracked -n -E '\.(insert_task|update_task|append_audit|insert_link|insert_request_key)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'
git grep --untracked -n -E 'ollama|anthropic|openai|langchain' -- src
git grep --untracked -n -E 'pragma: no cover|noqa' -- src/docket/reminders.py
git grep --untracked -n -E 'clock\.now\(|ids\.new_id\(|get_settings\(|os\.environ|getenv\(|open\(|connect\(|Store\(|localtime\(|astimezone\(|time\.sleep\(' -- src/docket/reminders.py
```
