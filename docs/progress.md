# Progress

One entry per phase, written by the coder, in the form `docs/phase-conventions.md` gives.

## Phase 0: skeleton (2026-11-14)
- Tests: 0 -> 96 (given 96)
- New public names: `docket`: `__version__`; `docket.clock`: `now`; `docket.ids`: `new_id`; `docket.config`: `DATA_DIR_MESSAGE`, `ConfigError`, `Settings`, `get_settings`, `prepare_data_dir`; `docket.keychain`: `SERVICE`, `NAME_MESSAGE`, `KeychainError`, `SecretMissing`, `KeychainUnavailable`, `get_secret`; `docket.cli`: `app`, `version`
- Changed files: 7
- Deviations:
  - data_dir uses a default_factory, and a leading ~ is expanded with Path.expanduser() in a validator.
  - Secret names use one re.fullmatch: a lowercase letter, then up to 63 of [a-z0-9._-].
  - prepare_data_dir uses Path.mkdir(parents=True, exist_ok=True), then chmod 0o700.
  - version prints with print; the Typer callback is _callback and has a docstring.
- Follow-ups:
  - None
