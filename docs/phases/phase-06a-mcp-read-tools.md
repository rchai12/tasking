# Phase 6a: MCP read tools

## Goal

Conductor can launch `docket mcp serve` as a child process and read the owner's tasks over stdio through two tools: `list_tasks(status, after)`, a page of tasks by status, and `get_task(id)`, one task with its sent and pending reminders. Both are marked read-only, declare typed output schemas that Conductor's tool check accepts, and refuse bad input with constant codes. This phase adds the MCP SDK dependency, the read logic in a new `docket.reads` module and the thin server in `docket.mcp_server`. It leaves the write tools with `request_key` to Phases 6b and 6c, and leaves `list_proposals`, `list_events`, `check_availability`, `snooze_task` and a task's calendar event to the stages that build those things.

Sections: `core`. The `tooling` section runs in the full check.

Follow `docs/phase-conventions.md`. N is 1670, the tests the previous phase left passing.

Start: `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_mcp_server.py --ignore=tests/integration/test_mcp_reads.py --ignore=tests/e2e/test_cli_mcp.py` must show `1670 passed`. The ignored files import names you create.

## Facts

Checked on this machine against `mcp` 2.3.0 (read from an existing installation, not installed here) and the code as of Phase 3e.

- **Install.** `.venv/bin/python -m pip install -e ".[dev]"` installs `mcp` 2.3.x and 12 packages it needs that the project lacks: `attrs`, `cffi`, `cryptography`, `jsonschema`, `jsonschema-specifications`, `mcp-types`, `pycparser`, `pyjwt`, `python-multipart`, `referencing`, `rpds-py` and `sse-starlette`. The package count goes from 39 to 52. Everything else `mcp` needs (`anyio`, `httpx2`, `pydantic`, `starlette`, `uvicorn`, `opentelemetry-api`) is already installed.
- **OpenTelemetry.** `mcp` wraps calls in OpenTelemetry spans through `opentelemetry-api`, which `fastapi` already brought in. With no OpenTelemetry SDK or exporter installed, the tracer is a no-op and nothing leaves the process. `test_no_tracing_backend_is_installed` keeps it that way.
- **Server.** `from mcp.server.mcpserver import MCPServer`; `MCPServer(name=..., instructions=..., log_level=...)`; `server.add_tool(fn, description=..., annotations=ToolAnnotations(...), structured_output=True)`; `server.run("stdio")`. `ToolAnnotations` comes from `mcp.types`, with the fields `read_only_hint`, `destructive_hint`, `idempotent_hint` and `open_world_hint`.
- **Sync tools run on worker threads.** The SDK runs a plain `def` tool through `anyio.to_thread.run_sync`. A `Store`'s SQLite connection belongs to the thread that opened it, so a store opened in `build_server` and used inside a tool raises `sqlite3.ProgrammingError`.
- **Refusals.** A tool that raises `mcp.server.mcpserver.exceptions.ToolError("unknown_task")` answers `is_error` true, no structured content, and the one text `Error executing tool get_task: unknown_task`. Any other exception answers only `Error executing tool get_task`.
- **Logging.** On any other exception the SDK logs an ERROR line with a traceback that includes the exception's text, on stderr. `MCPServer.__init__` calls `logging.basicConfig(level=log_level, ...)`; with `log_level="CRITICAL"`, a fresh process wrote 0 bytes to stderr for a failing tool. Under pytest the root logger already has handlers, so `basicConfig` changes nothing there. Docket code needs no `logging` import.
- **Schemas.** A tool whose return annotation is a pydantic `BaseModel` gets an output schema with `properties`, `required` and `$defs`, and its result arrives as `structured_content`. A field typed `X | None` with no default is required and nullable (`anyOf` with `null`). A `Literal` parameter becomes an `enum`, and the SDK's validation message for a value outside it echoes the value; a plain `str` parameter does not.
- **Conductor's tool check** (`langgraph/src/conductor/mcp_client/check.py`) reads `list_tools()`. For each action it compares the top-level properties' JSON types with the tool's input and output schemas, resolving one `$ref` and joining `anyOf` types. It requires `read_only` true for a read action and an output schema for every tool. Each field the action's result requires must be in the tool's `required`.
- **Testing in memory.** `mcp.client.Client(server)` connects to a server object without a process: `await client.list_tools()` and `await client.call_tool(name, arguments)`, with `.is_error`, `.structured_content` and `.content[i].text` on the result. `tests/mcp_cases.py` wraps these in `asyncio.run`.
- **Typer.** A sub-app added with `app.add_typer(mcp_app, name="mcp")` keeps its single command as a subcommand, as `clients add` does.
- **The store's id rule** is `t[1-9][0-9]*`; `Store.task` answers `None` for anything else. `Store.tasks(states)` returns tasks in id order, and `Store.reminders(task_id)` returns them in reminder-id order with `voided_at` set on voided ones.

