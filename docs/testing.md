# Testing strategy

Applies to every phase. Phase specs list the specific tests; this file sets the rules and the layers. It follows the email service's `docs/testing.md`.

## Layers

| Layer | Location | What it covers | Runs |
|---|---|---|---|
| Unit | `tests/unit/` | Pure functions: settings, deadlines, state rules, reminder planning, backoff | Every run; fast |
| Integration | `tests/integration/` | The store in a temporary folder, the API through FastAPI's test client or synthetic ASGI exchanges, the reminder loop with a fake notifier, calendar clients against fakes on 127.0.0.1 | Every run |
| End-to-end | `tests/e2e/` | Commands through Typer's `CliRunner`; a task from `POST /tasks` to its reminders, a press, and its calendar event, with every outside system faked | Every run |

## Rules

1. **Synthetic data only.** Invented titles, deadlines, message ids, event ids and tokens.
2. **No network.** `tests/conftest.py` blocks every connection that is not to 127.0.0.1, ::1, localhost or a Unix socket.
3. **No real Keychain.** The keyring backend fails on every call unless a test takes the `fake_keychain` fixture.
4. **No real Discord service, Google, Graph or EventKit.** Each gets a fake in `tests/fakes.py` in the phase that first needs it, checked against the real system's documented shapes. The email service's request shapes come from its `docs/interfaces.md`.
5. **Deterministic.** Time comes only from replacing `docket.clock.now`, ids from `docket.ids.new_id`. Tests that cross a daylight-saving change name the zone and the dates.
6. **Isolated settings.** Every `DOCKET_*` variable is removed, and `HOME` and `DOCKET_DATA_DIR` point at fresh temporary folders.
7. **Every bug fix adds a test** that fails before the fix.
8. **Coverage:** branch coverage on every run, overall at least 90%; every line and branch of each critical module.
9. **Expected values are literal**, never built by the code under test.
10. **HTTP concurrency:** use events and temporary SQLite locks to prove loop progress and connection thread ownership. Timeouts are failure watchdogs; do not assert elapsed performance or coordinate with wall-clock sleeps. ASGI fakes match the installed server scope and never open a socket.

## Critical modules

A bug here loses a reminder, sends one twice, creates a task without approval, or leaks a secret. The list lives in `scripts/critical_modules.txt`; a phase that adds a critical module adds it there and here.

- `config.py` and `keychain.py` (Phase 0)
- `deadlines.py` (instants, exact zone names, the 17:00 default, work-time rules; Phase 1a)
- `schema.py` and `store.py` (every write whole or not at all, in a transaction; nothing removed or rewritten; Phase 1b)
- `core.py` (the state rules, the title rule and one audit row per change; Phase 1c)
- `references.py` (email reference text bounds and forbidden Unicode categories; Phase 2g)
- `intake/` (who may create what, and retry safety; Phase 2)
- `reminders.py` (nothing lost, nothing twice; Phase 3)
- the press handler (who may press, and idempotency; Phase 4)
- `calendar/sync.py` (one event per task, only title and time sent; Phase 7)
- `calendar/reconcile.py` (a mismatch holds and asks, never edits; Phase 9)
