# Phase 3d: Daily digest

## Goal

Send the daily digest: once a home day, at the digest time in your zone (07:00 by default), one keyed message listing every open task that is past its last late reminder. The digest is queued once per home day with one persisted key, claimed before it is sent, retried with the same key after a refusal or a crash, and never sent twice. Tasks that ended or stopped being overdue before a retry are left out. A morning with nothing overdue sends nothing. If docket is down at 07:00, the first pass later that home day sends it, and days missed completely are skipped. This phase sends only through the given `Notifier` interface and the tests' fake. Pending proposals in the digest are Stage 10. The `DOCKET_DIGEST_TIME` setting and the 30-second `docket run` loop that calls the sender are Stage 5. The Discord card, with one Done button per line, is Stage 4.

Sections: `core`. The `tooling` section runs in the full check.

Follow `docs/phase-conventions.md`. N is 1558, the tests the previous phase left passing.

Start: `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_daily_digest.py --ignore=tests/integration/test_digest_store_contracts.py` must show `1558 passed`. The ignored files import names you create.

## Facts

Checked 2026-11-18 against 406e693 (Phase 3c PASS, 1558 tests):

- The last late reminder fires `reminders.LATE_MINUTES[-1]` (720) elapsed minutes after the deadline. "Past its last late reminder at the slot" therefore means `deadline.at + 720 minutes <= slot`, inclusive.
- `deadlines.make_deadline(day, at, zone).at` turns a home day and wall time into the UTC instant by the project's rule (`fold=0`). In `America/New_York` it gives 07:00 as 11:00 UTC on 2026-10-31 and 2027-03-14, and as 12:00 UTC on 2026-11-01. It gives 02:30 on 2027-03-14 as 07:30 UTC (the skipped hour moves forward), and 01:30 on 2026-11-01 as 05:30 UTC (the first of the repeated hour). These match the standard library.
- `views.deadline_text(deadline, home, now)` already writes the deadline text, for example `Tue Nov 17 17:00 EST` and `Wed Nov 18 09:00 EST (Wed Nov 18 23:00 JST where set)`. `views.py` is byte-frozen, so the digest's line text is built in `reminders.py` from that function.
- `config.py` is byte-frozen, so this phase adds no setting. `send_digest` takes the zone and the time from its caller.
- SQLite's `date(day) IS day` refuses `2026-02-30`, `2026-1-20`, `20261120`, `2026-11-20T00:00` and a leading space, and accepts `2026-11-20`.
- Stored instants are fixed-width microsecond UTC text, as in Phase 3c, so `tasks.deadline_at <= ?` compares instants.
- `store.py` is frozen structurally since 3b: new records, methods and helpers are allowed, and no old node changes. `reminders.py` is not frozen. The fake notifier lives in `tests/notifier_cases.py`, which no manifest pins.
- Given migration 6 moved every current-version pin from 5 to 6 in 14 earlier test, helper and probe files. The foreign-key observation in `test_store_coordination.py` gains two `(5, 1)` entries, one for each new `CREATE TABLE`, and is now formatted one entry per line. Historical pins stay put: failed upgrades at 2, the reference rebuild and 3b's refused upgrade at 3, and the unsupported version at 99. Node ids are unchanged. The architect's `rehash.py` moved the manifests' byte and AST pins for those files (33 moves), and nothing else in them changed.
- The given suite is 87 cases from 17 functions. On today's code, 71 fail for the missing behaviour and the 16 given-schema guards pass. On names-only stubs, 69 fail and 18 pass: the 16 schema guards plus the two names tests. A throwaway stand-in, deleted afterwards, passed the 33 sending, slot, round-trip and claim cases and both probe walks, so the expected values agree with one another.

## Owner's decisions

Decided 2026-11-18:

- **Empty day.** A morning with no task past its last late reminder sends nothing and stores nothing. Not chosen: a daily "Nothing overdue" message.
- **Missed 07:00.** If no pass ran at the digest time, the first pass later that same home day sends that day's digest. A home day with no pass after its slot has no digest, and an earlier day's digest is never sent on a later day. Not chosen: only within an hour of 07:00, or sending every missed day's digest on return.
- **Wording.** The heading is `Still open past their deadlines: N tasks.`, with `1 task.` for one. Each line carries the task id, its plain-text title and `Was due <deadline text>`. Not chosen: `Daily digest: N overdue tasks.`, or a heading saying the tasks no longer send reminders.
- **Retry lists.** A retry, with the same key, lists only the stored tasks that are still open and still past their last late reminder at the slot. If none is left, the digest is never sent. Not chosen: resending the list exactly as queued.

