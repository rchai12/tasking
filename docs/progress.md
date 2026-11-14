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

## Phase 1a: Time rules (2026-11-14)
- Tests: 96 -> 152 (given 56)
- New public names: `docket.deadlines`: `DEFAULT_TIME`, `DUE_WINDOW`, `WORK_MINUTES_MIN`, `WORK_MINUTES_MAX`, `ZONE_MESSAGE`, `TIME_MESSAGE`, `INSTANT_MESSAGE`, `WORK_LENGTH_MESSAGE`, `WORK_DAY_MESSAGE`, `WORK_DEADLINE_MESSAGE`, `DeadlineError`, `Deadline`, `WorkTime`, `make_deadline`, `make_work_time`, `status`
- Changed files: 2
- Deviations:
  - Zone names are cached with functools.cache.
  - make_work_time uses WorkTime's length check, so a stored value and a new work time share that rule.
- Follow-ups:
  - None

## Phase 1b: Task store (2026-11-14)
- Tests: 152 -> 202 (given 50)
- New public names: `docket.store`: `DB_FILENAME`, `SCHEMA_MESSAGE`, `TRANSACTION_MESSAGE`, `NESTED_MESSAGE`, `UNKNOWN_TASK_MESSAGE`, `UNCHANGED`, `StoreError`, `Task`, `AuditEntry`, `Store`, `open_store`
- Changed files: 2
- Deviations:
  - Migration SQL is split with sqlite3.complete_statement so each trigger stays one statement inside the transaction.
  - A task id matches re.fullmatch of t followed by a non-zero ASCII number.
- Follow-ups:
  - None

## Phase 1c: Task rules (2026-11-14)
- Tests: 202 -> 291 (given 89)
- New public names: `docket.core`: `UNKNOWN_TASK`, `INVALID_TITLE`, `INVALID_SOURCE`, `INVALID_REFERENCE`, `INVALID_ACTOR`, `INVALID_ACTION`, `TASK_ENDED`, `WORK_AFTER_DEADLINE`, `CoreError`, `Outcome`, `check_title`, `create_task`, `change_state`, `edit_task`
- Changed files: 2
- Deviations:
  - An email reference checks the message id and link before the provider, still as one INVALID_REFERENCE.
  - A non-email reference is refused unless provider, message id and link are all None.
- Follow-ups:
  - None

## Phase 1d: Settings and display text (2026-11-14)
- Tests: 291 -> 345 (given 54)
- New public names: `docket.config`: `TIME_ZONE_MESSAGE`, `TIME_ZONE_UNSET_MESSAGE`, `WORK_MINUTES_MESSAGE`, `home_zone`; `docket.views`: `when`, `deadline_text`, `work_text`, `status_text`
- Changed files: 3
- Deviations:
  - An empty time zone becomes None before the name is checked against available_timezones().
  - DOCKET_WORK_MINUTES uses Field bounds of 5 to 720, and get_settings maps that field's error to WORK_MINUTES_MESSAGE.
- Follow-ups:
  - None

## Phase 1e: Adding and listing tasks (2026-11-14)
- Tests: 345 -> 414 (given 66)
- New public names: `docket.views`: `task_line`, `task_detail`, `refusal_text`; `docket.cli`: `DUE_MESSAGE`, `AT_MESSAGE`, `AT_WITHOUT_DUE_MESSAGE`, `NO_TASKS_MESSAGE`, `tasks_app`, `add`, `list_tasks`, `show`
- Changed files: 1
- Deviations:
  - list and show open the store before the clock read, so a newer schema exits without reading the clock.
  - A date and a time share one shape check before fromisoformat.
- Follow-ups:
  - None