## Owner's decisions

All decided 2026-11-18.

1. **Stage 6 before Stage 4.** The shared Discord service does not exist yet, so the MCP tools come next.
2. **SDK pin:** `mcp>=2.3,<2.4`, in `[project] dependencies`.
3. **Later tools are left out** until their stages: `list_proposals` (Stage 10), `list_events` and `check_availability` (Stage 8), and `snooze_task` (Stage 4, with the Snooze button).
4. **Due** means open or in progress, with a deadline later today in `DOCKET_TIME_ZONE` that has not yet passed. **Overdue** means open or in progress, with a deadline that has passed.
5. **Reminder history** in `get_task` lists sent and pending reminders, each with its kind and fire time, plus the sent time if sent. Voided reminders are left out.

## Architect's decisions

- **Typed results.** Each tool returns a pydantic model, so its output schema names every field, and Conductor's check can compare them.
- **Plain string parameters, checked in docket.** `status` and `after` are `str`, and the code refuses bad values with constant codes (`invalid_status`, `invalid_cursor`, `unknown_task`). A `Literal` would make the SDK echo the caller's input in its message. A wrong JSON type (a number for `status`) is still answered by the SDK's own validation message. That message goes only to the caller and is never logged or stored; this is a known limit.
- **Decisions in `docket.reads`, not in `mcp_server`.** The status rules, cursor and paging live in `docket.reads`; `docket.mcp_server.server` only builds models from its answers, as `docket.views` does for the command line.
- **Paging by id.** Tasks come in id order, 50 a page. `after` is the last id of the previous page. Id order never changes as time passes, so a cursor stays valid between calls.
- **One store per call.** Each tool call opens the store and closes it before it returns (see Facts: worker threads). `build_server` also opens and closes it once, so a newer schema stops `docket mcp serve` at startup instead of at the first call.
- **Quiet server.** `log_level="CRITICAL"`, so no exception text, title or path reaches stderr. stdout carries only the protocol.
- **Lazy import in the command.** `cli.py` imports `docket.mcp_server` inside `mcp serve`. Other commands don't load the SDK, and `cli.py` imports before the module exists.
- **Deadline as both instant and local parts.** Each deadline carries its UTC instant (`at`) and its `date` and `time` in its own zone, in the shape Conductor's write actions will send (`date`, `time` or null, `time_zone`), so an agent never converts zones itself. `time` is null when no time was given.
- **Not in `get_task` yet:** the calendar event (no events exist before Stage 7) and email links (an agent does not need them).
- **No new critical modules.** `scripts/critical_modules.txt` is unchanged; the write tools in 6b add the MCP modules to it.

## Requirements

