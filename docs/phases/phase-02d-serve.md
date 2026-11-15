# Phase 2d: Serve

## Goal

Run Phase 2c's app on a port. `docket serve` reads the settings, loads the client tokens from the Keychain, migrates the store once, and serves `docket.web.create_app` with uvicorn on 127.0.0.1 at `DOCKET_WEB_PORT` (8767 by default). It refuses to start, before it opens a socket, when no client has a token, the Keychain can't be read, the port setting is bad, or the store is newer than the code. The email service can then post its approved tasks to a running app. `docket run` (the API, the reminder loop and the queues in one process), the launchd file, alerts and `docket status` are stage 5.

Sections: `core`. The `tooling` section runs in the full check.

Follow `docs/phase-conventions.md`. N is 703, the tests the previous phase left passing.

Start: `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_settings_port.py --ignore=tests/integration/test_server.py --ignore=tests/e2e/test_cli_serve.py` must show `703 passed`. The ignored files import names you create.

## Facts

Each checked on this machine on 2026-11-14 in a scratch environment with uvicorn 0.54.0.

- **The new packages** in an install with `uvicorn>=0.54,<0.55` added are exactly `uvicorn` and `click` (uvicorn requires `click` and `h11`; `h11` is already installed for `httpx2`, and typer 0.29 carries its own copy of click, so `click` is new).
- **`uvicorn.run(app, ...)` defaults** (`uvicorn/main.py`): `proxy_headers=True` (it trusts `X-Forwarded-*` from 127.0.0.1 and rewrites the client address), `server_header=True` (`server: uvicorn`), `access_log=True` (one line per request with the path), and `log_level=None`, which logs at INFO. With `log_level="warning"` and `access_log=False`, starting, answering and stopping print nothing.
- **A real loopback server for a test**: `uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=<free port>, log_level="warning", access_log=False))` run in a daemon thread, `started` polled, and `should_exit = True` to stop it, finishes in well under a second; `tests/conftest.py` allows 127.0.0.1.
- **`uvicorn.run` is looked up on the module at call time**, so `monkeypatch.setattr(uvicorn, "run", ...)` replaces it for code that does `import uvicorn` and calls `uvicorn.run(...)`, but not for code that does `from uvicorn import run`.
- **`client_tokens()`** (Phase 2c) returns `{}` when no client has a token and raises `KeychainUnavailable("keychain unavailable: client.email")` when the Keychain can't be read.
- **`open_store(settings)`** (Phase 1) makes the data folder, migrates, and raises `StoreError("unsupported schema version: 99")` for a newer store.
- **The email service doesn't send a token yet** (`mailroom/tasks_app.py` posts with only `Idempotency-Key`); adding it is that project's Phase 3c (`docs/handoffs/emails.md`). Until then its posts get 401, as they should.

## Owner's decisions

Decided 2026-11-14:

- **uvicorn** (`uvicorn>=0.54,<0.55`), as the email service and Conductor run.
- **No client, no start**: `docket serve` refuses to start when no client has a token, with a message naming the command that issues one.
- **No access log**: uvicorn logs only warnings and errors, and no line per request.
- **The cross-check with the email service** is a manual check the owner runs once after this phase passes (the roadmap's "Manual checks"), not a test here.
- Earlier: the API is on 127.0.0.1:8767, next to Conductor's 8766.

## Architect's decisions

- **`DOCKET_WEB_PORT`**, an integer from 1024 to 65535 (no port that needs root), default 8767. A bad value is reported after the data folder, the time zone and the work length, in that order, as `get_settings` reports the others.
- **The order of start-up**, each refusing before the next: the settings, the tokens, the store; then the "Serving on" line, then uvicorn. A refusal opens no socket, and one before the store leaves no data folder behind.
- **The store is opened once at start and closed**, so a newer store or a migration fails at start, not on the first request; each request still opens its own store (Phase 2c).
- **Tokens are read once at start**: a token issued or replaced while the app runs takes effect at the next start (Phase 2c's `--replace` already says so).
- **uvicorn is called with every setting that matters spelled out**: host `127.0.0.1`, the port, `access_log=False`, `server_header=False`, `proxy_headers=False`, `log_level="warning"`. No `forwarded_allow_ips`, no reload, no workers.
- **`docket serve` needs no `DOCKET_TIME_ZONE`**: the email service sends each deadline's zone.
- **Critical modules:** `server.py` (with `config.py`, `web.py` and `clients.py`, already critical).

## Requirements

1. **Install.** `pyproject.toml` is given with `uvicorn>=0.54,<0.55` added to the dependencies. Run `.venv/bin/python -m pip install -e '.[dev]'` (this needs the network to reach PyPI; nothing else does). Install nothing else.
2. **`src/docket/config.py`**: `WEB_PORT_MESSAGE = "DOCKET_WEB_PORT must be 1024 to 65535"`; `Settings.web_port: int`, default 8767, 1024 to 65535 inclusive. A bad value (out of range, not an integer, empty) makes `get_settings()` raise `ConfigError(WEB_PORT_MESSAGE)` `from None`, unless the data folder, the time zone or the work length is also bad, which are reported first.
3. **`src/docket/server.py`, names**: `NO_CLIENTS_MESSAGE = "No clients yet: run docket clients add email."`; `class ServeError(Exception)`.
4. **`build_app(settings: Settings) -> FastAPI`**: calls `client_tokens()` (a `KeychainUnavailable` propagates); with no token raises `ServeError(NO_CLIENTS_MESSAGE)` before touching the store; otherwise opens `open_store(settings)` once and closes it (a `StoreError` propagates), and returns `create_app(open_store=<a function calling open_store(settings)>, tokens=<the tokens>, port=settings.web_port)`.
5. **`run_app(app: FastAPI, port: int) -> None`** calls `uvicorn.run(app, host="127.0.0.1", port=port, access_log=False, server_header=False, proxy_headers=False, log_level="warning")`, with `uvicorn` imported as a module (`import uvicorn`), and nothing else.
6. **`docket serve`** (`src/docket/cli.py`, a top-level command, no arguments): `get_settings()`, then `build_app`, then prints `Serving on http://127.0.0.1:<port>` on stdout, then `run_app(app, settings.web_port)`. A `ConfigError`, `KeychainUnavailable`, `ServeError` or `StoreError` prints its text alone to stderr and exits 1, and uvicorn isn't called. It needs no `DOCKET_TIME_ZONE`.
7. **Nothing else listens or logs**: only `server.py` imports uvicorn; the host is always `127.0.0.1`; docket configures no logging and prints nothing but the "Serving on" line and the refusals.

8. **Progress entry** for `## Phase 2d: Serve (YYYY-MM-DD)` at the end of `docs/progress.md`.

## Given files

Already committed with this spec; never change them.

| File | What it is |
|---|---|
| `tests/unit/test_settings_port.py` | 11 tests from 4 functions (requirement 2) |
| `tests/integration/test_server.py` | 6 tests from 6 functions (requirements 3 to 5), one over real loopback |
| `tests/e2e/test_cli_serve.py` | 7 tests from 4 functions (requirement 6) |
| `tests/integration/test_web.py` | edited: its `Opened` helper now records each store's `close()`, so a store left open fails Phase 2c's close test (37 tests, unchanged in number) |
| `pyproject.toml` | edited: `uvicorn>=0.54,<0.55` in the dependencies |
| `scripts/critical_modules.txt` | edited: `src/docket/server.py` added |
| `docs/verification/probe-02d.py` | The verifier's probe |

Given test count: **24** (the three new files).

## Tests to write

The given tests cover every requirement's main cases. To reach full coverage, add behaviour tests in new `*_more.py` files beside them, never by changing a given test.

- **The port's place in the order**: a bad data folder with a bad port reports `DATA_DIR_MESSAGE`; a bad time zone with a bad port reports `TIME_ZONE_MESSAGE` (`DOCKET_TIME_ZONE=Mars/Base`, `DOCKET_WEB_PORT=80`).
- **The store `build_app` hands to the app** is the settings' store: build with `DOCKET_DATA_DIR` at a `tmp_path` folder, call the app's `open_store` through a request (FastAPI's test client, `base_url="http://127.0.0.1:8767"`), and find the task in that folder's database.
- **A refused start leaves no data folder**: with `DOCKET_WEB_PORT=80`, and with the Keychain down, `docket serve` exits 1 and `tmp_path / "data"` doesn't exist.

## Scope

| Path | Change |
|---|---|
| `src/docket/server.py` | create |
| `src/docket/config.py` | edit: `WEB_PORT_MESSAGE`, `web_port`, its place in `get_settings`'s order |
| `src/docket/cli.py` | edit: the `serve` command |
| `tests/**/*_more.py` | create: your tests |
| `docs/progress.md` | append your entry |

## Out of scope

- `docket run`, the reminder loop, the launchd file, alerts and `docket status` (stage 5).
- Reloading tokens while running, a signal handler, a PID file, a health route, or a second route of any kind.
- TLS, a Unix socket, `0.0.0.0` or any host but 127.0.0.1, `forwarded_allow_ips`, workers or reload.
- Logging setup of docket's own (a logger, a handler, a log file), or a log level setting.
- Any change to the email service; its token is its Phase 3c.
- Any change to a given file, `AGENTS.md` or the design docs.

## Rules that bite

- **Network**: the server listens only on 127.0.0.1; tests start real servers only on 127.0.0.1 at a free port; the install is the only step that reaches PyPI.
- **Secrets**: a token never appears in a message, a log line or stdout; `docket serve` prints the address, never a token.
- **Error messages are constant text plus identifiers**: the refusals print the exception's own text, which Phase 1 and 2c already made constant; never a library's exception text.
- **No telemetry**: no uvicorn or FastAPI setting that turns any on; FastAPI's stays off in `create_app`.
- **Thin CLI**: `serve` decides nothing; the order of start-up is in `build_app`.
- **Time through the module**: `clock.now()`, never `datetime.now()`, and never `from docket.clock import now`.
- If you stop before finishing, still write the progress entry with a `Stopped:` first follow-up (`docs/phase-conventions.md`, "When you stop").
- Commands start with `.venv/bin/python`; no bare `python3`, `pytest` or `ruff`.

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_settings_port.py --ignore=tests/integration/test_server.py --ignore=tests/e2e/test_cli_serve.py` (before you start) | `703 passed` |
| `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 727 passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest tests/unit/test_settings_port.py tests/integration/test_server.py tests/e2e/test_cli_serve.py --no-cov -q` | `24 passed` |
| `.venv/bin/python -m coverage report --include=src/docket/server.py,src/docket/config.py,src/docket/cli.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| `.venv/bin/python docs/verification/probe-02d.py` | last line `FAILURES 0` |
| `grep -c "^## Phase 2d: " docs/progress.md` | `1` |
| `.venv/bin/python scripts/check_reports.py --phase 2d` | `Reports OK.` |
| `git diff HEAD --stat -- tests/unit/test_settings_port.py tests/integration/test_server.py tests/e2e/test_cli_serve.py tests/integration/test_web.py pyproject.toml scripts/critical_modules.txt docs/verification/probe-02d.py` | no output |
| `git status --short` | only the Scope paths |

### Searches

Each prints nothing.

```zsh
git grep --untracked -n -E 'import (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)|from (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)' -- src
git grep --untracked -n -E 'print\(|logging|logger|warnings\.warn' -- src ':!src/docket/cli.py'
git grep --untracked -n -E 'datetime\.now|datetime\.utcnow|date\.today|time\.time\(|from docket\.(clock|ids) import' -- src ':!src/docket/clock.py'
git grep --untracked -n -E '\.(insert_task|update_task|append_audit|insert_link|insert_request_key)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'
git grep --untracked -n -E 'ollama|anthropic|openai|langchain' -- src
git grep --untracked -n -E 'pragma: no cover|noqa' -- src/docket/server.py src/docket/config.py src/docket/cli.py
git grep --untracked -n -E 'import keyring|from keyring' -- src ':!src/docket/keychain.py'
git grep --untracked -n -E 'uvicorn' -- src ':!src/docket/server.py'
git grep --untracked -n -E '0\.0\.0\.0|"::"|forwarded_allow_ips|uds=|reload=|workers=' -- src
git grep --untracked -n -E 'opentelemetry|otel' -- src
```