## Architect's decisions

**Schema.** Given `MIGRATION_6` creates `digests` and `digest_tasks`. `digests` holds a number, a home day that is unique and a valid `YYYY-MM-DD` date, a unique key of 1 to 200 characters, queued_at, and nullable claimed_at and sent_at. `digest_tasks` holds the digest and the task, with primary key (digest, task). Triggers refuse deleting a digest or a member, and refuse changing a digest's number, day, key or queued_at, or any member. No title, text or deadline is stored. Migrations 1 to 5 are unchanged.

**The rule.** A task is *overdue for a slot* when its state is `open` or `in_progress`, it has a deadline, and `deadline.at + timedelta(minutes=reminders.LATE_MINUTES[-1]) <= slot`. Membership, the claim and the lines all use this rule, judged at the day's slot and never at the pass's time. A task that crosses the line after 07:00 waits for the next day's digest.

**Store public additions** (`docket.store`). A frozen `DailyDigest` record has fields in this order: `id: str` (`d<number>`), `day: date`, `key: str`, `task_ids: tuple[str, ...]` (ordered by task number), `queued_at: datetime`, `claimed_at: datetime | None` and `sent_at: datetime | None`. Every instant argument must be canonical UTC, or the existing `StoreError("an instant must be in UTC")` is raised. A day argument must be a `datetime.date` that is not a `datetime`, or `StoreError("invalid digest day")` is raised. Every write method first requires the existing write guard (`StoreError("a write needs a transaction")`). Each validates everything before any SQL change, reads no clock and no id, and opens no transaction of its own.

- `Store.digest(day: date) -> DailyDigest | None`: that day's digest, or `None`. It is a read, so it needs no transaction. A stored digest time that is unparseable, naive or not UTC raises `StoreError("invalid stored digest time: d<n>")`, with no chained exception.
- `Store.queue_digest(day: date, task_ids: tuple[str, ...], *, key: str, at: datetime) -> DailyDigest`. Checks run in this order: the write guard, then UTC; the day (`invalid digest day`); the key is a `str` of 1 to `domain.REQUEST_KEY_MAX` characters (`invalid digest key`); the ids are not empty (`a digest needs a task`); then each id in turn is a well-formed task id (`invalid task id`) for a task that exists, is `open` or `in_progress`, and is not listed earlier in the same tuple (`task not open: <id>`); last, the day has no digest yet (`digest already queued: <YYYY-MM-DD>`). It inserts the digest and its members and returns it, with no claim or sent time.
- `Store.claim_digest(day: date, *, at: datetime, stale_before: datetime, overdue_before: datetime) -> DailyDigest | None`. Checks run in this order: the write guard; UTC of `at`, `stale_before` and `overdue_before`; the day. Then one `UPDATE ... RETURNING` sets claimed_at to `at` on that day's digest, but only if it is unsent, has no claim or a claim strictly before `stale_before`, and has at least one member that is `open` or `in_progress` with a deadline at or before `overdue_before`. It returns the claimed digest, or `None`.
- `Store.release_digest(digest_id: str, *, claimed_at: datetime) -> None`: clears the claim only when the digest is unsent and its claimed_at equals `claimed_at`. Otherwise it changes nothing.
- `Store.mark_digest_sent(digest_id: str, *, at: datetime) -> None`: sets sent_at to `at` only when the digest is unsent. A repeat changes nothing, and it does not require a claim. For both of these methods, an unknown or malformed digest id raises `StoreError("unknown digest")`.

**SQL boundary.** `docket._store_digests` holds the digest SQL, including the claim's join to `tasks`. Its functions take `connection: sqlite3.Connection` first, and the module imports nothing from `docket`. It calls no `connect`, `close`, `commit`, `rollback`, `cursor`, `executescript`, `now`, `new_id`, `isoformat` or `fromisoformat`, and runs no `BEGIN`, `COMMIT`, `ROLLBACK` or `PRAGMA`. Store owns validation, encoding, ids and record conversion. The function names are yours.

**Engine** (`docket.reminders`).