1. **Dependency.** The given `pyproject.toml` lists `mcp>=2.3,<2.4`. Install it once with `.venv/bin/python -m pip install -e ".[dev]"`, then run `.venv/bin/python -m pip check`, which must print `No broken requirements found.` Run the Start command before installing. Add nothing else.
2. **`docket.reads` names.** `STATUSES = ("open", "in_progress", "due", "overdue", "done", "cancelled")`, `PAGE_SIZE = 50`, `INVALID_STATUS = "invalid_status"`, `INVALID_CURSOR = "invalid_cursor"`, `UNKNOWN_TASK = "unknown_task"`. `class ReadRefused(Exception)` takes one code: `.code` is that code and `str(error)` is the code alone. Two frozen dataclasses: `TaskPage(tasks: tuple[Task, ...], next_after: str | None)` and `TaskRecord(task: Task, reminders: tuple[Reminder, ...])`.
3. **`reads.list_tasks(store: Store, status: object, after: object, *, zone: str) -> TaskPage`.**
   - **Status** is checked first: anything not a `str` in `STATUSES` raises `ReadRefused(INVALID_STATUS)`.
   - **Cursor:** `after` is `None`, or a task id as the store's id rule accepts it (`t12`). Anything else, the empty string included, raises `ReadRefused(INVALID_CURSOR)`. An id beyond every task is valid and gives an empty page.
   - **Matching:** `open`, `in_progress`, `done` and `cancelled` match tasks in that state. `due` and `overdue` match only open and in-progress tasks with a deadline. Overdue: `deadline.at <= now`. Due: `now < deadline.at`, and the deadline's date in `zone` equals today's date in `zone`.
   - **Page:** matches in id order with a number greater than the cursor's, at most `PAGE_SIZE`. `next_after` is the last id on the page when more matches follow it, else `None`.
   - **Clock:** it reads `clock.now()` exactly once for `due` and `overdue`, and never for the other statuses.
4. **`reads.task_record(store: Store, task_id: object) -> TaskRecord`.** It returns the task and its reminders that are not voided, in reminder-id order. A non-`str`, malformed or unknown id raises `ReadRefused(UNKNOWN_TASK)`. It never reads the clock.
5. **Result models** in `docket.mcp_server.server` are pydantic `BaseModel`s, each field required and none with a default:
   - `DeadlineResult(at: str, date: str, time: str | None, time_zone: str)`
   - `WorkResult(start: str, minutes: int, time_zone: str)`
   - `TaskResult(id: str, title: str, state: str, source: str, deadline: DeadlineResult | None, work: WorkResult | None, created_at: str, updated_at: str)`
   - `TaskPageResult(tasks: list[TaskResult], next_after: str | None)`
   - `ReminderResult(kind: str, fire_at: str, sent_at: str | None)`
   - `TaskDetailResult(TaskResult)`, adding `reminders: list[ReminderResult]`

   Every instant is the stored UTC `datetime`'s `.isoformat()` (`2026-11-20T22:00:00+00:00`). A deadline's `date` is its instant's date in the deadline's own zone, as `.isoformat()`. Its `time` is that local time as `.isoformat(timespec="minutes")` (`22:30`) when the time was given, else `None`. `time_zone` is the deadline's or work time's zone.
6. **Server names.** `SERVER_NAME = "docket"`, `INSTRUCTIONS = "The owner's tasks in docket. These tools only read: none of them changes a task."`, and the two descriptions `test_mcp_server.py` gives as `LIST_TASKS` and `GET_TASK`.
7. **`build_server(settings: Settings) -> MCPServer`.**
   - **Startup:** it takes the zone from `config.home_zone(settings)`, then opens and closes the store once with `open_store(settings)`. A `ConfigError` or `StoreError` passes up unchanged.
   - **Server:** `MCPServer(name=SERVER_NAME, instructions=INSTRUCTIONS, log_level="CRITICAL")`, with exactly two tools added with `structured_output=True` and `ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)`.
   - **The tools:** `list_tasks(status: str, after: str | None = None) -> TaskPageResult`, and `get_task(id: str) -> TaskDetailResult`.
   - **Each call** opens its own store with `open_store(settings)`, calls `reads.list_tasks` with the startup zone, or `reads.task_record`, and closes the store before returning.
   - **Errors:** a `ReadRefused` becomes `ToolError(error.code)`. Any other exception is left to the SDK.
