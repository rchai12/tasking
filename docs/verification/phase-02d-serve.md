# Verification guide: Phase 2d (Serve)

Spec: `docs/phases/phase-02d-serve.md`. Follow `docs/phase-conventions.md` ("For the verifier"). Never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor, never read the Keychain, and never open the real data folder.

## 1. Coder ran

Stop with FAIL ("the coder did not run") if any of these is missing:

- `src/docket/server.py`
- `grep -c "^## Phase 2d: " docs/progress.md` prints `1`

Stop with FAIL ("the coder stopped") if that entry's first `Follow-ups` line starts with `Stopped:`, as "A stopped coder" in `docs/phase-conventions.md` says. With no entry, `git status --short` tells "the coder did not run" (no Scope path changed) from "the coder broke off without reporting" (Scope paths changed; name them under `For the architect`).

Stop with FAIL ("the baseline is not committed") if `git ls-files --error-unmatch docs/phases/phase-02d-serve.md tests/unit/test_settings_port.py tests/integration/test_server.py tests/e2e/test_cli_serve.py tests/integration/test_web.py pyproject.toml scripts/critical_modules.txt docs/verification/probe-02d.py` fails: the diff gates can only be judged against a committed spec and given files.

## 2. Gates

Run each from the repository root, in this order. Given test count: 24.

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python -m pytest --no-cov -q --deselect=tests/unit/test_settings_port.py::test_the_port_setting_and_its_message --deselect=tests/unit/test_settings_port.py::test_the_ends_of_the_range --deselect=tests/unit/test_settings_port.py::test_a_bad_port_is_refused --deselect=tests/unit/test_settings_port.py::test_the_port_is_reported_after_the_work_length --deselect=tests/integration/test_server.py::test_the_message --deselect=tests/integration/test_server.py::test_with_no_client_the_app_is_not_built --deselect=tests/integration/test_server.py::test_building_the_app_opens_the_store_once_to_migrate_it --deselect=tests/integration/test_server.py::test_a_newer_store_stops_the_build --deselect=tests/integration/test_server.py::test_run_app_serves_on_loopback_only_and_quietly --deselect=tests/integration/test_server.py::test_the_built_app_answers_over_real_loopback --deselect=tests/e2e/test_cli_serve.py::test_serve_says_where_and_runs --deselect=tests/e2e/test_cli_serve.py::test_serve_uses_the_port_setting --deselect=tests/e2e/test_cli_serve.py::test_serve_needs_no_time_zone --deselect=tests/e2e/test_cli_serve.py::test_serve_refuses_to_start` | at least 703 passed, 0 failed (the coder's `*_more.py` tests add to the count) |
| G2 | `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 727 passed, 0 failed, 0 skipped |
| G3 | `.venv/bin/python -m pytest tests/unit/test_settings_port.py tests/integration/test_server.py tests/e2e/test_cli_serve.py --no-cov -q --deselect=tests/unit/test_settings_port.py::test_a_bad_data_folder_is_reported_before_the_port --deselect=tests/unit/test_settings_port.py::test_a_bad_time_zone_is_reported_before_the_port --deselect=tests/integration/test_server.py::test_a_request_uses_the_settings_store --deselect=tests/e2e/test_cli_serve.py::test_a_bad_port_leaves_no_data_folder --deselect=tests/e2e/test_cli_serve.py::test_a_down_keychain_leaves_no_data_folder` | `24 passed` |
| G4 | `.venv/bin/python -m coverage report --include=src/docket/server.py,src/docket/config.py,src/docket/cli.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| G5 | `.venv/bin/python docs/verification/probe-02d.py` | last line `FAILURES 0` |
| G6 | `grep -c "^## Phase 2d: " docs/progress.md` | `1` |
| G7 | `.venv/bin/python scripts/check_reports.py --phase 2d` | `Reports OK.` |
| G8 | `git diff HEAD --stat -- tests/unit/test_settings_port.py tests/integration/test_server.py tests/e2e/test_cli_serve.py tests/integration/test_web.py pyproject.toml scripts/critical_modules.txt docs/verification/probe-02d.py` | no output |
| G9 | `git status --short` | only the Scope paths |
| G10 | `.venv/bin/python -m pip list --format=freeze` | exactly two packages more than before this phase: `click` and `uvicorn` (0.54.x) |

## 3. Spot checks

For each row:
1. Copy the module outside the repository.
2. Make the change described in the module the coder wrote.
3. Run the deciding test with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest '<test>' --no-cov -vv`, and confirm it fails with the "Broken" value.
4. Restore the module from your copy, delete `src/docket/__pycache__`, and confirm `git diff` is as before.

A different failure from the "Broken" column is a note, not a finding; a pass is a finding.

