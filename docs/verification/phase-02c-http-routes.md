# Verification guide: Phase 2c (HTTP routes and client tokens)

Spec: `docs/phases/phase-02c-http-routes.md`. Follow `docs/phase-conventions.md` ("For the verifier"). Never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor, never read the Keychain, and never open the real data folder.

## 1. Coder ran

Stop with FAIL ("the coder did not run") if any of these is missing:

- `src/docket/clients.py`
- `src/docket/web.py`
- `grep -c "^## Phase 2c: " docs/progress.md` prints `1`

Stop with FAIL ("the coder stopped") if that entry's first `Follow-ups` line starts with `Stopped:`, as "A stopped coder" in `docs/phase-conventions.md` says. With no entry, `git status --short` tells "the coder did not run" (no Scope path changed) from "the coder broke off without reporting" (Scope paths changed; name them under `For the architect`).

Stop with FAIL ("the baseline is not committed") if `git ls-files --error-unmatch docs/phases/phase-02c-http-routes.md tests/unit/test_keychain_write.py tests/unit/test_clients.py tests/e2e/test_cli_clients.py tests/integration/test_web.py tests/fakes.py pyproject.toml scripts/critical_modules.txt docs/verification/probe-02c.py` fails: the diff gates can only be judged against a committed spec and given files.

## 2. Gates

Run each from the repository root, in this order. Given test count: 69.

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_keychain_write.py --ignore=tests/unit/test_clients.py --ignore=tests/e2e/test_cli_clients.py --ignore=tests/integration/test_web.py` | at least 634 passed, 0 failed (the coder's `*_more.py` tests add to the count) |
| G2 | `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 703 passed, 0 failed, 0 skipped |
| G3 | `.venv/bin/python -m pytest tests/unit/test_keychain_write.py tests/unit/test_clients.py tests/e2e/test_cli_clients.py tests/integration/test_web.py --no-cov -q` | `69 passed` |
| G4 | `.venv/bin/python -m coverage report --include=src/docket/clients.py,src/docket/web.py,src/docket/keychain.py,src/docket/cli.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| G5 | `.venv/bin/python docs/verification/probe-02c.py` | last line `FAILURES 0` |
| G6 | `grep -c "^## Phase 2c: " docs/progress.md` | `1` |
| G7 | `.venv/bin/python scripts/check_reports.py --phase 2c` | `Reports OK.` |
| G8 | `git diff HEAD --stat -- tests/unit/test_keychain_write.py tests/unit/test_clients.py tests/e2e/test_cli_clients.py tests/integration/test_web.py tests/fakes.py pyproject.toml scripts/critical_modules.txt docs/verification/probe-02c.py` | no output |
| G9 | `git status --short` | only the Scope paths |
| G10 | `.venv/bin/python -m pip list --format=freeze` | the packages before this phase plus exactly `fastapi`, `starlette`, `anyio`, `httpx2`, `httpcore2`, `h11`, `idna`, `truststore` and `opentelemetry-api`; no `opentelemetry-sdk` and no `opentelemetry-exporter-*` |

## 3. Spot checks

For each row:
1. Copy the module outside the repository.
2. Make the change described in the module the coder wrote.
3. Run the deciding test with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest '<test>' --no-cov -vv`, and confirm it fails with the "Broken" value.
4. Restore the module from your copy, delete `src/docket/__pycache__`, and confirm `git diff` is as before.

A different failure from the "Broken" column is a note, not a finding; a pass is a finding.