- `digest_slot(now: datetime, zone: str, at: time) -> tuple[date, datetime]`: the home day of `now` in `zone`, and that day's `at` as a UTC instant by `make_deadline`'s rule. It is pure, and returns today's slot even when `now` is before it.
- `digest_heading(count: int) -> str`: `Still open past their deadlines: 1 task.` for one, otherwise `Still open past their deadlines: {count} tasks.`.
- `send_digest(store: Store, notifier: Notifier, *, zone: str, at: time) -> bool` makes one pass:
  1. Read `clock.now()` once. This pass uses no other time and reads no settings. Take `day, slot = digest_slot(now, zone, at)`. If `now < slot`, return `False`.
  2. In one transaction: if `store.digest(day)` is `None`, find the tasks overdue for `slot` among `store.tasks(domain.OPEN_STATES)`. If there are any, call `queue_digest(day, their ids, key=ids.new_id(), at=now)`, one id for the day. Then call `claim_digest(day, at=now, stale_before=now - CLAIM_MINUTES, overdue_before=slot - LATE_MINUTES[-1])`.
  3. If nothing was claimed, return `False`. Otherwise build the lines from the claimed members that are still overdue for `slot`, ordered by deadline, then task number. Each line is `DigestLine(task.id, task.title, "Was due " + views.deadline_text(task.deadline, zone, now))`. Send `Digest(claimed.key, digest_heading(len(lines)), lines)` with `notifier.send_digest`.
  4. On `NotifierError`, release the claim (`claimed_at=now`) in its own transaction and return `False`. On success, mark the digest sent at `now` in its own transaction and return `True`. Any other exception propagates at once and leaves the claim to expire.

**Notifier.** The given `docket.notifier` adds `DigestLine(task_id, title, text)`, `Digest(key, heading, lines)` and the protocol method `send_digest(digest) -> None`, which delivers once per key and raises the same `NotifierError`. Stage 4 renders it as a card with one Done button per line, puts each title in a code block, and splits a long digest across cards under keys derived from the stored one. This phase adds no implementation.

## Requirements

1. **Digest storage:** implement `DailyDigest` and the five Store methods exactly as above, with their validation order, fixed refusals and no partial writes. Given: the record and table shapes, one round trip across a restart, 25 refusal cases, eight claim-selection cases, 16 schema guards and 9 corrupt-time cases.
2. **SQL ownership:** create `_store_digests` for the digest SQL on the supplied connection, with write SQL only inside a transaction. Given: the AST rules and observed callers, on one connection.
3. **Slot and heading:** `digest_slot` and `digest_heading` as above. Given: eight slot cases across both daylight-saving changes, the skipped and repeated hours, a home day behind UTC and a UTC zone, plus three headings.
4. **One a day:** `send_digest` as above. Nothing is sent before the slot. One digest at the slot lists the tasks overdue for it, in deadline order with ties by number, and leaves out the boundary-plus-one, ended, undated and future tasks. A second pass that day sends nothing, and the next day's digest has a new key. Given: literal digests and stored records. The test's `fixed_times` and `fixed_ids` allow one clock read a pass and one id a queued digest, and the settings are never read.
5. **Empty day:** nothing overdue means no message, no digest row and no id. Given: one test.
6. **Missed 07:00:** the first pass later that home day sends that day's digest, including after midnight UTC, and only the current day's digest after days away. Given: three cases.
7. **Retry safety:** a `NotifierError` is retried on the next pass with the same key. A crash before or after delivery, or an unexpected error, is resent once with the same key only after the claim is more than five minutes old. Given: one retry test and three crash cases.
8. **Live lines only:** a retry leaves out members that ended or stopped being overdue. A digest with no member still overdue (done, cancelled, a later deadline, or no deadline) is never sent. Given: one retry test and four cases.
9. **Never twice:** a second pass that runs while the first is sending sends nothing. Given: one interleaved test.
10. **Progress entry** for `## Phase 3d: Daily digest (YYYY-MM-DD)` at the end of `docs/progress.md`.

## Given files

Already committed with this spec; never change them.

