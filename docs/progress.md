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

## Phase 1f: State commands (2026-11-14)
- Tests: 414 -> 466 (given 52)
- New public names: `docket.views`: `change_text`; `docket.cli`: `start`, `done`, `cancel`, `reopen`
- Changed files: 3
- Deviations:
  - start, done, cancel and reopen share one helper that checks the zone, opens the store, and calls change_state with actor owner.
- Follow-ups:
  - None

## Phase 1g: Edit and plan (2026-11-14)
- Tests: 466 -> 522 (given 56)
- New public names: `docket.views`: `edited_text`, `planned_text`; `docket.cli`: `NOTHING_TO_EDIT_MESSAGE`, `BOTH_DUES_MESSAGE`, `PLAN_NEEDS_MESSAGE`, `CLEAR_ALONE_MESSAGE`, `PLAN_DATE_MESSAGE`, `PLAN_TIME_MESSAGE`, `MINUTES_MESSAGE`, `MIDNIGHT_MESSAGE`, `edit`, `plan`
- Changed files: 3
- Deviations:
  - edit and plan share one helper that opens the store and calls edit_task with actor owner.
  - A length refusal and a midnight refusal are told apart by DeadlineError's text.
- Follow-ups:
  - None

## Phase 2a: Keyed intake (2026-11-14)
- Tests: 522 -> 579 (given 57)
- New public names: `docket.store`: `UNKNOWN_LINK_MESSAGE`, `Link`, `RequestKey`, `insert_link`, `links`, `insert_request_key`, `request_key`; `docket.core`: `INVALID_CLIENT`, `INVALID_KEY`, `KEY_REUSED`, `LinkOutcome`, `create_task_once`, `add_link`
- Changed files: 3
- Deviations:
  - create_task_once writes the task and its create audit row itself, so the key is recorded in that same transaction.
  - A link id is l followed by a non-zero number, the same shape as a task id.
- Follow-ups:
  - None

## Phase 2b: Intake rules (2026-11-14)
- Tests: 579 -> 634 (given 55)
- New public names: `docket.intake`: `MISSING_KEY`, `INVALID_BODY`, `INVALID_DEADLINE`, `Answer`, `accept_task`, `accept_link`
- Changed files: 2
- Deviations:
  - accept_task and accept_link share the key check and the map from a core code to a status.
- Follow-ups:
  - None

## Phase 2c: HTTP routes and client tokens (2026-11-14)
- Tests: 634 -> 703 (given 69)
- New public names: `docket.keychain`: `VALUE_MESSAGE`, `set_secret`; `docket.clients`: `CLIENTS`, `ALREADY_MESSAGE`, `UNKNOWN_CLIENT_MESSAGE`, `ClientError`, `token_name`, `issue_token`, `client_tokens`; `docket.cli`: `clients_app`, `add_client`; `docket.web`: `WRONG_HOST`, `NOT_FOUND`, `UNAUTHORIZED`, `TOO_LARGE`, `INVALID_JSON`, `MAX_BODY`, `create_app`
- Changed files: 5
- Deviations:
  - The clients add command is the function add_client, so it does not clash with tasks add.
  - The OpenAPI, ReDoc and schema routes are turned off.
  - A secret value is refused when it contains a newline or a carriage return.
- Follow-ups:
  - None

## Phase 2d: Serve (2026-11-14)
- Tests: 703 -> 732 (given 24)
- New public names: `docket.config`: `WEB_PORT_MESSAGE`, `web_port`; `docket.server`: `NO_CLIENTS_MESSAGE`, `ServeError`, `build_app`, `run_app`; `docket.cli`: `serve`
- Changed files: 7
- Deviations:
  - serve reports ConfigError, KeychainUnavailable, ServeError and StoreError through one handler.
- Follow-ups:
  - None