| # | Module | Change | Deciding test | Correct | Broken |
|---|---|---|---|---|---|
| S1 | `web.py` | check the route before the host | `tests/integration/test_web.py::test_a_request_for_another_host_is_refused_first[other-name]` | `/nowhere` answers 400 `wrong_host` | 404 `not_found` |
| S2 | `web.py` | accept any port on `127.0.0.1` | `tests/integration/test_web.py::test_a_request_for_another_host_is_refused_first[other-port]` | 400 `wrong_host` | 201 (the test reads the real clock, so the task is made) |
| S3 | `web.py` | compare the `Authorization` header case-insensitively | `tests/integration/test_web.py::test_a_request_without_the_token_is_refused[lower-case-scheme]` | 401 | 201 |
| S4 | `web.py` | strip the `Authorization` header before comparing | `tests/integration/test_web.py::test_a_request_without_the_token_is_refused[trailing-space]` | 401 | 201 |
| S5 | `web.py` | allow one byte more than `MAX_BODY` | `tests/integration/test_web.py::test_a_body_over_64_kib_is_refused_before_anything_else` | 413 `too_large` | 400 `missing_key` (that request has no key) |
| S6 | `web.py` | parse the JSON before checking the key | `tests/integration/test_web.py::test_the_key_comes_before_the_json[key-before-json]` | 400 `missing_key` | 422 `invalid_json` |
| S7 | `web.py` | open the store before the JSON check | `tests/integration/test_web.py::test_each_request_opens_and_closes_one_store` | 2 stores | 3 stores |
| S8 | `web.py` | leave the store open after the answer | `tests/integration/test_web.py::test_each_request_opens_and_closes_one_store` | every store closed | `all_closed()` False |
| S9 | `web.py` | leave a wrong method to FastAPI's default answer | `tests/integration/test_web.py::test_anything_but_the_two_routes_is_not_found[get-tasks]` | 404 `{'error': 'not_found'}` | 405 `{'detail': 'Method Not Allowed'}` |
| S10 | `web.py` | drop the `WWW-Authenticate` header | `tests/integration/test_web.py::test_a_request_without_the_token_is_refused[none]` | `'Bearer'` | `KeyError` |
| S11 | `clients.py` | issue a token without checking for one already there | `tests/unit/test_clients.py::test_a_second_token_needs_replace` | `ClientError` | DID NOT RAISE |
| S12 | `keychain.py` | allow a line break in a value | `tests/unit/test_keychain_write.py::test_an_invalid_value_is_refused_before_any_write[trailing-newline]` | `ValueError` | DID NOT RAISE |
| S13 | `keychain.py` | raise `KeychainUnavailable` without `from None` | `tests/unit/test_keychain_write.py::test_a_failed_write_hides_the_backend_text[error]` | `__suppress_context__` True | False |
| S14 | `clients.py` | let `SecretMissing` out of `client_tokens` | `tests/unit/test_clients.py::test_the_tokens_the_service_accepts` | `{}` | `SecretMissing` raised |
| S15 | `cli.py` | print `Token: ` before the token | `tests/e2e/test_cli_clients.py::test_adding_the_email_client_prints_its_token_once` | the token alone on a line | no match for the token pattern |
| S16 | `web.py` | build the app with `FastAPI()` and no `telemetry=` | `tests/integration/test_web.py::test_fastapis_own_telemetry_is_off` | `[]` | a `fastapi` log line (FastAPI automatic telemetry configuration failed ...) |

Rows S2 to S4 were traced with the real clock: those tests set no `fixed_times`, so a request that wrongly gets through reaches intake and makes a task.

## 4. Probe

Run `.venv/bin/python docs/verification/probe-02c.py` from the repository root. It is a given file: do not edit it. Every line must end in `ok`; the last line must be `FAILURES 0`. A stop at the probe's own `assert` lines, before its self-check prints `ok`, is the probe's fault: report it under "For the architect", not as a finding. It touches no network, Keychain or real data folder.

It checks what the given tests do not reach: 2000 random requests through FastAPI's test client, each of host, method, path, token, body size, key and body good or bad, every answer compared with the web layer's own order of checks, a request passing them all answered with one of intake's statuses, every answer JSON with only `id` or `error`, never a 500, the token and key never echoed, and a store opened only for a request that reaches intake. Every answer of the web layer is reached at least 30 times.

## 5. Searches

Each prints nothing. A match is a finding against the rule it names.

| # | Rule | Command |
|---|---|---|
| Q1 | no network code | `git grep --untracked -n -E 'import (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)\|from (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)' -- src` |
| Q2 | no output outside the CLI | `git grep --untracked -n -E 'print\(\|logging\|logger\|warnings\.warn' -- src ':!src/docket/cli.py'` |
| Q3 | time read only in `clock.py`, through the module | `git grep --untracked -n -E 'datetime\.now\|datetime\.utcnow\|date\.today\|time\.time\(\|from docket\.(clock\|ids) import' -- src ':!src/docket/clock.py'` |
| Q4 | only the core writes tasks, audit rows, links and keys | `git grep --untracked -n -E '\.(insert_task\|update_task\|append_audit\|insert_link\|insert_request_key)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'` |
| Q5 | no model client | `git grep --untracked -n -E 'ollama\|anthropic\|openai\|langchain' -- src` |
| Q6 | no coverage or lint exclusions in this phase's modules | `git grep --untracked -n -E 'pragma: no cover\|noqa' -- src/docket/clients.py src/docket/web.py src/docket/keychain.py src/docket/cli.py` |
| Q7 | the Keychain is reached only through `docket.keychain` | `git grep --untracked -n -E 'import keyring\|from keyring' -- src ':!src/docket/keychain.py'` |
| Q8 | this phase serves nothing and opens no socket | `git grep --untracked -n -E 'uvicorn\|\.run\(\|socket' -- src` |
| Q9 | nothing in `src` uses OpenTelemetry | `git grep --untracked -n -E 'opentelemetry\|otel' -- src` |

(In the table, `\|` is a `|` in the command.)

## 6. Reasonable variations

These are correct even though the spec does not spell them out:

- The host check, the token check and the size check as middleware, a dependency, or code in each route; a shared helper for the two routes.
- Exception handlers for Starlette's `HTTPException` (404 and 405) answering `not_found`.
- The body read with `await request.body()` in `async` routes, or in `def` routes through Starlette's request.
- The token compared with `hmac.compare_digest` against each known token in turn.
- `issue_token` checking for an existing token with `get_secret` and catching `SecretMissing`.
- Private helpers inside the Scope modules, and extra behaviour tests in `*_more.py` files.

## 7. Verdict

Write `docs/reviews/phase-02c-http-routes.md` in the form `docs/phase-conventions.md` gives (`# Review: Phase 2c`), then run `.venv/bin/python scripts/check_reports.py --phase 2c`; it must print `Reports OK.`
