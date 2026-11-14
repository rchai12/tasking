# Phase 0: skeleton

## Goal

Make `docket` an installable, tested Python package with the check tooling every later phase uses, and the four seams every later phase builds on: one place for the current time, one for new ids, one for settings (including a private data folder), and one for reading secrets from the Keychain.

Sections: `core`. The `tooling` section (the report checker's tests) runs in the full check.

Follow `docs/phase-conventions.md`. In this phase N is 0: there is no `.venv` and no check run before you start.

## Facts

- **Python.** Python 3.12 is `/opt/homebrew/bin/python3.12` (3.12.16). `python3` on this machine is 3.15.1 and must not be used; `python` does not exist.
- **Versions** found on 2026-11-14 in a scratch environment with the bounds of `pyproject.toml`: keyring 25.7.0, pydantic-settings 2.16.3, typer 0.29.1, pytest 9.2.0, pytest-cov 7.1.0, ruff 0.17.5.
- **keyring 25.7.** `keyring.get_password(service, username)` returns `None` when nothing is stored. Every error it raises is a subclass of `keyring.errors.KeyringError`: `KeyringLocked` when access is denied, `NoKeyringError` from the failing backend. It looks up the backend on every call through `keyring.core.get_keyring()`, which is why tests can replace `keyring.core._keyring_backend` (and `tests/conftest.py` does, so no test can reach the real Keychain).
- **Typer.** An app with exactly one command and no callback treats that command as the whole program, so `docket version` exits with code 2. The app needs a `@app.callback()`.
- **pydantic-settings 2.16** reads `DOCKET_`-prefixed environment variables with `env_prefix="DOCKET_"`.
- **`Path.home()`** reads `HOME`, which `tests/conftest.py` sets to a temporary folder for each test, so a default computed from `Path.home()` must be computed when settings are read, not when the module is imported.

## Owner's decisions

- Tooling, roles and layout follow the sibling projects (`finances`, `emails`, `langgraph`), decided 2026-11-14: Python 3.12 in `.venv`, setuptools, pytest with pytest-cov, ruff, one spec and one verification guide per phase.
- The package and command are `docket` (assumed in `docs/open-questions.md`; the owner has not changed it).
- The email service's Phase 0 tooling is reused, adapted: `scripts/check.py`, `scripts/check_reports.py` and the report checker with its tests.

## Architect's decisions

- **Phase 0 matches the email service's Phase 0**, which passed review: the same four seams with the same rules, so the projects stay alike. Settings beyond the data folder (the time zone, the port, the owner's Discord id) come with the phase that first reads them.
- **Phase ids** are unpadded (`0`, `1a`); file names pad them to two digits (`phase-00-skeleton.md`). The report checker allows phase `0`.
- **Given files are committed** with this spec, not embedded in it. The 18 files below are already in the repository.
- **The data folder** defaults to `~/Library/Application Support/docket`, outside the repository, mode exactly `0o700`, created or tightened by `prepare_data_dir`, whatever the umask.
- **Secret names** are 1 to 64 characters: a lowercase letter, then lowercase letters, digits, `.`, `_` or `-`. The whole name must match; a trailing newline is not allowed. The keychain item is service `docket`, account = the secret's name.
- **Errors name only the key.** `SecretMissing` and `KeychainUnavailable` share the base `KeychainError`. A keyring error is replaced, not chained (`raise ... from None`), because a library's error text could contain more than a name.
- **Settings are read on each call** to `get_settings()` (no cache), so tests and the launchd environment always agree with the environment.
- **Critical modules:** `reports.py`, `config.py`, `keychain.py` (`scripts/critical_modules.txt`).

## Requirements

