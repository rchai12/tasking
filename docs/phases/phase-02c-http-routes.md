# Phase 2c: HTTP routes and client tokens

## Goal

Put Phase 2b's intake behind HTTP, signed in: `docket.web.create_app` answers `POST /tasks` and `POST /tasks/<id>/links` on 127.0.0.1 with the email service's contract, after its own checks (the host, the route, the client's token, the body's size, the key, the JSON). `docket clients add email` issues the email service's token once and keeps it in the Keychain, which the app can now write. Running the app on a port (`docket serve`, uvicorn), loading the tokens at start and the launchd file are Phase 2d.

Sections: `core`. The `tooling` section runs in the full check.

Follow `docs/phase-conventions.md`. N is 634, the tests the previous phase left passing.

Start: `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_keychain_write.py --ignore=tests/unit/test_clients.py --ignore=tests/e2e/test_cli_clients.py --ignore=tests/integration/test_web.py` must show `634 passed`. The ignored files import names you create.

## Facts

Each checked on this machine on 2026-11-14 in a scratch environment with fastapi 0.162.7, starlette 1.10.0 and httpx2 2.16.0.

- **Starlette's test client warns with `httpx`** ("Using `httpx` with `starlette.testclient` is deprecated; install `httpx2`"), which would put a warnings summary in the check; with `httpx2` installed instead it doesn't, even with warnings as errors. `finances` uses `httpx2` for the same reason; Conductor runs fastapi 0.162 with `httpx`.
- **A wrong method on a known path** reaches an exception handler as Starlette's `HTTPException` with 405; an unknown path as 404. A task id with `/`, an encoded `%2F`, or `/tasks/../links` (the client normalizes it to `/links`) matches no route.
- **The test client's default host is `testserver`**; `TestClient(app, base_url="http://127.0.0.1:8767")` sends `Host: 127.0.0.1:8767`, and a `Host` header in `headers=` replaces it.
- **Starlette reads a 70,000-byte body whole**: there is no size limit unless the app keeps one.
- **FastAPI 0.162 has telemetry of its own, on by default** (`fastapi/telemetry`): it records traces, metrics and logs through OpenTelemetry's global providers, and requires `opentelemetry-api` (which records nothing without an OpenTelemetry SDK, and none is installed). With `FASTAPI_OTEL_AUTO_CONFIGURE=true` and an OTLP endpoint in the environment, a default app tries at startup to add exporters and logs a failure on the `fastapi` logger. `FastAPI(telemetry={"tracing": False, "metrics": False, "logs": False, "operation_spans": False, "auto_configure": False})` turns all of it off: the same environment then logs nothing.
- **The new packages** in a fresh install are exactly `fastapi`, `starlette`, `anyio`, `httpx2`, `httpcore2`, `h11`, `idna`, `truststore` and `opentelemetry-api`.
- **`keyring.set_password`** raises `keyring.errors.PasswordSetError` (a `KeyringError`) when the backend refuses; `tests/fakes.py`'s `FakeKeychain` refused every write until now (given edit: it now records and stores writes).

## Owner's decisions

Decided 2026-11-14:

- **FastAPI** (`fastapi>=0.162,<0.163`) for the routes, with `httpx2>=2.16,<3` as a dev dependency for its test client.
- **`docket clients add email` refuses a second token unless `--replace`**; with it, a new token is stored and the old one stops working when the service next starts.
- **A body over 64 KiB is refused** (413) before it's parsed.
- Earlier: the token is printed once; each app keeps its own Keychain item; refusals as in Phase 2b.

## Architect's decisions

- **The order of the web layer's checks**, each refusing before the next: the host (400 `wrong_host`), the route (404 `not_found`, a wrong method included), the token (401 `unauthorized`), the size (413 `too_large`), the key (400 `missing_key`, as intake's rule), the JSON (422 `invalid_json`); then intake. The key comes before the JSON, as in the email service's fake.
- **The token is matched exactly**: `Authorization` must be `Bearer ` and a known token, compared with `hmac.compare_digest`; anything else is 401 with `WWW-Authenticate: Bearer`.
- **The app is built from its parts** (`create_app(open_store=…, tokens=…, port=…)`), so tests and Phase 2d pass the store, the tokens loaded from the Keychain and the port; the app reads no settings or Keychain of its own.
- **A store is opened per request that reaches intake, and closed after it**; refused requests open none.
- **The token is 32 random bytes in URL-safe base64** (`secrets.token_urlsafe(32)`, 43 characters), in the Keychain item `client.email`, and printed alone on stdout so it can be piped to the email service's setup.
- **Every answer is JSON** with `Cache-Control: no-store`.
- **FastAPI's telemetry is switched off** in code, whatever the environment says, as the project's no-telemetry rule requires; no OpenTelemetry SDK or exporter is ever installed.
- **Critical modules:** `clients.py` and `web.py` (with `keychain.py`, already critical).

