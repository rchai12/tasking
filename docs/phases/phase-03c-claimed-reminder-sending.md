# Phase 3c: Claimed reminder sending

## Goal

Send the durable Phase 3b reminder rows exactly once through a notifier. One loop pass groups each task's due reminders into one keyed post, claims it, hands a fixed-text notice to the notifier, and records the send. A pass that fails retries on the next pass with the same key. A pass that crashes mid-send retries after the five-minute claim expires. Reminders that came due while docket was down go out as one status message per task. Two loops never send the same post twice. This phase sends only through the given `Notifier` interface and the tests' fake. The shared Discord service's client and cards are Stage 4, the 30-second `docket run` loop and alerts are Stage 5, and the 07:00 digest is Phase 3d.

Sections: `core`. The `tooling` section runs in the full check.

Follow `docs/phase-conventions.md`. N is 1472, the tests the previous phase left passing.

Start: `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_reminder_sending.py --ignore=tests/integration/test_post_store_contracts.py` must show `1472 passed`. The ignored files import names you create.

## Facts

Checked 2026-11-18 against fb09266 (Phase 3b PASS, 1472 tests):

- The project's SQLite is 3.54.1, so `UPDATE ... RETURNING` is available. Stored instants are `isoformat(timespec="microseconds")` UTC text of fixed width, so comparing them as text orders them. `Store.transaction()` opens `BEGIN IMMEDIATE`, so two loops' write transactions run one after the other.
- Phase 3b's `Store.void_reminders` voids every row with no sent time, claimed rows included, so Done or Cancel after a claim leaves the claimed post with no live reminder.
- The planner keeps slots that are already past at planning time. A task created at 16:00 with a deadline at 13:00 gets rows at 13:00, 13:30, 14:00, 15:00 and 16:00, each with `fire_at <= planned_at`. Those are the slots the owner decided are not "missed".
- Phase 3b's `test_normal_reminder_sql_uses_only_the_supplied_connection_module` requires every `INSERT`, `UPDATE` and `SELECT ... FROM reminders` to run from `docket._store_reminders`. This phase's reminder SQL (the due query, the pending check, the claim mark and the sent mark) therefore goes there. Post SQL goes in the new `docket._store_posts`.
- `store.py` is frozen structurally since 3b (its 86 old nodes, signatures and imports). New methods, records and helpers are allowed, and no old node changes in this phase. `reminders.py` and `_store_reminders.py` are not frozen. `views.py`, `domain.py`, `tests/fakes.py` and `tests/support.py` are byte-frozen, so this phase changes none of them: the notice texts live in `reminders.py`, and the fake notifier lives in the new `tests/notifier_cases.py`.
- Given migration 5 moved every current-version pin from 4 to 5. That is 14 assertions across 12 earlier test, helper and probe files, plus one foreign-key observation, which gains two `(4, 1)` entries because migration 5 has two `CREATE TABLE` statements. Historical pins stay put: failed upgrades at 2, the reference rebuild at 3, 3b's refused upgrade at 3, and the unsupported version at 99. Node IDs are unchanged. The manifests' byte and AST pins for those files were moved by the architect's `rehash.py`, and nothing else in them changed.
- The given suite is 80 cases from 18 functions. On today's code, 65 fail for the missing behaviour and the 15 given-schema guards pass. On names-only stubs, 63 fail and 17 pass: the 15 schema guards plus the two names tests. No sender was built while specifying.

## Owner's decisions

Decided 2026-11-18:

- **Catch-up.** When one pass finds two or more due reminders for a task, they go out as one status message and all of them are marked sent. A single due reminder goes out normally, however late. Not chosen: a time threshold (2 minutes late), or sending only the newest with no mention of the rest.
- **Status wording.** `Missed while docket was offline: N reminders.`, a line break, then the newest due reminder's normal line. Not chosen: naming the current phase, or a bare catch-up prefix.
- **Already-past slots.** Only reminders that came due after they were planned count as missed (`fire_at > planned_at`). A task created or reopened after its deadline gets one normal line, and its older slots are marked sent with it silently. Not chosen: counting them all, or a separate "added after its deadline" line.
- **Retry.** A send the notifier refuses is retried on every pass with the same persisted key. Not chosen: backoff to 5 minutes. The 15-minute local alert stays in Stage 5.