| File | What it is |
|---|---|
| `src/docket/schema.py` | Given append-only `MIGRATION_6` (`digests`, `digest_tasks`); migrations 1 to 5 unchanged |
| `src/docket/notifier.py` | Given `DigestLine`, `Digest` and `Notifier.send_digest`; `Notice`, `NotifierError` and `send` unchanged |
| `scripts/critical_modules.txt` | Given append of `_store_digests.py` |
| `tests/notifier_cases.py` | `FakeNotifier.send_digest`, sharing the record and hooks with `send`; the rest unchanged |
| `tests/digest_cases.py` | Given synthetic tasks t1 to t9, the zone, the slot and the seeding helper |
| `tests/integration/test_daily_digest.py` | 26 tests from 10 functions: names, headings, slots, one a day, empty day, missed 07:00, retries, crashes, interleaving |
| `tests/integration/test_digest_store_contracts.py` | 61 tests from 7 functions: record, round trip, refusals, claims, schema, stored times, SQL ownership |
| `tests/integration/test_audit_link_key_contracts.py` | Earlier given: current version 5 becomes 6 only |
| `tests/integration/test_reference_coverage.py` | Earlier given: current version 5 becomes 6 only |
| `tests/integration/test_reference_migration.py` | Earlier given: current version 5 becomes 6 only |
| `tests/integration/test_reminder_storage_edges.py` | Phase 3b coder's file: current version 5 becomes 6 only |
| `tests/integration/test_server.py` | Earlier given: current version 5 becomes 6 only |
| `tests/integration/test_store.py` | Earlier given: current version 5 becomes 6 only (two assertions) |
| `tests/integration/test_store_coordination.py` | Earlier given: current version 5 becomes 6 only, and the foreign-key list gains `(5, 1), (5, 1)` |
| `tests/integration/test_store_links.py` | Earlier given: migration count and current version 5 become 6 only |
| `tests/integration/test_store_safety_coverage.py` | Earlier given: the planted-3 case now ends at 6 |
| `tests/startup_cases.py` | Earlier given: the current-version helper case 5 becomes 6 |
| `docs/verification/probe-02g.py` | Earlier given: current version 5 becomes 6 only |
| `docs/verification/probe-02i.py` | Earlier given: current version 5 becomes 6 only |
| `docs/verification/probe-03b.py` | Earlier given: its schema-version oracle line 5 becomes 6 only |
| `docs/verification/probe-03c.py` | Earlier given: its schema-version oracle line 5 becomes 6 only |
| `tests/product_consolidation_manifest.json` | Given pin moves for the files above; no case, selector or unrelated hash change |
| `tests/product_organization_manifest.json` | Given pin moves for the files above; no case, selector or unrelated hash change |
| `tests/product_support_manifest.json` | Given pin moves for the files above; no case, selector or unrelated hash change |
| `tests/tooling_boundary_manifest.json` | Given `_store_digests.py` added to `product_critical`; no other change |
| `docs/verification/probe-03d.py` | The verifier's probe |

Given test count: **87** (17 functions): `test_daily_digest.py` 26 tests from 10 functions, `test_digest_store_contracts.py` 61 tests from 7 functions. On today's code 71 fail and 16 pass (the schema guards).

## Tests to write

Write `tests/integration/test_daily_digest_edges.py` with synthetic inputs from `tests/digest_cases.py` and literal outcomes:

- A task whose last late reminder falls after the slot but before a later pass (deadline 20:00 EST the evening before, pass at 09:00) is not listed, and the heading counts only the others.
- A task inserted at 09:00 with a deadline two days earlier is listed by a digest first queued at 10:00 that day, when no earlier pass ran.
- A title changed between a refused send and the retry shows the new title in the retry.
- `digest_slot` for `Asia/Tokyo`, where the home day is ahead of UTC (`2026-11-19T22:00:00+00:00` is home day 2026-11-20).
- Any line or branch of `_store_digests`, the new Store methods, `digest_slot`, `digest_heading` or `send_digest` that the given tests leave uncovered.

Use this file name, not a generic `_more` file. Do not repair a given test or widen a freeze to make a test pass.

## Scope

| Path | Change |
|---|---|
| `src/docket/_store_digests.py` | create |
| `tests/integration/test_daily_digest_edges.py` | create |
| `src/docket/store.py` | edit: `DailyDigest` and the five methods; no change to an existing node |
| `src/docket/reminders.py` | edit: `digest_slot`, `digest_heading`, `send_digest`; the planner and `send_due` unchanged |
| `docs/progress.md` | append your entry |

## Out of scope

- Pending proposals in the digest, the proposal tables, or any proposal code (Stage 10).
- A `DOCKET_DIGEST_TIME` setting, a change to `config.py`, `docket run`, a loop, sleep or timer, a CLI or API command that sends, or `docket status` (Stage 5).
- The shared Discord service's client, the digest card, Done buttons, splitting a long digest, or any HTTP call; a real `Notifier` (Stage 4).
- Calling `send_digest` from `send_due`, or `send_due` from `send_digest`; snooze; quiet hours; a weekly or per-task digest; listing tasks that are only due or late.
- Changing the planner, `send_due`, a Phase 3b or 3c method, `views.py`, `domain.py`, `core.py`, `tests/fakes.py`, `tests/support.py` or any old `store.py` node.
- Any change to a given file, `AGENTS.md` or the design docs.