## Phase 2e: Phase tooling (2026-11-15)
- Tests: 732 -> 795 (given 55)
- New public names: `docket.reports`: `ENTRY_MESSAGE`, `format_entry`, `put_entry`; `docket.acceptance`: `HEADING_MESSAGE`, `MAX_DETAIL`, `Row`, `read_rows`, `digest`, `accept`; `docket.spotcheck`: `MATCH_MESSAGE`, `SpotError`, `mutate`, `spot_check`, `verdict`
- Changed files: 11
- Deviations:
  - An empty progress file is written as the entry alone, with no leading blank line.
- Follow-ups:
  - None

## Phase 2f: Authenticated client identity (2026-11-17)
- Tests: 795 -> 837 (given 41)
- New public names: None
- Changed files: 6
- Deviations:
  - None
- Follow-ups:
  - None

## Phase 2g: Safe email references (2026-11-17)
- Tests: 837 -> 927 (given 84)
- New public names: `docket.references`: `MESSAGE_ID_MAX`, `LINK_MAX`, `valid_reference`
- Changed files: 5
- Deviations:
  - None
- Follow-ups:
  - None

## Phase 2h: Nonblocking HTTP and bounded reads (2026-11-17)
- Tests: 927 -> 960 (given 30)
- New public names: None
- Changed files: 3
- Deviations:
  - None
- Follow-ups:
  - None

## Phase 2i: Safe store startup and reads (2026-11-17)
- Tests: 960 -> 1042 (given 76)
- New public names: None
- Changed files: 4
- Deviations:
  - None
- Follow-ups:
  - None

## Phase 2j: Shared creation and serialization (2026-11-17)
- Tests: 1042 -> 1074 (given 25)
- New public names: `docket.serialization`: `canonical_json`
- Changed files: 5
- Deviations:
  - None
- Follow-ups:
  - None

## Phase 2k: Shared domain rules and parsing (2026-11-17)
- Tests: 1074 -> 1170 (given 87)
- New public names: `docket.domain`: `STATES`, `OPEN_STATES`, `ENDED_STATES`, `SOURCES`, `CORE_CLIENTS`, `ACTORS`, `STATE_ACTIONS`, `AUDIT_ACTIONS`, `PROVIDERS`, `SOURCE_ACTORS`, `STATE_LABELS`, `FORBIDDEN_TEXT_CATEGORIES`, `TITLE_MAX`, `REQUEST_KEY_MAX`, `WORK_MINUTES_MIN`, `WORK_MINUTES_MAX`, `zone_names`; `docket.parsing`: `ParseError`, `parse_date`, `parse_time`; `docket.config`: `SETTINGS_MESSAGE`
- Changed files: 12
- Deviations:
  - The unchanged intake replay status is written as 201 minus 1 so intake has no literal 200.
- Follow-ups:
  - None

## Phase 2l: Audit, link and request-key boundaries (2026-11-17)
- Tests: 1170 -> 1193 (given 18)
- New public names: None
- Changed files: 6
- Deviations:
  - Private SQL entry points are insert_audit/select_audit, insert_link/select_links/select_existence/select_link, and insert_request_key/select_request_key.
- Follow-ups:
  - None

## Phase 2m: Task table boundary (2026-11-17)
- Tests: 1193 -> 1223 (given 26)
- New public names: None
- Changed files: 4
- Deviations:
  - Private task SQL entry points are insert_task, update_task, select_task, select_tasks, select_tasks_in_states, and select_existence.
- Follow-ups:
  - None

## Phase 2n: Repository phase tooling (2026-11-17)
- Tests: 1223 -> 1261 (given 33)
- New public names: None
- Changed files: 27
- Deviations:
  - The put-entry import is parenthesized so docket_tools.reports fits the line length; its AST matches the manifest.
- Follow-ups:
  - None

## Phase 2o: Shared product test support (2026-11-18)
- Tests: 1261 -> 1295 (given 32)
- New public names: tests.support: path, store, refused
- Changed files: 4
- Deviations:
  - None