## Requirements

1. **Install.** `pyproject.toml` is given with `fastapi>=0.162,<0.163` and the dev dependency `httpx2>=2.16,<3`. Run `.venv/bin/python -m pip install -e '.[dev]'` (this needs the network to reach PyPI; nothing else does). Install nothing else.
2. **`src/docket/keychain.py`**: `VALUE_MESSAGE = "invalid secret value"`. `set_secret(name: str, value: str) -> None` checks the name as `get_secret` does (`ValueError(NAME_MESSAGE)`), then the value: a non-empty `str` with no line break (`ValueError(VALUE_MESSAGE)`), both before any Keychain call; then `keyring.set_password(SERVICE, name, value)`, a `KeyringError` becoming `KeychainUnavailable("keychain unavailable: <name>")` `from None`.
3. **`src/docket/clients.py`**: `CLIENTS = ("email",)`; `ALREADY_MESSAGE = "email already has a token; use --replace to issue a new one."` (with the client's name); `UNKNOWN_CLIENT_MESSAGE = "Clients are: email."`; `class ClientError(Exception)`; `token_name(client) -> str` is `"client.<client>"`.
4. **`issue_token(client: str, *, replace: bool = False) -> str`**: an unknown client raises `ClientError(UNKNOWN_CLIENT_MESSAGE)`; a client that already has a token (its `get_secret` succeeds) raises `ClientError(ALREADY_MESSAGE)` unless `replace`; otherwise it stores `secrets.token_urlsafe(32)` with `set_secret` and returns it. `KeychainUnavailable` propagates.
5. **`client_tokens() -> dict[str, str]`** maps each stored token to its client, skipping a client with no token (`SecretMissing`); `KeychainUnavailable` propagates.
6. **`docket clients add CLIENT [--replace]`** (argument `client`): prints the token alone on stdout and exits 0; a `ClientError` or `KeychainUnavailable` prints its text to stderr and exits 1. It needs no `DOCKET_TIME_ZONE`.
7. **`src/docket/web.py`, names**: `WRONG_HOST = "wrong_host"`, `NOT_FOUND = "not_found"`, `UNAUTHORIZED = "unauthorized"`, `TOO_LARGE = "too_large"`, `INVALID_JSON = "invalid_json"`, `MAX_BODY = 65536`.
8. **`create_app(*, open_store: Callable[[], Store], tokens: Mapping[str, str], port: int) -> FastAPI`** answers, in this order, each with `{"error": <code>}`:
   - a `Host` header other than `127.0.0.1:<port>` or `localhost:<port>`: 400 `wrong_host`;
   - anything but `POST /tasks` and `POST /tasks/{task_id}/links`: 404 `not_found`;
   - an `Authorization` header other than `Bearer <a key of tokens>`: 401 `unauthorized`, with `WWW-Authenticate: Bearer`;
   - a body over `MAX_BODY` bytes: 413 `too_large`;
   - an `Idempotency-Key` header missing or not 1 to 200 characters: 400 `missing_key`;
   - a body that isn't UTF-8 JSON: 422 `invalid_json`;
   - then, with a store from `open_store()` closed after the answer, `accept_task(store, key=…, body=…)` or `accept_link(store, task_id, key=…, body=…)`, its `Answer` sent as the status and JSON body.
9. **Every answer** has `Content-Type: application/json` and `Cache-Control: no-store`, and no answer echoes the token, the key or the body.
10. **No telemetry**: `create_app` builds its `FastAPI` with `telemetry={"tracing": False, "metrics": False, "logs": False, "operation_spans": False, "auto_configure": False}`, so with `FASTAPI_OTEL_AUTO_CONFIGURE=true` and an OTLP endpoint set, the app still starts and logs nothing on the `fastapi` logger.
11. **The web layer decides nothing about tasks**: it writes only through `docket.intake`, reads no clock, settings, environment or Keychain itself, and opens no socket (serving is Phase 2d).

12. **Progress entry** for `## Phase 2c: HTTP routes and client tokens (YYYY-MM-DD)` at the end of `docs/progress.md`.

## Given files

Already committed with this spec; never change them.

| File | What it is |
|---|---|
| `tests/unit/test_keychain_write.py` | 14 tests from 5 functions (requirement 2) |
| `tests/unit/test_clients.py` | 11 tests from 7 functions (requirements 3 to 5) |
| `tests/e2e/test_cli_clients.py` | 7 tests from 7 functions (requirement 6) |
| `tests/integration/test_web.py` | 37 tests from 12 functions (requirements 7 to 11) |
| `tests/fakes.py` | Edited: `FakeKeychain` records writes in `writes` and stores them |
| `pyproject.toml` | Edited: the two dependencies (requirement 1) |
| `scripts/critical_modules.txt` | Adds `clients.py` and `web.py` |
| `docs/verification/probe-02c.py` | The verifier's probe |

Given test count: **69**.

## Tests to write

The given tests cover every requirement's main cases. To reach full coverage, add behaviour tests in new `*_more.py` files beside them, never by changing a given test.

## Scope

| Path | Change |
|---|---|
| `src/docket/clients.py` | create |
| `src/docket/web.py` | create |
| `src/docket/keychain.py` | edit: `VALUE_MESSAGE`, `set_secret` |
| `src/docket/cli.py` | edit: the `clients` group and `add` |
| `docs/progress.md` | append your entry |

## Out of scope

- `docket serve`, uvicorn, binding a port, loading tokens at start, the launchd file, `DOCKET_WEB_PORT` (Phase 2d).
- Removing or listing clients; any client but `email`; proposals; Conductor over HTTP.
- CORS, a login page, cookies, rate limits, request logging, an OpenAPI page in use.
- Any change to `intake.py`, `core.py`, `store.py`, a given file, `AGENTS.md` or the design docs.
- Any change to a given file, `AGENTS.md` or the design docs.

## Rules that bite

- **Nothing without approval**: a task arrives only from a request carrying the email client's token, through intake.
- **Secrets come only from the Keychain**: the token is written and read only through `docket.keychain`; it is never logged, put in an error, or echoed; it appears once, on the `clients add` command's stdout.
- **No telemetry**: FastAPI's own is switched off in `create_app`; nothing in `src` imports OpenTelemetry, and no SDK or exporter is installed.
- **Network**: this phase opens no socket; `import http` is still forbidden (use plain status numbers), so the network search stays silent.
- **Error messages are constant text plus a name**: never a token, a key or a body.
- **Time through the module**: `clock.now()`, never `datetime.now()`, and never `from docket.clock import now`.
- If you stop before finishing, still write the progress entry with a `Stopped:` first follow-up (`docs/phase-conventions.md`, "When you stop").
- Commands start with `.venv/bin/python`; no bare `python3`, `pytest` or `ruff`.

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_keychain_write.py --ignore=tests/unit/test_clients.py --ignore=tests/e2e/test_cli_clients.py --ignore=tests/integration/test_web.py` (before you start) | `634 passed` |
| `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 703 passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest tests/unit/test_keychain_write.py tests/unit/test_clients.py tests/e2e/test_cli_clients.py tests/integration/test_web.py --no-cov -q` | `69 passed` |
| `.venv/bin/python -m coverage report --include=src/docket/clients.py,src/docket/web.py,src/docket/keychain.py,src/docket/cli.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| `.venv/bin/python docs/verification/probe-02c.py` | last line `FAILURES 0` |
| `grep -c "^## Phase 2c: " docs/progress.md` | `1` |
| `.venv/bin/python scripts/check_reports.py --phase 2c` | `Reports OK.` |
| `git diff HEAD --stat -- tests/unit/test_keychain_write.py tests/unit/test_clients.py tests/e2e/test_cli_clients.py tests/integration/test_web.py tests/fakes.py pyproject.toml scripts/critical_modules.txt docs/verification/probe-02c.py` | no output |
| `git status --short` | only the Scope paths |

### Searches

Each prints nothing.

```zsh
git grep --untracked -n -E 'import (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)|from (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)' -- src
git grep --untracked -n -E 'print\(|logging|logger|warnings\.warn' -- src ':!src/docket/cli.py'
git grep --untracked -n -E 'datetime\.now|datetime\.utcnow|date\.today|time\.time\(|from docket\.(clock|ids) import' -- src ':!src/docket/clock.py'
git grep --untracked -n -E '\.(insert_task|update_task|append_audit|insert_link|insert_request_key)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'
git grep --untracked -n -E 'ollama|anthropic|openai|langchain' -- src
git grep --untracked -n -E 'pragma: no cover|noqa' -- src/docket/clients.py src/docket/web.py src/docket/keychain.py src/docket/cli.py
git grep --untracked -n -E 'import keyring|from keyring' -- src ':!src/docket/keychain.py'
git grep --untracked -n -E 'uvicorn|\.run\(|socket' -- src
git grep --untracked -n -E 'opentelemetry|otel' -- src
```
