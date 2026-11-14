# Review: Phase 0

- Verdict: PASS
- Passed: 96
- Findings: 0
- Approved deviations: data_dir uses a default_factory and Path.expanduser(); names use one re.fullmatch; prepare_data_dir uses mkdir then chmod 0o700; version uses print and the callback has a docstring
- For the architect: None

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none

## Gate output

Coder ran: the six `src/docket` modules, `.venv/bin/python`, and `.venv/bin/docket` are present. `grep -c "^## Phase 0: " docs/progress.md` printed `1`. `git ls-files --error-unmatch` found the spec, `pyproject.toml`, `tests/conftest.py`, and `docs/verification/probe-00.py`.

G1 `.venv/bin/python scripts/check.py --first core` ended with `All checks passed.` Summary: lint passed, format passed, `tests (core): passed`, tests passed, critical coverage passed. The tests step collected 96, passed 96, 0 failed, 0 skipped, and printed no warnings summary.

```
Sections:
  core           37 passed    0 failed    0 skipped
Sections:
  tooling        59 passed    0 failed    0 skipped
  core           37 passed    0 failed    0 skipped
```

G2, run immediately after G1: exit 0, `TOTAL` 67 statements, 0 miss, 100%.

G3: `96 passed in 0.12s`.

G4: `docket 0.1.0`.

G6: no output.

G7 before this report: `docs/progress.md` and the six `src/docket` modules. After this report, that set plus `docs/reviews/phase-00-skeleton.md`.

G8: the freeze list is `docket`, the `pyproject.toml` dependencies and their dependencies (`pydantic-settings`, `typer`, `keyring`, `pytest`, `pytest-cov`, `ruff`, and the packages those require), and `pip`. No other packages. `setuptools` is not installed; the gate allows it and does not require it.

## Probe

`.venv/bin/python docs/verification/probe-00.py`: every line ended in `ok`, including `oracle: ok`. Last line: `FAILURES 0`.

## Searches

Q1 through Q7 each printed nothing.

## Spot checks

Each deciding test failed with the guide's broken value. Modules were copied outside the repository, restored from those copies, and `src/docket/__pycache__` was removed. `git status --short` and `git diff HEAD` matched the pre-check diff.

- S1: `assert 493 == 448` (`0o755` left in place).
- S2: `ConfigError` was not raised.
- S3: both reads were `.../data`.
- S4: the default was the home directory from import, not the test's temporary home.
- S5: `__suppress_context__` was `False`.
- S6: `calls == [('docket', 'Google')]`.
- S7: `SecretMissing` was not raised.
- S8: `KeyringError` propagated.
- S9: `SecretMissing` for a 65-character name.
- S10: output was `0.1.0\n`.
- S11: `tzinfo` was `None`.