- Follow-ups:
  - None

## Phase 2p: Product test consolidation (2026-11-18)
- Tests: 1295 -> 1321 (given 24)
- New public names: None
- Changed files: 16
- Deviations:
  - None
- Follow-ups:
  - None

## Phase 2q: Product behaviour test paths (2026-11-18)
- Tests: 1321 -> 1349 (given 28)
- New public names: None
- Changed files: 17
- Deviations:
  - None
- Follow-ups:
  - None

## Phase 3a: Deterministic reminder planning (2026-11-18)
- Tests: 1349 -> 1382 (given 30)
- New public names: docket.reminders: LATE_MINUTES, PlannedReminder, plan_reminders
- Changed files: 3
- Deviations:
  - None
- Follow-ups:
  - None

## Phase 3b: Durable reminder plans (2026-11-18)
- Tests: 1382 -> 1472 (given 83)
- New public names: docket.core: INVALID_REMINDER_PLAN; docket.store: Reminder, insert_reminders, void_reminders, reminders
- Changed files: 5
- Deviations:
  - A combined edit writes the deadline reminder group before the start group.
- Follow-ups:
  - None

## Phase 3c: Claimed reminder sending (2026-11-18)
- Tests: 1472 -> 1558 (given 80)
- New public names: docket.store: Post, due_reminders, queue_post, claim_posts, release_post, mark_post_sent, posts; docket.reminders: CLAIM_MINUTES, notice_text, send_due
- Changed files: 6
- Deviations:
  - None
- Follow-ups:
  - None

## Phase 3d: Daily digest (2026-11-18)
- Tests: 1558 -> 1650 (given 87)
- New public names: docket.store: DailyDigest, digest, queue_digest, claim_digest, release_digest, mark_digest_sent; docket.reminders: digest_slot, digest_heading, send_digest
- Changed files: 5
- Deviations:
  - None
- Follow-ups:
  - None

## Phase 3e: Reminder loop (2026-11-18)
- Tests: 1650 -> 1670 (given 17)
- New public names: docket.reminders: LOOP_SECONDS, PassResult, Stop, run_pass, run_loop
- Changed files: 3
- Deviations:
  - None
- Follow-ups:
  - None

## Phase 6a: MCP read tools (2026-11-21)
- Tests: 1670 -> 1719 (given 40)
- New public names: docket.reads: STATUSES, PAGE_SIZE, INVALID_STATUS, INVALID_CURSOR, UNKNOWN_TASK, ReadRefused, TaskPage, TaskRecord, list_tasks, task_record; docket.mcp_server.server: SERVER_NAME, INSTRUCTIONS, LIST_TASKS, GET_TASK, build_server, serve, DeadlineResult, WorkResult, TaskResult, TaskPageResult, ReminderResult, TaskDetailResult
- Changed files: 7
- Deviations:
  - None
- Follow-ups:
  - None

## Phase 6b: Retire the freeze manifests (2026-11-21)
- Tests: 1719 -> 1653 (given 35)
- New public names: None
- Changed files: 18
- Deviations:
  - None
- Follow-ups:
  - None

## Phase 6c: Core input checks (2026-11-21)
- Tests: 1653 -> 1707 (given 53)
- New public names: docket.core: INVALID_DEADLINE, INVALID_WORK
- Changed files: 5
- Deviations:
  - None
- Follow-ups:
  - None

## Phase 6d: MCP write tools (2026-11-21)
- Tests: 1707 -> 1775 (given 67)
- New public names: docket.writes: INVALID_DEADLINE, UNKNOWN_TASK, WriteRefused, parse_deadline, create_task, complete_task, cancel_task; docket.core: change_state_once; docket.mcp_server.server: CREATE_TASK, COMPLETE_TASK, CANCEL_TASK, DeadlineInput, TaskChangeResult
- Changed files: 8
- Deviations:
  - None
- Follow-ups:
  - None