## Architect's decisions

**Schema.** Given `MIGRATION_5` creates `posts` (number, task, unique key of 1 to 200 characters, the newest reminder's kind, a missed count of zero or more, queued_at, nullable claimed_at and sent_at) and `post_reminders` (post, reminder). Each reminder appears in at most one post (`UNIQUE`). Triggers refuse deleting posts or links, and refuse changing a post's number, task, key, kind, missed or queued_at, or any link. No title, text, payload or calendar data is stored. Migrations 1 to 4 are unchanged.

**Store public additions** (`docket.store`). A frozen `Post` record has fields in this order: `id: str` (`p<number>`), `task_id: str`, `key: str`, `kind: str`, `missed: int`, `reminder_ids: tuple[str, ...]` (ordered by reminder number), `queued_at: datetime`, `claimed_at: datetime | None` and `sent_at: datetime | None`. Every instant argument must be canonical UTC, or the existing `StoreError("an instant must be in UTC")` is raised. Every write method first requires the existing write guard (`StoreError("a write needs a transaction")`). Each validates everything before any SQL change. Each reads no clock and no id, and opens no transaction of its own.

- `Store.due_reminders(at: datetime) -> list[Reminder]`: rows with `fire_at <= at` and no claimed, sent or voided time, ordered by task number, then fire_at, then reminder number. It is a read, so it needs no transaction.
- `Store.queue_post(task_id: str, reminder_ids: tuple[str, ...], *, key: str, kind: str, missed: int, at: datetime) -> Post`. Checks run in this order: the write guard and UTC; the task exists (`unknown task`); the key is a `str` of 1 to `domain.REQUEST_KEY_MAX` characters (`invalid post key`); the kind is in `domain.REMINDER_KINDS` (`invalid reminder kind`); `missed` is an `int`, not a `bool`, from 0 to the number of ids (`invalid missed count`); the ids are not empty (`a post needs a reminder`); each id is `r<digits>` (`invalid reminder id`); and each is a pending reminder of that task, not already listed earlier in the same tuple (`reminder not pending: r<n>`). It then inserts the post and its links, sets each reminder's claimed_at to `at`, and returns the new `Post` with no claimed or sent time.
- `Store.claim_posts(*, at: datetime, stale_before: datetime) -> list[Post]`: one `UPDATE ... RETURNING` sets claimed_at to `at` on every post that is unsent, has no claim or a claim strictly before `stale_before`, and still has at least one unvoided reminder. It returns those posts ordered by number.
- `Store.release_post(post_id: str, *, claimed_at: datetime) -> None`: clears the claim only when the post is unsent and its claimed_at equals `claimed_at`. Otherwise it changes nothing.
- `Store.mark_post_sent(post_id: str, *, at: datetime) -> None`: sets the post's sent_at to `at`, and the sent_at of its unvoided, unsent reminders to `at`, only when the post is unsent. A repeat changes nothing, and it does not require a claim. For both of these methods, an unknown or malformed post id raises `StoreError("unknown post")`.
- `Store.posts(task_id: str) -> list[Post]`: the task's posts ordered by number, `[]` for an unknown or malformed task id. A stored post time that is unparseable, naive or not UTC raises `StoreError("invalid stored post time: p<n>")`, with no chained exception and no partial result.

**SQL boundary.** `docket._store_posts` holds the ordinary post SQL. Its functions take `connection: sqlite3.Connection` first, and the module imports nothing from `docket`. It calls no `connect`, `close`, `commit`, `rollback`, `cursor`, `executescript`, `now`, `new_id`, `isoformat` or `fromisoformat`, and runs no `BEGIN`, `COMMIT`, `ROLLBACK` or `PRAGMA`. The reminder SQL this phase needs goes in `docket._store_reminders` under the same rules. Store owns validation, encoding, ids and record conversion. The function names in both modules are yours.

**Engine** (`docket.reminders`). `CLAIM_MINUTES = 5`. `notice_text(kind: str, missed: int) -> str` returns the kind's line (`start` "Time to start.", `before` "Are you working on this?", `due_soon` "This is due soon.", `due` "This is now due.", `late` "This is late."). When `missed >= 2` it prefixes `Missed while docket was offline: {missed} reminders.` and a line break. `send_due(store: Store, notifier: Notifier) -> int` makes one pass:

1. Read `clock.now()` once. This pass uses no other time.
2. In one transaction: `due_reminders(now)`. For each task, in that order, queue one post of all its due rows, with `key=ids.new_id()` (one call per post), `kind` the last row's kind, and `missed` the number of rows with `fire_at > planned_at`. Then `claim_posts(at=now, stale_before=now - CLAIM_MINUTES)`.
3. For each claimed post, in order: build `Notice(post.key, post.task_id, store.task(post.task_id).title, notice_text(post.kind, post.missed))` and call `notifier.send`. On `NotifierError`, release the claim (`claimed_at=now`) in its own transaction and go on to the next post. On success, mark the post sent at `now` in its own transaction. Any other exception propagates at once and leaves the claim to expire.
4. Return the number of posts marked sent.

**Notifier.** The given `docket.notifier` defines `Notice(key, task_id, title, text)`, `NotifierError` and the `Notifier` protocol (`send(notice) -> None`, delivering once per key). Stage 4 implements it with the shared Discord service's keyed request and renders the title in a code block. This phase adds no implementation. A notice carries only the key, the task id, the plain-text title and fixed text.

## Requirements

1. **Post storage:** implement `Post` and the six Store methods exactly as above, with their validation order and fixed refusals, no partial writes, and the stored-time refusal. Given: the record and table shapes, one round trip across a restart, 25 refusal cases, six claim-selection cases, 15 schema guards and 9 corrupt-time cases.
2. **SQL ownership:** create `_store_posts` for post SQL and add the reminder SQL to `_store_reminders`, both on the supplied connection, with write SQL only inside a transaction. Given: the AST rules and observed callers, on one connection.
3. **Notice text:** `CLAIM_MINUTES` and `notice_text` exactly as above. Given: seven literal texts and the names test.
4. **One pass:** `send_due` as above. Deadlines 1, 2 and 3 minutes out fire in order. A work-time start fires once. Reminders that came due while down become one status message with the owner's wording. Already-past slots are not counted as missed (created, reopened and mixed cases). Given: literal notices, posts and reminder times. The test's `fixed_times` and `fixed_ids` lists give exactly one clock read per pass and one id per new post.
5. **Retry safety:** a `NotifierError` is retried on the next pass with the same key. A crash before or after delivery, or an unexpected error, is resent once with the same key only after the claim is more than five minutes old, including across a restart. Given: one retry test and three crash cases.
6. **Never twice:** a second loop that runs while the first is sending sends nothing, and two processes passing together send each post once. Given: one interleaved test and one spawned-process test.
7. **Ended tasks:** a post whose reminders were all voided (Done or Cancel after a crashed claim) is never sent. Given: two cases.
8. **Least data out, no task change:** a pass changes no task, audit row, link or request key, and sends only `Notice` fields. Given: the table snapshot in the catch-up test.
9. **Progress entry** for `## Phase 3c: Claimed reminder sending (YYYY-MM-DD)` at the end of `docs/progress.md`.

## Given files

Already committed with this spec; never change them.

| File | What it is |
|---|---|
| `src/docket/schema.py` | Given append-only `MIGRATION_5` (`posts`, `post_reminders`); migrations 1 to 4 unchanged |
| `src/docket/notifier.py` | Given `Notice`, `NotifierError` and the `Notifier` protocol |
| `scripts/critical_modules.txt` | Given append of `_store_posts.py` |
| `tests/notifier_cases.py` | Given `FakeNotifier`, `Killed`, `SyntheticBug`, time helpers and the spawned sender |
| `tests/integration/test_reminder_sending.py` | 22 tests from 11 functions: names, texts, passes, catch-up, retries, crashes, loops, ended tasks |
| `tests/integration/test_post_store_contracts.py` | 58 tests from 7 functions: record, round trip, refusals, claims, schema, stored times, SQL ownership |
| `tests/integration/test_audit_link_key_contracts.py` | Earlier given: current version 4 becomes 5 only |
| `tests/integration/test_reference_coverage.py` | Earlier given: current version 4 becomes 5 only |
| `tests/integration/test_reference_migration.py` | Earlier given: current version 4 becomes 5 only |
| `tests/integration/test_reminder_storage_edges.py` | Phase 3b coder's file: current version 4 becomes 5 only |
| `tests/integration/test_server.py` | Earlier given: current version 4 becomes 5 only |
| `tests/integration/test_store.py` | Earlier given: current version 4 becomes 5 only (two assertions) |
| `tests/integration/test_store_coordination.py` | Earlier given: current version 4 becomes 5 only, and the foreign-key list gains `(4, 1), (4, 1)` |
| `tests/integration/test_store_links.py` | Earlier given: migration count and current version 4 become 5 only |
| `tests/integration/test_store_safety_coverage.py` | Earlier given: the planted-3 case now ends at 5 |
| `tests/startup_cases.py` | Earlier given: the current-version helper case 4 becomes 5 |
| `docs/verification/probe-02g.py` | Earlier given: current version 4 becomes 5 only |
| `docs/verification/probe-02i.py` | Earlier given: current version 4 becomes 5 only |
| `docs/verification/probe-03b.py` | Earlier given: its schema-version oracle line 4 becomes 5 only |
| `tests/product_consolidation_manifest.json` | Given pin moves for the files above; no case, selector or unrelated hash change |
| `tests/product_organization_manifest.json` | Given pin moves for the files above; no case, selector or unrelated hash change |
| `tests/product_support_manifest.json` | Given pin moves for the files above; no case, selector or unrelated hash change |
| `tests/tooling_boundary_manifest.json` | Given `_store_posts.py` added to `product_critical`; no other change |
| `docs/verification/probe-03c.py` | The verifier's probe |

Given test count: **80** (18 functions): `test_reminder_sending.py` 22 tests from 11 functions, `test_post_store_contracts.py` 58 tests from 7 functions. On today's code 65 fail and 15 pass (the schema guards).

## Tests to write

Write `tests/integration/test_reminder_sending_edges.py` with synthetic inputs and literal outcomes:

- A pass with nothing due returns 0, consumes no id and still claims a stale post.
- A post whose reminders were partly voided after queueing (a deadline edit after a crash) is still sent with its stored kind and missed count, and only its unvoided reminders get a sent time.
- A NotifierError on the first of two claimed posts still sends the second in the same pass.
- The title in a resent notice is the task's title at the time of the resend.
- Any line or branch of `_store_posts`, the new `_store_reminders` functions, the new Store methods or `send_due` that the given tests leave uncovered.

Use this file name, not a generic `_more` file. Do not repair a given test or widen a freeze to make a test pass.

## Scope

| Path | Change |
|---|---|
| `src/docket/_store_posts.py` | create |
| `tests/integration/test_reminder_sending_edges.py` | create |
| `src/docket/store.py` | edit: `Post` and the six methods; no change to an existing node |
| `src/docket/reminders.py` | edit: `CLAIM_MINUTES`, `notice_text`, `send_due`; the planner unchanged |
| `src/docket/_store_reminders.py` | edit: add the due, pending, claim and sent SQL; the three 3b functions unchanged |
| `docs/progress.md` | append your entry |

## Out of scope

- The shared Discord service's client, cards, buttons, channels, presses or any HTTP call; a real `Notifier`.
- A loop runner, `docket run`, a sleep or timer, a CLI or API command that sends, `docket status`, the 15-minute alert, backoff, the digest, snooze, calendar holds, pruning.
- Changing the planner, `core`, a Phase 3b method, `views.py`, `domain.py`, `tests/fakes.py`, `tests/support.py` or any old `store.py` node.
- Any change to a given file, `AGENTS.md` or the design docs.

## Rules that bite

- **A reminder is never lost or sent twice.** The claim is the only thing that stops a second send. Never mark a post sent before the notifier returns, and never queue a reminder that is already in a post.
- **Ids through the module.** `ids.new_id()` once per new post, persisted as its key and reused on every attempt. Never in a Store method or a SQL module.
- **Least data out.** A notice holds the key, the task id, the title and fixed text. No deadline, link, message id or source.
- **Errors** are constant text plus a reminder or post id. Never a title or a library's exception text.
- **Time through the module**: `clock.now()`, never `datetime.now()`, and never `from docket.clock import now`.
- If you stop before finishing, still write the progress entry with a `Stopped:` first follow-up (`docs/phase-conventions.md`, "When you stop").
- Commands start with `.venv/bin/python`; no bare `python3`, `pytest` or `ruff`.

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_reminder_sending.py --ignore=tests/integration/test_post_store_contracts.py` (before you start) | `1472 passed` |
| `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1552 passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest tests/integration/test_reminder_sending.py tests/integration/test_post_store_contracts.py --no-cov -q` | `80 passed` |
| `.venv/bin/python -m coverage report --include=src/docket/_store_posts.py,src/docket/_store_reminders.py,src/docket/store.py,src/docket/reminders.py,src/docket/schema.py,docket_tools/reports.py,docket_tools/acceptance.py,docket_tools/spotcheck.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| `.venv/bin/python docs/verification/probe-03c.py` | last line `FAILURES 0` |
| `grep -c "^## Phase 3c: " docs/progress.md` | `1` |
| `.venv/bin/python scripts/check_reports.py --phase 3c` | `Reports OK.` |
| `git diff HEAD --stat -- src/docket/schema.py src/docket/notifier.py scripts/critical_modules.txt tests/notifier_cases.py tests/integration/test_reminder_sending.py tests/integration/test_post_store_contracts.py tests/integration/test_audit_link_key_contracts.py tests/integration/test_reference_coverage.py tests/integration/test_reference_migration.py tests/integration/test_reminder_storage_edges.py tests/integration/test_server.py tests/integration/test_store.py tests/integration/test_store_coordination.py tests/integration/test_store_links.py tests/integration/test_store_safety_coverage.py tests/startup_cases.py docs/verification/probe-02g.py docs/verification/probe-02i.py docs/verification/probe-03b.py tests/product_consolidation_manifest.json tests/product_organization_manifest.json tests/product_support_manifest.json tests/tooling_boundary_manifest.json docs/verification/probe-03c.py` | no output |
| `git status --short` | only the Scope paths |

### Searches

Each prints nothing.

```zsh
git grep --untracked -n -E 'import (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)|from (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)' -- src
git grep --untracked -n -E 'print\(|logging|logger|warnings\.warn' -- src ':!src/docket/cli.py'
git grep --untracked -n -E 'datetime\.now|datetime\.utcnow|date\.today|time\.time\(|from docket\.(clock|ids) import' -- src ':!src/docket/clock.py'
git grep --untracked -n -E '\.(insert_task|update_task|append_audit|insert_link|insert_request_key)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'
git grep --untracked -n -E 'ollama|anthropic|openai|langchain' -- src
git grep --untracked -n -E 'pragma: no cover|noqa' -- src/docket/_store_posts.py src/docket/store.py src/docket/reminders.py src/docket/_store_reminders.py
git grep --untracked -n -E 'ids\.new_id\(' -- src ':!src/docket/reminders.py'
git grep --untracked -n -E '\.(queue_post|claim_posts|release_post|mark_post_sent)\(' -- src ':!src/docket/reminders.py' ':!src/docket/store.py'
git grep --untracked -n -E 'send_due\(' -- src ':!src/docket/reminders.py'
git grep --untracked -n -E 'time\.sleep\(|asyncio|threading' -- src
```