1. **Install.** Create the environment with `/opt/homebrew/bin/python3.12 -m venv .venv` and install with `.venv/bin/python -m pip install -e '.[dev]'` (this step needs the network to reach PyPI; nothing else in this phase does). Install nothing else.
2. **`src/docket/__init__.py`** contains `__version__ = "0.1.0"` and no imports.
3. **`src/docket/clock.py`**: `now() -> datetime` returns the current moment as an aware datetime in UTC (`tzinfo` is `datetime.UTC`).
4. **`src/docket/ids.py`**: `new_id() -> str` returns a new random id of 32 lowercase hex characters (`uuid.uuid4().hex`).
5. **`src/docket/config.py`, settings**:
   - `class Settings` (a pydantic-settings `BaseSettings`, prefix `DOCKET_`) with one field, `data_dir: Path`.
   - Default `data_dir`: `Path.home() / "Library" / "Application Support" / "docket"`, computed when settings are read.
   - A leading `~` in `DOCKET_DATA_DIR` is the home folder (`~` alone, or `~/...`).
   - `get_settings() -> Settings` builds new settings on every call.
   - If `data_dir` is not absolute after `~` is expanded, `get_settings()` raises `ConfigError` whose text is exactly `DATA_DIR_MESSAGE` = `"DOCKET_DATA_DIR must be an absolute path"`. No pydantic `ValidationError` escapes, and its text is not chained (`from None`).
6. **`src/docket/config.py`, data folder**: `prepare_data_dir(settings: Settings) -> Path` creates `settings.data_dir` and any missing parents, sets the data folder's own mode to exactly `0o700` (new or existing, under any umask), and returns `settings.data_dir`. Calling it again is harmless. It changes the mode of the data folder only, never of its parents.
7. **`src/docket/keychain.py`, names**: `SERVICE = "docket"`, `NAME_MESSAGE = "invalid secret name"`. `get_secret(name: str) -> str` raises `ValueError(NAME_MESSAGE)` for a name that breaks the rule above, before any keychain call.
8. **`src/docket/keychain.py`, reading**: for a valid name, `get_secret` calls `keyring.get_password(SERVICE, name)` (on every call; nothing cached) and returns the value.
   - `None` or `""` raises `SecretMissing` with text `"secret not found: <name>"`.
   - Any `keyring.errors.KeyringError` raises `KeychainUnavailable` with text `"keychain unavailable: <name>"`, `from None`.
   - Any other exception propagates unchanged.
   - `KeychainError(Exception)` is the base of both. The module never writes or deletes keychain items.
9. **`src/docket/cli.py`**: `app` is a `typer.Typer` with a `@app.callback()` and one command, `version`, which prints `docket <__version__>` and a newline (`docket 0.1.0`). `pyproject.toml` already maps the `docket` command to `docket.cli:app`.
10. **Progress entry** for `## Phase 0: skeleton (YYYY-MM-DD)` at the end of `docs/progress.md`, in the form `docs/phase-conventions.md` gives.

## Given files

Already committed; never change them.

| File | What it is |
|---|---|
| `pyproject.toml` | Package metadata, dependencies, the `docket` command, ruff, pytest and coverage settings |
| `scripts/check.py` | Lint, format, tests by section, overall and critical coverage (from the email service) |
| `scripts/check_reports.py` | Checks the form of progress entries and reviews |
| `scripts/critical_modules.txt` | The critical modules: `reports.py`, `config.py`, `keychain.py` |
| `src/docket/reports.py` | The report checker's module (from the email service; allows phase `0`) |
| `tests/conftest.py` | Blocks the network and the real Keychain; isolates `HOME`, `DOCKET_*` and the data folder; the `fake_keychain` fixture |
| `tests/fakes.py` | `FakeKeychain`; imports nothing from `docket` |
| `tests/support.py` | `run`, `runner`, `fixed_times`, `fixed_ids` |
| `tests/sections.toml` | Sections `tooling` (report tests) and `core` (everything else) |
| `tests/unit/test_reports.py`, `test_reports_more.py`, `test_reports_phase.py`, `test_reports_phase_more.py` | The report checker's tests: 59 |
| `tests/unit/test_clock_ids.py` | 5 tests (requirements 3, 4, and the given helpers) |
| `tests/unit/test_config.py` | 10 tests (requirements 5, 6) |
| `tests/unit/test_keychain.py` | 19 tests (requirements 7, 8) |
| `tests/unit/test_cli.py` | 3 tests (requirements 1, 2, 9) |
| `docs/verification/probe-00.py` | The verifier's probe (you may run it; never change it) |

