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
8. **Coverage:** branch coverage on every run, overall at least 90%; every line and branch of each product critical module and every listed tooling module (separate gates from Phase 2n).
9. **Expected values are literal**, never built by the code under test.
10. **HTTP concurrency:** use events and temporary SQLite locks to prove loop progress and connection thread ownership. Timeouts are failure watchdogs; do not assert elapsed performance or coordinate with wall-clock sleeps. ASGI fakes match the installed server scope and never open a socket.
11. **Store startup:** use spawn-mode processes and standard-library IPC against synthetic temporary databases to test independent openers and lock release on process exit. Probe entry points have a main guard so spawned children do not recursively run them. Keep process/queue cleanup in finally blocks; no real database or account is used.
12. **Pins (Phase 6b onward):** given tests are committed behind strict `xfail` markers that the coder deletes. The verifier reviews in `docs/reviews/` are pinned by sha256 in `tests/review_pins.json`; the architect pins each passed phase's review in the next spec's commit. Nothing else is byte- or AST-pinned: a verifier judges given files with `git diff` against the phase's base commit.

## Critical modules

Phase 2n specifies two independent 100% line-and-branch gates after the same full test run. Product `critical coverage` uses `scripts/critical_modules.txt`, relative to src/docket. Repository `tooling coverage` uses `scripts/tooling_modules.txt`, relative to the repository. Missing measurements fail either gate. Pytest measures both docket and docket_tools with branch coverage and retains the overall 90% floor. A product failure stops before the tooling gate; a tooling failure cannot produce overall success.

Product critical modules guard task approval, retry safety, reminder integrity and secrets. The target inventory after Phase 2n is:

- config.py and keychain.py
- deadlines.py; Phase 3a adds reminders.py for pure scheduling
- schema.py and store.py
- _store_tasks.py, _store_audit.py, _store_links.py and _store_keys.py; Phase 3b adds _store_reminders.py, 3c _store_posts.py and 3d _store_digests.py
- core.py
- references.py
- serialization.py
- domain.py and parsing.py
- intake.py, clients.py, web.py and server.py

Tooling coverage preserves the existing complete coverage of reports.py, acceptance.py and spotcheck.py under docket_tools. The checker itself is exercised by fake-runner/gate tests; this phase does not create a new 100% promise for scripts/check.py.

Future reminder, press and calendar-sync/reconciliation modules join the product critical inventory when their phases add them. Product packaging remains confined to src; repository tooling is not installed or imported by product code. The Phase 2n packaging check uses unchanged discovery plus an isolated src-copy CLI smoke test with network and Keychain access blocked; it does not claim a wheel was built.

Phase 3b adds populated v3 upgrade/restart, independent upgraders, last-approved-time/past-slot preservation and post-reminder-write rollback across tasks/audits/keys/reminders/sequences. Its scoped structural freezes retain unaffected source nodes, existing imports and mutable-method signatures while permitting the named feature bodies; all unrelated byte guards remain exact. Do not refresh guards from an implementation to make tests pass. Claim/delivery and double-loop send tests remain requirements of the later sender, not claims made by persistence tests.
