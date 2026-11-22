# Phase 5e: Isolated reminder passes

## Goal

Stop one bad row from silencing every reminder (audit finding 4), and stop an emptied digest from being sent (finding 10's empty-digest race). Today `send_due` queues and claims every task's post in one transaction, so a single reminder, post or task row that fails to decode rolls back the whole half and no task is reminded, pass after pass. After this phase each task is queued and claimed in its own transaction; a task whose rows raise `StoreError` is skipped, named in the pass result, and every other task is sent as before. A claimed digest whose every task ended before it was read is marked sent without calling the notifier. The loop's stored status and failure counts are Phase 5f.

Sections: `core`. The `tooling` section runs in the full check.

Follow `docs/phase-conventions.md`. N is 1936, the tests the previous phase left passing.

Start: `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_isolated_passes.py` must show `1936 passed`. The ignored file is this phase's new given test file.

## Facts

- `reminders.send_due(store, notifier) -> int` (line 19) opens one `store.transaction()` (lines 21-39): it reads `store.due_reminders(now)`, groups the rows by task, calls `store.queue_post` once per task with a key from `ids.new_id()`, and then `store.claim_posts(at=now, stale_before=now - 5 minutes)` for every task. After the transaction it sends each claimed post in post-number order, reading `store.task(post.task_id)` for its title; a `NotifierError` releases the post, any other send marks it sent.
- A row that fails to decode raises `StoreError("invalid stored <label>: <id>")`. A naive time in a reminder's `planned_at`, a post's `queued_at` or a task's `created_at` does so, and the `ROLLBACK` in `Store.transaction` (line 245) undoes every task's post with it.
- `Store.transaction` refuses to nest (`StoreError(NESTED_MESSAGE)`), so a savepoint inside the one transaction is not available without changing it.
- `run_pass` (line 132) calls `send_due` and `send_digest`, each in `except Exception`, and returns `PassResult(sent, digest, failed)`; `failed` holds `"reminders"` and/or `"digest"`. `PassResult` is a frozen dataclass with those three fields.
- `send_digest` (line 70) claims the day's digest, re-reads its tasks, keeps those still open and past their last late reminder, and calls `notifier.send_digest` even when none is left (`lines == ()`).
- `store.due_reminders(at)` (store.py line 618) reads `_store_reminders.select_due_reminders(connection, at)` (line 42), `ORDER BY task, fire_at, number`. `store.claim_posts(*, at, stale_before)` (line 678) runs `_store_posts.claim_posts(connection, at, stale_before)` (line 27), which claims every unsent post that is unclaimed or claimed before `stale_before` and still holds a live reminder.
- `send_due` is called 22 times in the tests (`test_reminder_sending.py`, `test_reminder_sending_edges.py`, `tests/notifier_cases.py`) and by `docs/verification/probe-03c.py`, all through its two-argument signature and its `int` answer.
- `tests/integration/test_reminder_loop.py::test_the_loop_names_and_result_contract` pins `PassResult`'s fields as exactly `["sent", "digest", "failed"]`.
- A throwaway draft added 86 lines and deleted 41 in four modules (`reminders` 39 and 26, `_store_posts` 25 and 8, `store` 16 and 4, `_store_reminders` 6 and 3). With it, the full suite passed (1945) and every `docket` module was covered at 100% with branches.

## Owner's decisions

- **Split (2026-11-22):** the audit's 5e row is two phases. 5e isolates each task's pass and fixes the empty digest; 5f stores the last pass result and each half's consecutive-failure count for `docket status`. The service moves to 5g.
- **Status store (2026-11-22, for 5f):** a one-row `loop_status` table, written by `run_loop`, in one migration.
- **A skipped task counts (2026-11-22, for 5f):** a pass that skips any task is a failing pass for its half, and the skipped ids are recorded. In this phase a skip is only named in `PassResult.skipped`; `failed` keeps its meaning.

## Architect's decisions

- **One transaction per task, not a savepoint.** `Store.transaction` stays as it is.
- **Only `StoreError` skips a task.** Any other exception still propagates out of `send_due`, so `run_pass` fails the whole reminders half, as today: a bug must stay loud, and a skip is for a bad row.
- **Which tasks a pass visits.** `Store.pending_task_ids` lists the tasks with a due unclaimed reminder or a claimable post, from the row numbers alone, so it never decodes a stored time and cannot fail on a bad row.
- **Send order stays by post number.** Each task's claimed posts are gathered first, then sent in post-number order, so on sound rows a pass sends exactly what today's code sends, key for key.
- **`send_due` keeps its signature and its `int` answer.** `run_pass` reads the skipped ids through a private helper the coder names.
- **A retry key drawn for a task that is then skipped is lost**, never stored; the next pass draws a new one. Keys are not reused across a rollback.
- **The digest is not isolated.** One bad task row still fails the digest half, as today; a given test pins that.
- **`PassResult.skipped` defaults to `()`**, so a three-argument `PassResult(...)` still builds. The given edit to `test_reminder_loop.py` pins the first three fields; the new file pins all four.

## Requirements

1. **Pending tasks.** `Store.pending_task_ids(self, *, at: datetime, stale_before: datetime) -> list[str]` answers, in task-number order and each once, the open or ended tasks that have a reminder due by `at` (unclaimed, unsent, not voided) or a post `claim_posts` would claim at `at` with `stale_before`. It decodes no stored time, so a row with a bad time still names its task.
2. **Narrowed reads.** `Store.due_reminders(self, at: datetime, *, task_id: str | None = None) -> list[Reminder]` and `Store.claim_posts(self, *, at: datetime, stale_before: datetime, task_id: str | None = None) -> list[Post]` read or claim only that task's rows when `task_id` is given, and every task's otherwise, exactly as today. An unknown `task_id` raises the store's unknown-task `StoreError`.
3. **One transaction per task.** `send_due` visits each task of `pending_task_ids(at=now, stale_before=now - CLAIM_MINUTES)`; for each it opens one transaction that reads the task's due reminders, queues its post if any is due (the same key, kind and missed count as today), claims the task's posts and reads the task.
4. **A bad row skips only its task.** When that transaction raises `StoreError`, it rolls back, the task is skipped for this pass, and the pass goes on to the next task. Any other exception propagates out of `send_due`.
5. **Sending.** After every task is visited, the claimed posts are sent in post-number order, exactly as today: a `NotifierError` releases the post; any other send marks it sent. `send_due(store, notifier) -> int` still answers the posts sent.
6. **Pass result.** `PassResult` gains a fourth field, `skipped: tuple[str, ...] = ()`, after `failed`. `run_pass` puts the ids `send_due` skipped there, in the order they were visited. `failed` keeps its meaning: a half that raised.
7. **Emptied digest.** When `send_digest` has claimed a digest and none of its tasks is left to list, it marks the digest sent at `now` in a transaction, calls no notifier, and answers `False`. A later call that day sends nothing.
8. **Same answers.** With every row sound, the notices, keys, digests, pass results' first three fields and stored rows are those of the spec commit's code. No message, public signature (beyond requirements 1, 2 and 6), schema or reminder time changes. Every existing test passes, with the one given edit to `tests/integration/test_reminder_loop.py`.
9. **Given markers**: `tests/integration/test_isolated_passes.py` carries 8 strict `xfail` markers with reasons starting `Phase 5e given test: remove this marker`, one line each. Delete all 8 once requirements 1 to 8 are done, and nothing else in the file. A strict marker on a passing test fails the run, so `check.py` tells you when.
10. **Progress entry** for `## Phase 5e: Isolated reminder passes (YYYY-MM-DD)` at the end of `docs/progress.md`.

## Given files

Already committed with this spec; never change them, except the markers of requirement 9.

| File | What it is |
|---|---|
| `tests/integration/test_isolated_passes.py` | Tests that one bad row silences only its task (list below) |
| `tests/integration/test_reminder_loop.py` | Edited: the field pin checks the first three `PassResult` fields |
| `docs/verification/probe-05e.py` | The verifier's probe |

The given tests check that:

- a bad reminder row, a bad task row and a bad post row each silence only their task, which `skipped` names, while the other tasks are sent, and that the task is sent once its row is voided;
- a bad task row still fails the digest half;
- an unexpected exception (`SyntheticBug`) fails the whole reminders half and sends nothing;
- the send order stays by post number (a guard that passes today);
- `pending_task_ids` names a task whose reminder row has a bad time, and a task whose post can be claimed again;
- `due_reminders` and `claim_posts` narrow to one task;
- a digest whose task ended after the claim is marked sent with no send, and is not sent again;
- `PassResult`'s fields are `sent`, `digest`, `failed`, `skipped`, and `skipped` defaults to `()`.

Given test count: **9** new (`test_isolated_passes.py`: 9 functions, 9 tests). Before you start, the file shows 8 xfailed and 1 passed: `test_the_send_order_stays_by_post_number` guards behaviour that must not change. The edit to `test_reminder_loop.py` adds no test.

## Tests to write

None are required: the given tests, the existing reminder, digest and loop tests, and the probe cover requirements 1 to 8 and every line and branch of the draft. If a helper you add has a branch they miss, cover it in a new `tests/integration/test_isolated_passes_more.py`, never by changing a given test.

## Scope

| Path | Change |
|---|---|
| `src/docket/reminders.py` | edit: requirements 3 to 7 |
| `src/docket/store.py` | edit: requirements 1 and 2 |
| `src/docket/_store_posts.py` | edit: requirements 1 and 2 |
| `src/docket/_store_reminders.py` | edit: requirement 2 |
| `tests/integration/test_isolated_passes.py` | delete the 8 markers only |
| `tests/integration/test_isolated_passes_more.py` | create, only if you need it |
| `docs/progress.md` | append your entry |

## Out of scope

- Storing the last pass result or failure counts, `docket status`, and any migration (Phase 5f).
- Isolating the digest's task reads.
- Any change to `Store.transaction`, `run_loop`, the notifier, the schema or a reminder rule.
- Any change to a given file beyond the markers, `AGENTS.md` or the design docs.

## Rules that bite

- **Nothing without approval / no timeout changes**: a skipped task is left exactly as it was; nothing is voided, ended or rewritten because a row failed.
- **Everything is retry-safe**: every post is still queued and claimed in a transaction before it is sent, and a skipped task's post is queued on a later pass with a new key.
- **Code decides everything**: with sound rows the probe compares every notice, key, digest and row with the spec commit's.
- **Error messages are constant text**: `StoreError`'s words are unchanged; `skipped` holds task ids only.
- **Critical modules**: all four modules in Scope are critical; every line and branch is covered, with no `pragma: no cover`.
- If you stop before finishing, still write the progress entry with a `Stopped:` first follow-up (`docs/phase-conventions.md`, "When you stop").
- Commands start with `.venv/bin/python`; no bare `python3`, `pytest` or `ruff`.

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_isolated_passes.py` (before you start) | `1936 passed` |
| `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1945 passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest tests/integration/test_isolated_passes.py --no-cov -q` | `9 passed` |
| `.venv/bin/python -m coverage report --include=src/docket/reminders.py,src/docket/store.py,src/docket/_store_posts.py,src/docket/_store_reminders.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| `.venv/bin/python docs/verification/probe-05e.py` | last line `FAILURES 0` |
| `grep -c "^## Phase 5e: " docs/progress.md` | `1` |
| `.venv/bin/python scripts/check_reports.py --phase 5e` | `Reports OK.` |
| `git diff HEAD --stat -- docs/verification/probe-05e.py tests/integration/test_reminder_loop.py tests/loop_cases.py tests/notifier_cases.py tests/support.py tests/conftest.py tests/sections.toml docs/reviews AGENTS.md pyproject.toml scripts/check.py scripts/critical_modules.txt scripts/tooling_modules.txt src/docket/schema.py src/docket/core.py src/docket/notifier.py src/docket/cli.py` | no output |
| `git diff HEAD --numstat -- tests/integration/test_isolated_passes.py` | `0	8	tests/integration/test_isolated_passes.py` (the markers, nothing else) |
| `git status --short` | only the Scope paths |

### Searches

Each prints nothing.

```zsh
git grep --untracked -n -E 'import (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)|from (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)' -- src
git grep --untracked -n -E 'print\(|logging|logger|warnings\.warn' -- src ':!src/docket/cli.py'
git grep --untracked -n -E 'datetime\.now|datetime\.utcnow|date\.today|time\.time\(|from docket\.(clock|ids) import' -- src ':!src/docket/clock.py'
git grep --untracked -n -E 'pragma: no cover|noqa' -- src/docket/reminders.py src/docket/store.py src/docket/_store_posts.py src/docket/_store_reminders.py
git grep --untracked -n -i -E 'savepoint|release savepoint' -- src
git grep --untracked -n -E 'except (KeyError|ValueError|LookupError|sqlite3\.)' -- src/docket/reminders.py
```
