# Review: Phase 2d

- Verdict: PASS
- Passed: 732
- Findings: 0
- Approved deviations: serve reports ConfigError, KeychainUnavailable, ServeError and StoreError through one handler
- For the architect: None

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none

The baseline is commit `51a8640`. `git ls-files --error-unmatch` found the spec, `tests/unit/test_settings_port.py`, `tests/integration/test_server.py`, `tests/e2e/test_cli_serve.py`, `tests/integration/test_web.py`, `pyproject.toml`, `scripts/critical_modules.txt`, and `docs/verification/probe-02d.py`. `git diff HEAD` for those given files is empty. `grep -c "^## Phase 2d: " docs/progress.md` printed `1`. The first follow-up is `None`, not `Stopped:`.

G1 `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_settings_port.py --ignore=tests/integration/test_server.py --ignore=tests/e2e/test_cli_serve.py`: `708 passed`, 0 failed. The five `*_more.py` tests add to the 703 from the previous phase.

G2 `.venv/bin/python scripts/check.py --first core` ended with `All checks passed.` Summary: lint passed, format passed, `tests (core): passed`, tests passed, critical coverage passed. The tests step passed 732, 0 failed, 0 skipped, and printed no warnings summary.

```
Sections:
  core          673 passed    0 failed    0 skipped
Sections:
  tooling        59 passed    0 failed    0 skipped
  core          673 passed    0 failed    0 skipped
```

G4, run immediately after G2: exit 0, `TOTAL` 100% (`server.py` 20 statements and 2 branches, `config.py` 61 statements and 14 branches, `cli.py` 188 statements and 36 branches, 0 missing).

G3: `24 passed`.

G5: `oracle: ok`, `400 random start-ups follow the order of refusals: ok`, `a repeated request across a restart makes one task, and it survives: ok`. Last line: `FAILURES 0`.

G6: `1`.

G8: no output against `HEAD`.

G9: `docs/progress.md`, `src/docket/cli.py`, `src/docket/config.py`, `src/docket/server.py`, `tests/e2e/test_cli_serve_more.py`, `tests/integration/test_server_more.py`, and `tests/unit/test_settings_port_more.py`, the Scope paths. Changed files in the progress entry is 7. This report is the extra path after it is written.

G10: the freeze list is the previous packages plus exactly `click` 8.5.1 and `uvicorn` 0.54.0.

Q1 through Q10 printed nothing (`git grep` exit 1).

The extra tests check the port's place ahead of a bad data folder and a bad time zone, that a request uses the settings' store, and that a bad port or a down Keychain leaves no data folder.

Spot checks, each restored from `/tmp/phase02d-verify-copies` before the next. Hashes matched afterwards (`config.py` `fe548a9ca9e0dd356738f7bb329a77d531cb90ea`, `server.py` `99b1338ddf04d16399c6b0c4f414669dc1866ead`, `cli.py` `5702adfc108d52cdae1b524acda690b84a0a9a3c`), `src/docket/__pycache__` was absent, and `git diff HEAD` for `config.py` and `cli.py` was the phase diff again.

- S1 failed: `DOCKET_WEB_PORT must be 1024 to 65535`.
- S2 failed: `DID NOT RAISE ConfigError`.
- S3 failed: `docket.sqlite3` exists.
- S4 failed: `sqlite3.OperationalError: unable to open database file`.
- S5 failed: `(400, {'error': 'wrong_host'})`.
- S6 failed: `"host": "0.0.0.0"`.
- S7 failed: the call has no `proxy_headers`.
- S8 failed: stdout `Serving on http://127.0.0.1:8767\n`.
- S9 failed: stderr `""`.
- S10 failed: exit 1.