| # | Module | Change | Deciding test | Correct | Broken |
|---|---|---|---|---|---|
| S1 | `config.py` | check the port before the work length | `tests/unit/test_settings_port.py::test_the_port_is_reported_after_the_work_length` | `DOCKET_WORK_MINUTES must be 5 to 720` | `DOCKET_WEB_PORT must be 1024 to 65535` |
| S2 | `config.py` | lowest port 1 instead of 1024 | `tests/unit/test_settings_port.py::test_a_bad_port_is_refused[privileged]` | `ConfigError` | DID NOT RAISE (port 80 accepted) |
| S3 | `server.py` | open the store before reading the tokens | `tests/integration/test_server.py::test_with_no_client_the_app_is_not_built` | no `docket.sqlite3` | `docket.sqlite3` exists |
| S4 | `server.py` | drop the store's open and close in `build_app` | `tests/integration/test_server.py::test_building_the_app_opens_the_store_once_to_migrate_it` | `user_version` `(2,)` | `sqlite3.OperationalError` (no data folder to open the file in) |
| S5 | `server.py` | pass `port=8767` to `create_app` instead of the setting | `tests/integration/test_server.py::test_the_built_app_answers_over_real_loopback` | 201 `{"id": "t1"}` | 400 `{"error": "wrong_host"}` (the free port is not 8767) |
| S6 | `server.py` | serve on `0.0.0.0` | `tests/integration/test_server.py::test_run_app_serves_on_loopback_only_and_quietly` | `"host": "127.0.0.1"` | `"host": "0.0.0.0"` |
| S7 | `server.py` | leave out `proxy_headers=False` | `tests/integration/test_server.py::test_run_app_serves_on_loopback_only_and_quietly` | the call has `"proxy_headers": False` | the call has no `proxy_headers` |
| S8 | `cli.py` | print the "Serving on" line before `build_app` | `tests/e2e/test_cli_serve.py::test_serve_refuses_to_start[no-clients]` | stdout `""` | stdout `"Serving on http://127.0.0.1:8767\n"` |
| S9 | `cli.py` | stop catching `ConfigError` in `serve` | `tests/e2e/test_cli_serve.py::test_serve_refuses_to_start[bad-port]` | stderr `DOCKET_WEB_PORT must be 1024 to 65535\n` | stderr `""` (the runner catches the exception, exit 1) |
| S10 | `cli.py` | read the settings through the home-zone helper (`home_zone`) in `serve` | `tests/e2e/test_cli_serve.py::test_serve_needs_no_time_zone` | exit 0 | exit 1 (`DOCKET_TIME_ZONE is not set`) |

## 4. Probe

Run `.venv/bin/python docs/verification/probe-02d.py` from the repository root. It is a given file: do not edit it. Every line must end in `ok`; the last line must be `FAILURES 0`. A stop at the probe's own `assert` lines, before its self-check prints `ok`, is the probe's fault: report it under "For the architect", not as a finding. It touches no network, Keychain or real data folder.

It checks 400 random start-ups against the order of refusals (a refusal never calls uvicorn, and one before the store leaves no data folder), that a start-up that passes serves only on 127.0.0.1 at the set port, and that over real loopback a repeated request across a restart makes one task that survives.

## 5. Searches

Each prints nothing. A match is a finding against the rule it names.

| # | Rule | Command |
|---|---|---|
| Q1 | no network code | `git grep --untracked -n -E 'import (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)\|from (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)' -- src` |
| Q2 | no output outside the CLI | `git grep --untracked -n -E 'print\(\|logging\|logger\|warnings\.warn' -- src ':!src/docket/cli.py'` |
| Q3 | time read only in `clock.py`, through the module | `git grep --untracked -n -E 'datetime\.now\|datetime\.utcnow\|date\.today\|time\.time\(\|from docket\.(clock\|ids) import' -- src ':!src/docket/clock.py'` |
| Q4 | only the core writes tasks, audit rows, links and keys | `git grep --untracked -n -E '\.(insert_task\|update_task\|append_audit\|insert_link\|insert_request_key)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'` |
| Q5 | no model client | `git grep --untracked -n -E 'ollama\|anthropic\|openai\|langchain' -- src` |
| Q6 | no coverage or lint exclusions in this phase's modules | `git grep --untracked -n -E 'pragma: no cover\|noqa' -- src/docket/server.py src/docket/config.py src/docket/cli.py` |
| Q7 | the Keychain only through `docket.keychain` | `git grep --untracked -n -E 'import keyring\|from keyring' -- src ':!src/docket/keychain.py'` |
| Q8 | only `server.py` uses uvicorn | `git grep --untracked -n -E 'uvicorn' -- src ':!src/docket/server.py'` |
| Q9 | no host but 127.0.0.1, no forwarded headers, socket file, reload or workers | `git grep --untracked -n -E '0\.0\.0\.0\|"::"\|forwarded_allow_ips\|uds=\|reload=\|workers=' -- src` |
| Q10 | no OpenTelemetry | `git grep --untracked -n -E 'opentelemetry\|otel' -- src` |

(In the table, `\|` is a `|` in the command.)

## 6. Reasonable variations

These are correct even though the spec does not spell them out:

- The refusals caught in one `except` with a tuple, or one per exception, as long as each prints only its text and exits 1.
- `build_app`'s store function as a lambda, a nested function or `functools.partial(open_store, settings)`.
- The port checked by `Field(ge=1024, le=65535)` or by a validator, as long as the message and the order hold.
- `serve` importing `docket.server` at the top of `cli.py` or inside the command.
- The "Serving on" line through `print` or `typer.echo`.
- Private helpers inside the Scope modules, and extra behaviour tests in `*_more.py` files.

## 7. Verdict

Write `docs/reviews/phase-02d-serve.md` in the form `docs/phase-conventions.md` gives (`# Review: Phase 2d`), then run `.venv/bin/python scripts/check_reports.py --phase 2d`; it must print `Reports OK.`

## Selector migration (Phase 2p, 2026-11-18)

The port-setting, server, CLI-serve and CLI-task continuation cases now live in their canonical modules. Executable selectors above preserve the original case sets: positive file selections deselect later cases; former file ignores deselect only their original functions. Counts and implementation history describe the original phase. Retired continuation paths in historical prose are historical names, not runnable selectors. This migration authorizes only the literal replacements recorded in tests/product_consolidation_manifest.json; earlier test bodies, spot-check decisions and review reports are unchanged.
