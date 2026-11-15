# Review: Phase 2c

- Verdict: PASS
- Passed: 703
- Findings: 0
- Approved deviations: the clients add command is add_client so it does not clash with tasks add; the OpenAPI, ReDoc and schema routes are turned off; a secret value is refused when it contains a newline or a carriage return
- For the architect: S8 still passes if the store is left open, because all_closed() calls tasks() from the test thread and an open SQLite connection raises across threads, which that helper counts as closed

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none

The baseline is commit `8a699d9`. `git ls-files --error-unmatch` found the spec, `tests/unit/test_keychain_write.py`, `tests/unit/test_clients.py`, `tests/e2e/test_cli_clients.py`, `tests/integration/test_web.py`, `tests/fakes.py`, `pyproject.toml`, `scripts/critical_modules.txt`, and `docs/verification/probe-02c.py`. `git diff HEAD` for those given files is empty. `grep -c "^## Phase 2c: " docs/progress.md` printed `1`. The first follow-up is `None`, not `Stopped:`.

G1 `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_keychain_write.py --ignore=tests/unit/test_clients.py --ignore=tests/e2e/test_cli_clients.py --ignore=tests/integration/test_web.py`: `634 passed`, 0 failed. There is no `*_more.py` for this phase.

G2 `.venv/bin/python scripts/check.py --first core` ended with `All checks passed.` Summary: lint passed, format passed, `tests (core): passed`, tests passed, critical coverage passed. The tests step passed 703, 0 failed, 0 skipped, and printed no warnings summary.

```
Sections:
  core          644 passed    0 failed    0 skipped
Sections:
  tooling        59 passed    0 failed    0 skipped
  core          644 passed    0 failed    0 skipped
```

G4, run immediately after G2: exit 0, `TOTAL` 100% (`cli.py` 178 statements and 36 branches, `clients.py` 30 statements and 6 branches, `keychain.py` 33 statements and 8 branches, `web.py` 61 statements and 14 branches, 0 missing).

G3: `69 passed`.

G5: `oracle: ok`, `2000 random requests follow the web layer's order of checks: ok`. Last line: `FAILURES 0`.

G6: `1`.

G8: no output against `HEAD`.

G9: `docs/progress.md`, `src/docket/cli.py`, `src/docket/keychain.py`, `src/docket/clients.py`, and `src/docket/web.py`, the Scope paths. Changed files in the progress entry is 5. This report is the extra path after it is written.

G10: the freeze list is the previous packages plus exactly `anyio` 4.16.0, `fastapi` 0.162.7, `h11` 0.16.0, `httpcore2` 2.16.0, `httpx2` 2.16.0, `idna` 3.20, `opentelemetry-api` 1.45.2, `starlette` 1.10.0, and `truststore` 0.10.5. No `opentelemetry-sdk` and no `opentelemetry-exporter-*`.

Q1 through Q9 printed nothing (`git grep` exit 1).

Spot checks, each restored from `/tmp/phase02c-verify-copies` before the next. Hashes matched afterwards (`web.py` `a8d8ea1d63408383fccf0ad10a1d112175d6939a`, `clients.py` `e359c8edd8c552916e785cae538a0b87a4ed18f4`, `keychain.py` `9c2b5d49ad08cd4db68d26ac90ac393157a9a264`, `cli.py` `dd195c0d60018e8994835809deb149a8fcb78f52`), `src/docket/__pycache__` was absent, and `git diff HEAD` for `cli.py` and `keychain.py` was the phase diff again.

- S1 failed: `(404, {'error': 'not_found'})` for `/nowhere`.
- S2 failed: `(201, {'id': 't1'})`.
- S3 failed: `(201, {'id': 't1'})`.
- S4 failed: `(201, {'id': 't1'})`.
- S5 failed: `(400, {'error': 'missing_key'})`.
- S6 failed: `(422, {'error': 'invalid_json'})`.
- S7 failed: `3` stores against `2`.
- S8 passed. A note, not a finding. See the architect line.
- S9 failed: `(405, {'detail': 'Method Not Allowed'})`.
- S10 failed: `KeyError: 'www-authenticate'`.
- S11 failed: `DID NOT RAISE ClientError`.
- S12 failed: `DID NOT RAISE ValueError`.
- S13 failed: `__suppress_context__` False.
- S14 failed: `SecretMissing`.
- S15 failed: stdout was `Token: ` plus the token, so the token pattern did not match.
- S16 failed: a `fastapi` log line that automatic telemetry configuration failed.
