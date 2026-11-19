# Phase 3e: Reminder loop

## Goal

Run the reminder engine as a loop: every 30 seconds, one pass sends the due reminders (`send_due`) and then the daily digest (`send_digest`). Each half of a pass fails alone, and an unexpected error never stops the loop: the next pass, 30 seconds later, tries again, and the claims from Phases 3c and 3d keep every retry from sending twice. Only a crash (`KeyboardInterrupt`, `SystemExit`, the process dying) or the caller's stop ends it. This phase also gives Stage 3's own test: deadlines 1, 2 and 3 minutes out fire in order, a work time's start reminder fires once, a restart mid-run loses nothing and sends one status message, two loops never send twice, and Done voids everything pending. The loop still sends only through the tests' fake notifier, and nothing starts it yet: `docket run`, which passes the settings and a stop on shutdown, is Stage 5.

Sections: `core`. The `tooling` section runs in the full check.

Follow `docs/phase-conventions.md`. N is 1650, the tests the previous phase left passing.

Start: `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_reminder_loop.py --ignore=tests/integration/test_reminder_engine_stage.py` must show `1650 passed`. The ignored files import names you create.

## Facts

Checked 2026-11-18 against 072bec6 (Phase 3d PASS, 1650 tests):

- `send_due` and `send_digest` each read `clock.now()` exactly once, so a pass that runs both halves reads the clock twice. Each already handles a `NotifierError` itself, by releasing its claim and returning, so a refused send is not a failed half.
- An unexpected exception from the notifier inside either half leaves its claim committed. The 5-minute claim expiry (`CLAIM_MINUTES`) then resends it with the same key, so the loop can try again without sending twice.
- `threading.Event` has `is_set()` and `wait(timeout)`, and `wait` returns `True` once the event is set (Python 3.12's `threading` module). An event therefore fits the `Stop` protocol below, and Stage 5 can stop the loop from a signal handler without a sleep.
- `tests/support.fixed_times` raises `StopIteration` when its moments run out. That is an `Exception`, which the loop must catch, so a loop test using it would hide a broken path. The given tests use `tests/loop_cases.Ticker` instead: one object that is the clock and the stop, and moves the clock on only inside `wait`.
- `core.create_task` plans a `due_soon` reminder at its own instant for a deadline less than an hour out. That is why deadlines 1, 2 and 3 minutes out send three "This is due soon." notices on the first pass, then "This is now due." for each one a minute apart. After a crash at the 60-second pass and 2 hours down, the restart sends the interrupted notice again with its old key, plus one "Missed while docket was offline: 3 reminders." message.
- `reminders.py` is not byte-pinned. This phase adds no migration, setting or given product file, so no version pin or manifest moves.
- The given suite is 17 cases from 12 functions. On today's code all 17 fail with `AttributeError` for the missing names. On names-only stubs, 16 fail with `NotImplementedError` and the names test passes. A throwaway stand-in, deleted afterwards, passed all 17 and both probe walks, so the expected values agree with one another.

## Owner's decisions

Decided 2026-11-18:

- **A failed pass.** An unexpected error in a pass, such as a bug or a database locked by another writer, never stops the loop. It waits the usual 30 seconds and tries again. Stage 5 turns repeated failures into an alert and shows them in `docket status`. Not chosen: ending the loop and leaving launchd to restart the process, or ending it after 10 failed passes in a row.
- **Pass halves.** The reminder half and the digest half fail alone. A failure in one never skips the other in the same pass. Not chosen: ending the pass at the first failure.

## Architect's decisions

**Names.** In `reminders.py`:

- `LOOP_SECONDS = 30`.
- `@dataclass(frozen=True) class PassResult` with `sent: int` (what `send_due` returned, 0 when it failed), `digest: bool` (what `send_digest` returned, `False` when it failed) and `failed: tuple[str, ...]`. `failed` names each half that raised, in order, from `"reminders"` and `"digest"`.
- `class Stop(Protocol)` with `is_set(self) -> bool` and `wait(self, timeout: float) -> bool`.
- `run_pass(store: Store, notifier: Notifier, *, zone: str, at: time) -> PassResult`.
- `run_loop(store: Store, notifier: Notifier, *, zone: str, at: time, stop: Stop) -> int`, which returns the number of passes run.

**A pass.** `run_pass` calls `send_due(store, notifier)`, then `send_digest(store, notifier, zone=zone, at=at)`. Each call is in its own `try` with `except Exception`, and nothing wider. A `BaseException` that is not an `Exception` (`KeyboardInterrupt`, `SystemExit`, the tests' `Killed`) passes through, which ends the pass and the loop. A caught failure is only recorded in `failed`: nothing is printed, logged or retried within the pass.

**The loop.** `run_loop` repeats this: if `stop.is_set()`, return the passes so far; run one pass; then call `stop.wait(LOOP_SECONDS)`, and return if it answers `True`. The wait is the only pause, and the loop reads no clock of its own. The pause runs after each pass ends, so passes are 30 seconds apart plus the pass's own time. The caller owns the store: the loop opens, closes and reconnects nothing, and it reads no settings. The zone and digest time come from the caller, as in Phase 3d.

## Requirements

1. **Names:** `LOOP_SECONDS`, `PassResult`, `Stop`, `run_pass` and `run_loop`, as above. Given: one names-and-result test.
2. **One pass:** `run_pass` sends the due reminders, then the digest, and returns what each half sent. A second pass at the same moment sends nothing. Given: one test with literal notices, digest and results, and two clock reads a pass.
3. **Halves fail alone:** an unexpected error in either half is recorded in `failed`, and the other half still runs. A `NotifierError` is not a failure. Given: four cases (a reminders bug, a digest bug, both halves, and refusals).
4. **Keeps going:** after a failed pass the loop runs every later pass, and the post the bug interrupted is resent with its key once its claim is more than 5 minutes old. Given: one 12-pass test.
5. **Crashes pass through:** a `BaseException` that is not an `Exception` leaves `run_loop` unchanged, with no wait after it. Given: one test.
6. **Pace and stop:** the loop waits `LOOP_SECONDS` after each pass, stops when `wait` answers `True`, and runs no pass when the stop is already set, a `threading.Event` included. Given: one waits test and two already-stopped cases.
7. **Stage 3's test:** deadlines 1, 2 and 3 minutes out fire in order; a work time's start reminder fires once; a restart mid-run, killed before or after delivery, loses nothing and sends one status message; a second loop on another connection, interleaved between and during passes, never sends twice; and Done voids everything pending, while a second Done changes nothing. Given: five functions, six cases.
8. **Nothing else starts or paces it:** no sleep, thread, timer, signal handler, settings read or command. Only `stop.wait` pauses, and no code outside `reminders.py` calls `run_pass` or `run_loop`. Given: the searches.
9. **Progress entry** for `## Phase 3e: Reminder loop (YYYY-MM-DD)` at the end of `docs/progress.md`.

## Given files

Already committed with this spec; never change them.

| File | What it is |
|---|---|
| `tests/loop_cases.py` | Given `Ticker` (the loop's fake clock and stop), the start instant, zone and digest time, and the `text` helper |
| `tests/integration/test_reminder_loop.py` | 11 tests from 7 functions: names, pace, already stopped, one pass, halves failing alone, keeping going, crashes |
| `tests/integration/test_reminder_engine_stage.py` | 6 tests from 5 functions: Stage 3's test |
| `docs/verification/probe-03e.py` | The verifier's probe |

Given test count: **17** (12 functions): `test_reminder_loop.py` 11 tests from 7 functions, `test_reminder_engine_stage.py` 6 tests from 5 functions. On today's code all 17 fail.

## Tests to write

Write `tests/integration/test_reminder_loop_edges.py` with `tests/loop_cases.Ticker`, the fake notifier and literal outcomes:

- A `threading.Event` set from inside the first pass (through the fake notifier's `during` hook) ends the loop after that pass: `run_loop` returns 1.
- A loop started at 06:59:30 UTC (zone `UTC`, digest time 07:00) with a task past its last late reminder sends no digest on its first pass and the digest on its second, and later passes send no second digest.
- A notice refused with `NotifierError` on one pass is delivered on the next pass with the same key, and both results have `failed == ()`.
- Any line or branch of `PassResult`, `run_pass` or `run_loop` that the given tests leave uncovered.

Use this file name, not a generic `_more` file. Do not repair a given test to make it pass.

## Scope

| Path | Change |
|---|---|
| `src/docket/reminders.py` | edit: `LOOP_SECONDS`, `PassResult`, `Stop`, `run_pass`, `run_loop`; the planner, `send_due` and `send_digest` unchanged |
| `tests/integration/test_reminder_loop_edges.py` | create |
| `docs/progress.md` | append your entry |

## Out of scope

- `docket run`, a CLI or API command that starts the loop, launchd, a thread, `time.sleep`, `asyncio` or a signal handler (Stage 5).
- Logging, printing or alerting on a failed pass, counting failures in a row, `docket status`, or a backoff after failures (Stage 5's alerts).
- Reading `DOCKET_TIME_ZONE` or a digest time from the settings, or adding a setting.
- A real `Notifier`, the shared Discord service's client, cards or buttons (Stage 4).
- Reopening the store after a failure, or any change to the planner, `send_due`, `send_digest`, `store.py`, `core.py`, `tests/notifier_cases.py` or `tests/support.py`.
- Any change to a given file, `AGENTS.md` or the design docs.

## Rules that bite

- **A crash is not a failure.** Catch `Exception` only, once for each half. `except BaseException`, a bare `except:` or one `try` around the whole pass breaks requirements 3 and 5.
- **Retry safety stays in the claims.** The loop never marks, releases or resends anything itself. The resend after a bug is Phase 3c's 5-minute expiry.
- **Ids and time through the modules.** The loop calls neither `ids.new_id()` nor `clock.now()`. The halves read the clock, once each.
- **Errors carry no text.** The loop keeps only the names of the failed halves, never an exception's message, which may hold a title.
- **Time through the module**: `clock.now()`, never `datetime.now()`, and never `from docket.clock import now`.
- If you stop before finishing, still write the progress entry with a `Stopped:` first follow-up (`docs/phase-conventions.md`, "When you stop").
- Commands start with `.venv/bin/python`; no bare `python3`, `pytest` or `ruff`.

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_reminder_loop.py --ignore=tests/integration/test_reminder_engine_stage.py` (before you start) | `1650 passed` |
| `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1667 passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest tests/integration/test_reminder_loop.py tests/integration/test_reminder_engine_stage.py --no-cov -q` | `17 passed` |
| `.venv/bin/python -m coverage report --include=src/docket/reminders.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| `.venv/bin/python docs/verification/probe-03e.py` | last line `FAILURES 0` |
| `grep -c "^## Phase 3e: " docs/progress.md` | `1` |
| `.venv/bin/python scripts/check_reports.py --phase 3e` | `Reports OK.` |
| `git diff HEAD --stat -- tests/loop_cases.py tests/integration/test_reminder_loop.py tests/integration/test_reminder_engine_stage.py docs/verification/probe-03e.py` | no output |
| `git status --short` | only the Scope paths |

### Searches

Each prints nothing.

```zsh
git grep --untracked -n -E 'import (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)|from (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)' -- src
git grep --untracked -n -E 'print\(|logging|logger|warnings\.warn' -- src ':!src/docket/cli.py'
git grep --untracked -n -E 'datetime\.now|datetime\.utcnow|date\.today|time\.time\(|from docket\.(clock|ids) import' -- src ':!src/docket/clock.py'
git grep --untracked -n -E 'ollama|anthropic|openai|langchain' -- src
git grep --untracked -n -E 'pragma: no cover|noqa' -- src/docket/reminders.py
git grep --untracked -n -E 'except BaseException|except:|except \(' -- src/docket/reminders.py
git grep --untracked -n -E 'time\.sleep\(|asyncio|threading|signal|get_settings|DIGEST_TIME' -- src/docket/reminders.py
git grep --untracked -n -E '(run_loop|run_pass)\(' -- src ':!src/docket/reminders.py'
git grep --untracked -n -E 'ids\.new_id\(' -- src ':!src/docket/reminders.py'
```