8. **`serve(server: MCPServer) -> None`** calls `server.run("stdio")` and prints nothing.
9. **`docket mcp serve`** is the given command in `cli.py`. It exits 1 with the `ConfigError` or `StoreError` message on stderr, prints nothing on success, and reads no secret.
10. **Progress entry** for `## Phase 6a: MCP read tools (YYYY-MM-DD)` at the end of `docs/progress.md`.

## Given files

Already committed with this spec; never change them.

| File | What it is |
|---|---|
| `pyproject.toml` | Adds `"mcp>=2.3,<2.4"` to `[project] dependencies` |
| `src/docket/cli.py` | Adds the `mcp` sub-app and `mcp serve`, which imports `docket.mcp_server.server` inside the command |
| `tests/product_consolidation_manifest.json` | The byte pins for the two edits above, moved |
| `tests/product_organization_manifest.json` | The same |
| `tests/product_support_manifest.json` | The same |
| `tests/mcp_cases.py` | The in-memory client calls, a counting clock, and a nine-task seed made at 10:00 in New York on 2026-11-20 |
| `tests/integration/test_mcp_server.py` | Names, instructions, log level, descriptions, hints and both schemas as Conductor's check joins their types; the no-tracing guard |
| `tests/integration/test_mcp_reads.py` | Each status, whole results, both daylight-saving days, paging at 50 and 51, every refusal code, an unexpected error, the reminder history, and that nothing is written |
| `tests/e2e/test_cli_mcp.py` | `docket mcp serve` runs on stdio silently, reads no secret, and refuses to start on a missing zone, a bad setting or a newer store |
| `docs/verification/probe-06a.py` | The verifier's probe |

Given test count: **40** (16 functions: `test_mcp_server.py` 5 functions, 5 tests; `test_mcp_reads.py` 8 functions, 30 tests; `test_cli_mcp.py` 3 functions, 5 tests). Two of them pass before you start: `test_no_tracing_backend_is_installed` and `test_mcp_serve_refuses_to_start[bad-setting]`.

## Tests to write

The given tests cover every requirement's main cases. To reach full coverage, add behaviour tests in new `*_more.py` files beside them, never by changing a given test.

- `tests/unit/test_reads.py`, calling `docket.reads` directly on a store under `tmp_path`:
  - `status` of `None` and of `["open"]` raise `invalid_status`.
  - `after` of `1` raises `invalid_cursor`.
  - `task_id` of `None` raises `unknown_task`.
  - `str(ReadRefused("invalid_cursor")) == "invalid_cursor"`.
  - An empty store gives `TaskPage((), None)` for every status.
  - An in-progress task with a deadline later today is `due`.
  - A task with a work time and no deadline is never `due` or `overdue`.
- `tests/integration/test_mcp_server_more.py`, through `tests/mcp_cases.py`:
  - **Deadline in another zone:** home zone `America/New_York`, clock at `2026-11-20T15:00Z`, deadline `2026-11-21T04:30Z` in `Europe/London`. It is listed as `due` (23:30 in New York), with `date` `2026-11-21` and `time` `04:30` (its own zone).
  - A task with a work time and no deadline gives `deadline` null and `work` set.

## Scope

| Path | Change |
|---|---|
| `src/docket/reads.py` | create |
| `src/docket/mcp_server/__init__.py` | create, empty |
| `src/docket/mcp_server/server.py` | create |
| `tests/unit/test_reads.py` | create |
| `tests/integration/test_mcp_server_more.py` | create |
| `docs/progress.md` | append your entry |

The installed packages in `.venv/` change too; `.venv/` is gitignored.

## Out of scope

- Any write tool, `request_key`, or a call into `docket.core`: Phases 6b and 6c.
- `list_proposals`, `list_events`, `check_availability`, `snooze_task`, a calendar event or email links in `get_task`.
- A stdio, SSE or HTTP transport option, a `--port`, resources, prompts, or a second server.
- A `Literal`, enum or length limit in a tool's parameters, a nicer refusal text, or a retry.
- Sorting by deadline, a page size setting, or a total count.
- Any `logging` import or configuration, a log file, or an OpenTelemetry SDK or exporter.
- Adding modules to `scripts/critical_modules.txt` or `tests/tooling_boundary_manifest.json`.
- Any change to a given file, `AGENTS.md` or the design docs.

