# Verification guide: Phase 0 (skeleton)

Spec: `docs/phases/phase-00-skeleton.md`. Follow `docs/phase-conventions.md` ("For the verifier"). Never call `get_secret` or `keyring` against the real Keychain, and never connect to Google, Microsoft Graph, the shared Discord service, Discord, the email service or Conductor.

## 1. Coder ran

Stop with FAIL ("the coder did not run") if any of these is missing:

- `src/docket/__init__.py`, `clock.py`, `ids.py`, `config.py`, `keychain.py`, `cli.py`
- `.venv/bin/python` and `.venv/bin/docket`
- `grep -c "^## Phase 0: " docs/progress.md` prints `1`

Stop with FAIL ("the baseline is not committed") if `git ls-files --error-unmatch docs/phases/phase-00-skeleton.md pyproject.toml tests/conftest.py docs/verification/probe-00.py` fails: G6 and G7 can only be judged against a committed spec and given files.

## 2. Gates

Run each from the repository root, in this order.

| # | Command | Must show |
|---|---|---|
| G1 | `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; `tests (core): passed`; in the `tests` step at least 96 passed, 0 failed, 0 skipped, no warnings summary; every `Sections:` line 0 failed |
| G2 | `.venv/bin/python -m coverage report --include=src/docket/__init__.py,src/docket/clock.py,src/docket/ids.py,src/docket/config.py,src/docket/keychain.py,src/docket/cli.py --fail-under=100` (right after G1) | exit 0, `TOTAL` at `100%` |
| G3 | `.venv/bin/python -m pytest tests/unit/test_reports.py tests/unit/test_reports_more.py tests/unit/test_reports_phase.py tests/unit/test_reports_phase_more.py tests/unit/test_clock_ids.py tests/unit/test_config.py tests/unit/test_keychain.py tests/unit/test_cli.py --no-cov -q` | `96 passed` |
| G4 | `.venv/bin/docket version` | `docket 0.1.0` |
| G5 | `.venv/bin/python scripts/check_reports.py --phase 0` (after writing the report) | `Reports OK.` |
| G6 | `git diff HEAD --stat -- pyproject.toml scripts src/docket/reports.py tests/conftest.py tests/fakes.py tests/support.py tests/sections.toml tests/unit/test_reports.py tests/unit/test_reports_more.py tests/unit/test_reports_phase.py tests/unit/test_reports_phase_more.py tests/unit/test_clock_ids.py tests/unit/test_config.py tests/unit/test_keychain.py tests/unit/test_cli.py docs/verification/probe-00.py` | no output |
| G7 | `git status --short` | only: the six `src/docket/` modules above, `docs/progress.md`, any `tests/unit/test_*_more.py`, and your report |
| G8 | `.venv/bin/python -m pip list --format=freeze` | no packages beyond `docket`, the dependencies of `pyproject.toml` (with their own dependencies), `pip` and `setuptools` |

## 3. Spot checks

For each row: copy the module outside the repository, make the change described in the module the coder wrote (the one line that does what the "Change" cell names), run the deciding test with `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest <test> --no-cov -vv`, and confirm it fails with the "Broken" value. Then restore the module from your copy, delete `src/docket/__pycache__`, and confirm `git diff` is as before. A different failure from the "Broken" column is a note, not a finding; a pass is a finding.

| # | Module | Change | Deciding test | Correct | Broken |
|---|---|---|---|---|---|
| S1 | `config.py` | drop the step that sets the mode of an existing folder (keep only creating it) | `tests/unit/test_config.py::test_prepare_makes_an_existing_data_dir_private` | `0o700` (448) | `0o755` (493) |
| S2 | `config.py` | drop the absolute-path check | `tests/unit/test_config.py::test_a_relative_data_dir_is_refused[data]` | `ConfigError` raised | no exception: `data_dir` is `Path('data')` |
| S3 | `config.py` | cache `get_settings()` (for example `functools.cache`) | `tests/unit/test_config.py::test_settings_are_read_again_on_each_call` | `(…/data, …/other)` | `(…/data, …/data)` |
| S4 | `config.py` | compute the default from `Path.home()` once, at import | `tests/unit/test_config.py::test_the_default_data_dir_is_in_application_support` | the test's own `tmp_path/home/…` | the first test's home, or the real home |
| S5 | `keychain.py` | raise `KeychainUnavailable` without `from None` | `tests/unit/test_keychain.py::test_a_keychain_failure_hides_the_backend_text[error]` | `__suppress_context__` is `True` | `False` |
| S6 | `keychain.py` | check the name after the keychain call instead of before | `tests/unit/test_keychain.py::test_an_invalid_name_is_refused_before_the_keychain[capital]` | `calls == []` | `[('docket', 'Google')]` |
| S7 | `keychain.py` | treat only `None` as missing (an empty value is returned) | `tests/unit/test_keychain.py::test_an_empty_secret_is_missing` | `SecretMissing` | returns `''` |
| S8 | `keychain.py` | catch only `KeyringLocked` instead of `KeyringError` | `tests/unit/test_keychain.py::test_a_keychain_failure_hides_the_backend_text[error]` | `KeychainUnavailable` | `KeyringError` propagates |
| S9 | `keychain.py` | allow 65 characters instead of 64 | `tests/unit/test_keychain.py::test_an_invalid_name_is_refused_before_the_keychain[too-long]` | `ValueError` | `SecretMissing` |
| S10 | `cli.py` | print the version without the name | `tests/unit/test_cli.py::test_version_prints_the_name_and_version` | `'docket 0.1.0\n'` | `'0.1.0\n'` |
| S11 | `clock.py` | return `datetime.now()` (naive) | `tests/unit/test_clock_ids.py::test_now_is_an_aware_utc_moment` | `tzinfo` is `UTC` | `None` |

## 4. Probe

Run `.venv/bin/python docs/verification/probe-00.py` from the repository root, without editing it. Every line must end in `ok`; the last line must be `FAILURES 0`. A stop at the `assert` lines before `oracle: ok` is the probe's fault: report it under "For the architect", not as a finding. The probe installs its own fake keychain and temporary folders before it imports `docket`; it never reads the real Keychain. It checks what the given tests do not reach: names with newlines, tabs, non-ASCII letters and digits; any `KeyringError` subclass hidden; `~` alone; a trailing slash; the folder private under umask 000 and 077; preparing twice; the installed command.

## 5. Searches

Each prints nothing. A match is a finding against the rule it names.

| # | Rule | Command |
|---|---|---|
| Q1 | the keychain is only read, through `keyring.get_password` | `git grep --untracked -n -E 'set_password\|delete_password\|set_keyring\(\|keyring\.core' -- src` |
| Q2 | time and ids only in `clock.py` and `ids.py` | `git grep --untracked -n -E 'datetime\.now\|datetime\.utcnow\|date\.today\|time\.time\(\|uuid[0-9]' -- src ':!src/docket/clock.py' ':!src/docket/ids.py'` |
| Q3 | time and ids read through the module | `git grep --untracked -n -E 'from docket\.(clock\|ids) import' -- src` |
| Q4 | no network code in this phase | `git grep --untracked -n -E 'import (socket\|ssl\|http\|urllib\|requests\|httpx)([^A-Za-z_]\|$)' -- src` |
| Q5 | settings come only from `get_settings()` | `git grep --untracked -n -E 'os\.environ\|getenv\(' -- src ':!src/docket/config.py'` |
| Q6 | no output or logging outside the CLI | `git grep --untracked -n -E 'print\(\|logging\|logger' -- src ':!src/docket/cli.py'` |
| Q7 | no coverage exclusions | `git grep --untracked -n -E 'pragma: no cover' -- src` |

(In the table, `\|` is a `|` in the command.)

## 6. Reasonable variations

These are correct even though the spec does not spell them out:

- The default `data_dir` as a `default_factory`, a validator, or a computed default, as long as it is computed when settings are read.
- `~` expanded with `Path.expanduser()` in a validator, or in `get_settings()`.
- The name rule written as one `re.fullmatch`, or as character sets; any form that matches the whole name.
- `os.makedirs` or `Path.mkdir(parents=True, exist_ok=True)`, followed by `chmod(0o700)`.
- `typer.echo` or `print` in `cli.py`; `no_args_is_help=True` or not; a docstring on the callback.
- Exception messages set through `__init__` or passed when raising.
- Private helpers inside the Scope modules, and extra behaviour tests in `tests/unit/test_*_more.py`.

## 7. Verdict

Write `docs/reviews/phase-00-skeleton.md` in the form `docs/phase-conventions.md` gives (`# Review: Phase 0`), then run `.venv/bin/python scripts/check_reports.py --phase 0`; it must print `Reports OK.`