## Rules that bite

- **Sent once, never lost.** The claim is the only thing that stops a second send. Never mark a digest sent before the notifier returns, and never queue a second digest for a day.
- **Ids through the module.** `ids.new_id()` once per queued digest, persisted as its key and reused on every attempt. Never in a Store method or a SQL module, and never for a pass that queues nothing.
- **Days are home days.** The day and the slot come from the zone passed in, never from UTC or the machine's zone, so daylight-saving changes never move 07:00.
- **Least data out.** A digest holds the key, the fixed heading, and each line's task id, plain-text title and fixed deadline text. No link, message id, source or calendar data.
- **Errors** are constant text plus a day, task id or digest id. Never a title or a library's exception text.
- **Time through the module**: `clock.now()`, never `datetime.now()`, and never `from docket.clock import now`.
- If you stop before finishing, still write the progress entry with a `Stopped:` first follow-up (`docs/phase-conventions.md`, "When you stop").
- Commands start with `.venv/bin/python`; no bare `python3`, `pytest` or `ruff`.

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_daily_digest.py --ignore=tests/integration/test_digest_store_contracts.py` (before you start) | `1558 passed` |
| `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1645 passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest tests/integration/test_daily_digest.py tests/integration/test_digest_store_contracts.py --no-cov -q` | `87 passed` |
| `.venv/bin/python -m coverage report --include=src/docket/_store_digests.py,src/docket/store.py,src/docket/reminders.py,src/docket/schema.py,docket_tools/reports.py,docket_tools/acceptance.py,docket_tools/spotcheck.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| `.venv/bin/python docs/verification/probe-03d.py` | last line `FAILURES 0` |
| `grep -c "^## Phase 3d: " docs/progress.md` | `1` |
| `.venv/bin/python scripts/check_reports.py --phase 3d` | `Reports OK.` |
| `git diff HEAD --stat -- src/docket/schema.py src/docket/notifier.py scripts/critical_modules.txt tests/notifier_cases.py tests/digest_cases.py tests/integration/test_daily_digest.py tests/integration/test_digest_store_contracts.py tests/integration/test_audit_link_key_contracts.py tests/integration/test_reference_coverage.py tests/integration/test_reference_migration.py tests/integration/test_reminder_storage_edges.py tests/integration/test_server.py tests/integration/test_store.py tests/integration/test_store_coordination.py tests/integration/test_store_links.py tests/integration/test_store_safety_coverage.py tests/startup_cases.py docs/verification/probe-02g.py docs/verification/probe-02i.py docs/verification/probe-03b.py docs/verification/probe-03c.py tests/product_consolidation_manifest.json tests/product_organization_manifest.json tests/product_support_manifest.json tests/tooling_boundary_manifest.json docs/verification/probe-03d.py` | no output |
| `git status --short` | only the Scope paths |

### Searches

Each prints nothing.

```zsh
git grep --untracked -n -E 'import (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)|from (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)' -- src
git grep --untracked -n -E 'print\(|logging|logger|warnings\.warn' -- src ':!src/docket/cli.py'
git grep --untracked -n -E 'datetime\.now|datetime\.utcnow|date\.today|time\.time\(|from docket\.(clock|ids) import' -- src ':!src/docket/clock.py'
git grep --untracked -n -E '\.(insert_task|update_task|append_audit|insert_link|insert_request_key)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'
git grep --untracked -n -E 'ollama|anthropic|openai|langchain' -- src
git grep --untracked -n -E 'pragma: no cover|noqa' -- src/docket/_store_digests.py src/docket/store.py src/docket/reminders.py
git grep --untracked -n -E 'ids\.new_id\(' -- src ':!src/docket/reminders.py'
git grep --untracked -n -E '\.(queue_digest|claim_digest|release_digest|mark_digest_sent)\(' -- src ':!src/docket/reminders.py' ':!src/docket/store.py'
git grep --untracked -n -E 'send_digest\(' -- src ':!src/docket/reminders.py' ':!src/docket/notifier.py'
git grep --untracked -n -E 'get_settings|DIGEST_TIME|time\.sleep\(|asyncio|threading' -- src/docket/reminders.py src/docket/store.py src/docket/_store_digests.py
```
