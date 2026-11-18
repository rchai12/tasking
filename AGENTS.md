# Rules for AI coding agents

This file applies to every phase. Read it, then `docs/architecture.md`, then `docs/testing.md`, then `docs/phase-conventions.md` (what every phase spec and guide assume), then the phase spec you were assigned.

## Scope discipline

- Implement **only** the phase you were assigned. Do not build features from later phases, even if it seems convenient.
- If the spec is ambiguous, pick the simplest option that satisfies the acceptance criteria and record the decision in `docs/progress.md`.
- If the spec seems wrong or impossible, stop instead of improvising a large workaround, and report the stop in your progress entry (`docs/phase-conventions.md`, "When you stop"), not only in your final message.
- Do not add dependencies that the phase spec does not list. If you believe one is needed, stop and ask.
- When finished, or when you stop before finishing, append an entry to `docs/progress.md` in the form `docs/phase-conventions.md` gives. A phase always ends with an entry.

## Running commands

- The project's interpreter is `.venv/bin/python`. Every command names it: `.venv/bin/python -m pytest`, `.venv/bin/python -m ruff check .`, `.venv/bin/docket version`.
- Never type `python`, `python3`, `ruff`, or `pytest` on their own. On this machine `python` does not exist, `python3` may be a different interpreter without the project's packages, and a bare `ruff` may be a different installation.
- Do not activate the virtual environment. Each command runs in a new shell, so activation is lost before the next command.
- From Phase 0 on, `.venv/` exists. It is gitignored. Do not create another virtual environment and do not reinstall packages unless the phase spec has a step for it.
- If a command prints `command not found` or `No module named ...`, it was not typed as written. Stop and fix the command; do not skip the step.
- Before reporting a phase, run `.venv/bin/python scripts/check.py` as the spec's acceptance gives it. It must end with `All checks passed.`

## Privacy and safety rules (non-negotiable)

1. **No real accounts or services.** Never connect to Google, Microsoft Graph, the shared Discord service, Discord itself, the email service or Conductor while working, never run the EventKit helper against real calendars, and never read the macOS Keychain. Tests replace all of them. The owner runs the real thing after verification.
2. **Synthetic data only** in tests and fixtures: invented titles, deadlines, ids, events and tokens. Never copy anything from the data folder, a calendar, or the Keychain.
3. **Nothing without approval.** No code path creates a task except from an approved source (an authenticated `POST /tasks`, an MCP write tool, the owner's command) or the owner's press on a proposal. No code path changes or ends a task on a timeout or from a calendar change.
4. **No model.** The app makes no model call and holds no prompt.
5. **Calendar writes carry only the approved title and time.** Calendar reads are never stored.
6. **Secrets come only from the Keychain**, through `docket.keychain`. Never from environment variables, files, code, or the repository. Never print, log, or put a secret in an error message.
7. **Network.** Code may connect only to what the phase spec names: the shared Discord service on 127.0.0.1, Google's OAuth and Calendar endpoints, Microsoft's sign-in and Graph. The API listens only on 127.0.0.1. Tests touch no network: `tests/conftest.py` blocks every connection that is not to 127.0.0.1 or a Unix socket.
8. **No telemetry.** No tracing, analytics, crash reporting, or update checks.
9. **Presses are the owner's only.** Every press and command checks the owner's Discord user id.

## Determinism rules

- **Code decides everything.** Reminder times, backoff, state changes and every policy are code.
- **Time and ids come from one place.** Read the current time only through `docket.clock.now()`, called through the module (`clock.now()`, not `from docket.clock import now`). Persistent internal rows use SQLite-assigned, never-reused row numbers: existing tasks `t1`, links `l1`, and future reminders `r1`. Outbound retry keys come only from `docket.ids.new_id()`, called through the module, and are persisted once and reused on retry. Pure planners allocate no IDs. Tests can replace clock/ID functions.
- **Everything is retry-safe.** Every create is keyed, every reminder is claimed before it is sent, every press can be repeated.
- **Deadlines are UTC instants plus a zone.** Never store local time strings; never use the machine's zone implicitly.

## Architecture rules

- See `docs/architecture.md` for the components and their boundaries.
- Every change to a task goes through `docket.core`, so a press, a command and an MCP tool share one path and one audit row.
- All configuration comes from `docket.config.get_settings()` (environment variables with prefix `DOCKET_`). No hardcoded paths, no secrets in settings.
- `cli`, `mcp_server` and the API routes are thin and contain no decisions.
- Use `pathlib.Path`. Development and deployment happen on macOS.
- **Error messages are constant text plus identifiers** (a task id, a field name, a line number). They never echo a title, a request body, a secret, or the text of an exception from a library that may contain one.
- **Titles are untrusted** plain text of at most 100 characters: never rendered as links or markdown that can act.

## Code style

- Python 3.12+, type hints on all public functions.
- `ruff check .` and `ruff format --check .` must pass.
- Prefer small, pure functions. Docstrings only where the intent is not obvious.
- `pytest` must pass, including all tests from previous phases.

## Testing

Follow `docs/testing.md`: put tests in the right layer (`tests/unit`, `tests/integration`, `tests/e2e`), keep them deterministic and offline, keep coverage above the configured threshold, and add a failing-first test for every bug fix. If you add code to a module listed under "Critical modules", cover every line and branch.