## Rules that bite

- **Read-only.** Neither tool changes a task, a reminder, an audit row or a key. Nothing in `reads.py` or `mcp_server/` imports `docket.core`, opens a transaction, or reads the Keychain.
- **Constant refusals.** A refusal is the code alone; it never echoes a status, cursor, id, title or exception text.
- **Time.** Dates come from `ZoneInfo(zone)`, never the machine's zone: no `astimezone()` without an argument, no `strftime`. Through the module: `clock.now()`, never `datetime.now()`, and never `from docket.clock import now`.
- **Titles are untrusted** plain text: return them as stored, never as markdown or a link.
- **Synthetic data only** in your tests. Never run `docket mcp serve` against the real data folder, and never connect it to Conductor.
- If you stop before finishing, still write the progress entry with a `Stopped:` first follow-up (`docs/phase-conventions.md`, "When you stop").
- Commands start with `.venv/bin/python`; no bare `python3`, `pytest` or `ruff`.

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest --no-cov -q --ignore=tests/integration/test_mcp_server.py --ignore=tests/integration/test_mcp_reads.py --ignore=tests/e2e/test_cli_mcp.py` (before you start) | `1670 passed` |
| `.venv/bin/python -m pip check` (after the install) | `No broken requirements found.` |
| `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 1710 passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest tests/integration/test_mcp_server.py tests/integration/test_mcp_reads.py tests/e2e/test_cli_mcp.py --no-cov -q` | `40 passed` |
| `.venv/bin/python -m coverage report --include=src/docket/reads.py,src/docket/mcp_server/__init__.py,src/docket/mcp_server/server.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| `.venv/bin/python docs/verification/probe-06a.py` | last line `FAILURES 0` |
| `grep -c "^## Phase 6a: " docs/progress.md` | `1` |
| `.venv/bin/python scripts/check_reports.py --phase 6a` | `Reports OK.` |
| `git diff HEAD --stat -- pyproject.toml src/docket/cli.py tests/product_consolidation_manifest.json tests/product_organization_manifest.json tests/product_support_manifest.json tests/mcp_cases.py tests/integration/test_mcp_server.py tests/integration/test_mcp_reads.py tests/e2e/test_cli_mcp.py docs/verification/probe-06a.py` | no output |
| `git status --short` | only the Scope paths |

### Searches

Each prints nothing.

```zsh
git grep --untracked -n -E 'import (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)|from (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)' -- src
git grep --untracked -n -E 'print\(|logging|logger|warnings\.warn' -- src ':!src/docket/cli.py'
git grep --untracked -n -E 'datetime\.now|datetime\.utcnow|date\.today|time\.time\(|from docket\.(clock|ids) import' -- src ':!src/docket/clock.py'
git grep --untracked -n -E '\.(insert_task|update_task|append_audit|insert_link|insert_request_key)\(' -- src ':!src/docket/core.py' ':!src/docket/store.py'
git grep --untracked -n -E 'os\.environ|getenv\(|strftime\(|import locale' -- src/docket/reads.py src/docket/mcp_server/__init__.py src/docket/mcp_server/server.py
git grep --untracked -n -E 'tzlocal|time\.tzname|localtime\(|astimezone\(\)|environ\[.TZ.\]' -- src
git grep --untracked -n -E 'ollama|anthropic|openai|langchain' -- src
git grep --untracked -n -E 'pragma: no cover|noqa' -- src/docket/reads.py src/docket/mcp_server/__init__.py src/docket/mcp_server/server.py
git grep --untracked -n -E 'docket\.core|import core|\.transaction\(|keychain|keyring|approve' -- src/docket/reads.py src/docket/mcp_server
git grep --untracked -n -E 'opentelemetry|basicConfig|getLogger' -- src
```