Given test count: **96**.

## Tests to write

The given tests cover every requirement. If coverage of a module you write falls short, add a behaviour test in a new file under `tests/unit/` (for example `tests/unit/test_config_more.py`), never by changing a given test.

## Scope

| Path | Change |
|---|---|
| `src/docket/__init__.py` | create |
| `src/docket/clock.py` | create |
| `src/docket/ids.py` | create |
| `src/docket/config.py` | create |
| `src/docket/keychain.py` | create |
| `src/docket/cli.py` | create |
| `tests/unit/test_*_more.py` | create, only if coverage needs them |
| `docs/progress.md` | append your entry |

`.venv/`, `*.egg-info/`, `.coverage` and caches are gitignored and do not appear in `git status --short`.

## Out of scope

- Writing or deleting secrets, and any command that stores one (a later phase adds it with the first sign-in).
- Any setting other than `data_dir` (the time zone, the port, the owner's Discord id, the digest time); caching settings.
- Logging, a `doctor` or `status` command, a `--version` flag, or any command other than `version`.
- The database, tasks, deadlines, the API, reminders, Discord, calendars, the MCP server, a launchd file.
- Fakes beyond `FakeKeychain`.
- Any change to a given file, `AGENTS.md` or the design docs.

## Rules that bite

- **Never read the real Keychain.** Do not call `get_secret` or `keyring` outside the tests, not even to try it: `.venv/bin/python -c "..."` against the real Keychain is forbidden (`AGENTS.md` rule 6).
- **Error messages are constant text plus the identifier**: never a value, never a library's error text.
- **Time and ids through the module**: nothing outside `clock.py` reads the time, and nothing outside `ids.py` makes a uuid.
- Commands start with `.venv/bin/python`; no bare `python3`, `pytest` or `ruff`.

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 96 passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest tests/unit/test_reports.py tests/unit/test_reports_more.py tests/unit/test_reports_phase.py tests/unit/test_reports_phase_more.py tests/unit/test_clock_ids.py tests/unit/test_config.py tests/unit/test_keychain.py tests/unit/test_cli.py --no-cov -q` | `96 passed` |
| `.venv/bin/python -m coverage report --include=src/docket/__init__.py,src/docket/clock.py,src/docket/ids.py,src/docket/config.py,src/docket/keychain.py,src/docket/cli.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| `.venv/bin/docket version` | `docket 0.1.0` |
| `.venv/bin/python docs/verification/probe-00.py` | last line `FAILURES 0` |
| `grep -c "^## Phase 0: " docs/progress.md` | `1` |
| `.venv/bin/python scripts/check_reports.py --phase 0` | `Reports OK.` |
| `git diff HEAD --stat -- pyproject.toml scripts src/docket/reports.py tests/conftest.py tests/fakes.py tests/support.py tests/sections.toml tests/unit/test_reports.py tests/unit/test_reports_more.py tests/unit/test_reports_phase.py tests/unit/test_reports_phase_more.py tests/unit/test_clock_ids.py tests/unit/test_config.py tests/unit/test_keychain.py tests/unit/test_cli.py docs/verification/probe-00.py` | no output |
| `git status --short` | only the Scope paths |

### Searches

Each prints nothing.

```zsh
git grep --untracked -n -E 'set_password|delete_password|set_keyring\(|keyring\.core' -- src
git grep --untracked -n -E 'datetime\.now|datetime\.utcnow|date\.today|time\.time\(|uuid[0-9]' -- src ':!src/docket/clock.py' ':!src/docket/ids.py'
git grep --untracked -n -E 'from docket\.(clock|ids) import' -- src
git grep --untracked -n -E 'import (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)' -- src
git grep --untracked -n -E 'os\.environ|getenv\(' -- src ':!src/docket/config.py'
git grep --untracked -n -E 'print\(|logging|logger' -- src ':!src/docket/cli.py'
git grep --untracked -n -E 'pragma: no cover' -- src
```
