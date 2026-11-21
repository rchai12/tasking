# Decisions

A task exists only after you approve it, a reminder is never lost, and nothing reaches your calendar except an approved title and time.

Decisions from the original doc are dated Nov 9, 2026; later ones carry their own date. Rows marked *proposed* were chosen while writing these docs and stand until you change them.

| Decision | Choice | Reason | Rejected |
| --- | --- | --- | --- |
| App boundary | One app for tasks, reminders and calendar sync | Shared state; avoids a task done but a reminder still firing | Separate reminder and calendar apps |
| Internal shape | Modular monolith | Easy to split later, hard to merge back | Many small services |
| No model | The app makes no model call at all | Every rule here can be code; a missed reminder is the failure to avoid | A model for parsing or scheduling |
| Approved intake (Nov 14) | Sources that run their own approval (email, Conductor) send tasks that become tasks at once, with no second approval | You never approve the same thing twice; matches the email service's handoff decision | Every source filing a proposal the tasks app asks about again |
| Email contract (Nov 14) | Adopt the email service's stub contract unchanged: `POST /tasks` and `POST /tasks/<id>/links`, keyed by `Idempotency-Key` | The email service is built and tested against it | A new contract |
| Agent approval (Nov 14) | Approving a Conductor step is enough. Agent tools that change tasks are Conductor `write` actions | One approval, in the place you already approve the plan | `propose_task` filing a proposal that the tasks app asks about again |
| Proposals | First-class object with a source and evidence, for sources that cannot ask you (cameras, later) | One approval path for every such source | Each source creating tasks directly |
| Discord (Nov 14) | A separate shared Discord service owns the bot token and Gateway, posts cards for every app and forwards presses to each app on 127.0.0.1 | One bot connection, no bot code in each app; the email service moves onto it | Each app running its own bot; a shared library with one Gateway per app |
| Approval places (Nov 14) | Conductor approvals in the terminal, on its 127.0.0.1 page, and on Discord, all recorded in one store | Discord matters when you are away from the Mac; this may change with private routing to the Mac | Discord only; the Mac only |
| Reminder engine | Deterministic code polling a durable table every 30 seconds | A missed reminder is the failure to avoid; nothing lives in memory | Model-driven or in-memory timers |
| Completion | Your press (or your approved command) is the source of truth | The system cannot verify the work itself | Auto-detecting completion |
| Stored states (*proposed*, Nov 14) | Stored: open, in progress, done, cancelled. Due and overdue are worked out from the deadline when read | Time passing can never change a stored row, so a restart cannot skip a transition | Storing overdue, written by a timer |
| Quiet hours (Nov 14) | None; reminders fire when they come due | Your choice | 22:00 to 08:00 with an urgent flag |
| Date-only deadline (Nov 14) | 17:00 in your time zone, shown on the card | End of the working day; the 1-hour reminder lands at 16:00 | 23:59; 09:00 |
| Time handling | Deadlines stored as a UTC instant plus the IANA time zone they were given in | Daylight-saving safe | Local time strings |
| Missing and repeated times (Nov 14) | A wall time that doesn't exist (02:30 on the spring-forward day) moves forward to 03:30; one that happens twice (01:30 on the fall-back day) is the first, so a deadline errs early. Both are Python's `fold=0` | Clear rules with no question asked for an hour a year | Refusing a missing time; the second of a repeated one |
| Zone names (Nov 14) | Only exact names from `zoneinfo.available_timezones()` | macOS loads `america/new_york` too, so one zone could be stored under two spellings | Whatever `ZoneInfo` loads |
| Travel (Nov 14) | A deadline is a fixed instant; travelling does not move it | Simplest; matches how calendars store events | Following the local clock; per-task choice |
| Late backoff (Nov 14) | Late reminders at 30 minutes and 1 hour after the deadline, then hourly 3 times, then every 4 hours twice, then the daily digest | About half a day of pings, then one line a day | Gentler; every 30 minutes forever |
| Calendar writes | One-way, tasks app to calendar | Simplest; no conflict rules | Two-way sync |
| Write target (Nov 14) | A dedicated Tasks calendar under one Google account, named in settings | Easy to hide or recolor on your phone; the app never touches your own events | Your primary calendar |
| What becomes an event (Nov 14) | A dated task becomes one due-date event with an alert; the app never adds a time block on its own | Narrow v1 | A time block made automatically for every dated task |
| Planned work time (Nov 14) | A task may have one planned time to work on it, on one day (start and length: 5 to 720 real minutes, ending by the task's deadline and by midnight in its zone), set by you or an approved Conductor step. It becomes a timed event on the Tasks calendar and gets a "Time to start" reminder | What "daily schedules" meant in the original doc | A schedule that repeats every day |
| Done on the calendar (Nov 14) | A done task's events stay, with "Done: " in front of the title; a cancelled task's events are deleted | The calendar keeps a record of what was finished | Deleting the event on Done |
| Daily digest (Nov 14) | 07:00 in your time zone | Your choice | 09:00 |
| Calendar reads | Live read at proposal and scheduling time, across every calendar that holds real events | The agent always sees your current calendar | Cached copy |
| Read backends (Nov 14) | Google first, then Apple EventKit through a small read-only helper on the Mac (you keep some events in iCloud), then Microsoft Graph | iCloud events must count when checking availability | EventKit deferred |
| Calendar scopes (Nov 14, to confirm in a spike) | Google: `calendar.app.created` (make the Tasks calendar and manage only its events), `calendar.calendarlist.readonly` and `calendar.events.readonly` (reads). Microsoft: `Calendars.ReadBasic` | The narrowest scopes Google and Microsoft document; ReadBasic leaves out event bodies | `calendar` or `calendar.events` (write to every calendar); `Calendars.Read` |
| Google sign-in lifetime (Nov 14) | Set the Google project's consent screen to In production before the real sign-in | Google documents that External apps in Testing get refresh tokens that expire in 7 days | A weekly sign-in |
| Moved or deleted events | Reconcile before reminding; ask, never auto-edit | Keeps the approval rule intact | Silent two-way updates |
| Agent access | Typed MCP tools over stdio only | No shell, AppleScript runner or screen control | The agent driving the Apple apps directly |
| Intake sign-in (*proposed*, Nov 14) | Each client has its own token in the Keychain, sent as a bearer token; the token fixes the source it may claim | Any local process can reach 127.0.0.1; a token stops one posing as another | No sign-in on loopback |
| Explicit intake identity (Nov 17, Phase 2f) | Require a keyword-only `client` with no default in both Python intake functions; migrate existing tests and the earlier probe to pass `client="email"` | Owner chose explicit identity so a caller cannot silently assume email; HTTP forwards the matched token identity | An email default for compatibility with existing Python callers |
| Retry safety (*proposed*, Nov 14) | Every create is keyed; the same key with the same body returns the first answer, with a different body it is refused | Retries never duplicate, and a key reused by mistake is visible | Matching on title and date |
| Task ids (Nov 14) | `t1`, `t2`, ...: the row's number, never reused | Easy to type in `/done t12` and read on a phone | 32-character hex; short random letters |
| Reopen (Nov 14) | A done or cancelled task can be reopened any time, with its own audit row | A mistaken tap can be undone | Final states; reopening within 24 hours only |
| Titles (Nov 14) | Refused, never rewritten: 1 to 100 characters, no leading or trailing whitespace, no Cc, Cf, Zl or Zp characters | The app never changes what a source sent; matches the email service's own title check | Trimming and cleaning up |
| Ended tasks (Nov 14) | Only Reopen works on a done or cancelled task; an edit is refused (`task_ended`) | Done keeps meaning done | Title-only edits; any edit |
| Deadline vs work time (Nov 14) | A change that leaves a work time ending after the deadline is refused (`work_after_deadline`) | Nothing changes behind your back | Clearing the work time |
| Past dates (Nov 14) | Allowed at creation and in edits; the task is overdue at once | The approval already happened, for example an email approved late | Refusing past deadlines; future-only work times |
| Repeats (Nov 14) | A change to the state or values a task already has reports no change and writes nothing | Double taps and retried calls are harmless | Writing an audit row for every press |
| Core errors (Nov 14) | One constant code per refusal (`unknown_task`, `invalid_title`, `task_ended`, ...), also the error's text | An MCP tool or API route passes it on unchanged; no input is echoed | Messages with values |
| Display zone (Nov 14) | Your zone, plus the zone a deadline or work time was set in when it differs (`... where set`) | You always see your own clock, and nothing set while travelling is ambiguous | Always your zone; always the task's own |
| Typed input (Nov 14) | ISO dates and times (`2026-11-20`, `17:00`) in your zone for the commands; words like "Friday" later, with the Discord deadline form | Exact, nothing guessed | Weekdays and today/tomorrow now |
| No zone set (Nov 14) | `DOCKET_TIME_ZONE` has no default; a command that needs it refuses; an empty value counts as unset | The app never reads the machine's zone, and a wrong default would be silent | New York or UTC by default |
| Time text (Nov 14) | `Fri Nov 20 17:00 EST`: English names, no leading zero on the day, 24-hour clock, the year only when it isn't this year in that zone | Same text on the command line and on Discord; no locale surprises | `strftime` with the locale |
| Task list (Nov 14) | Open and in-progress tasks by default, soonest deadline first (overdue on top), then undated by id; `--all` adds the rest in the same order | What needs doing next comes first | By id; everything by default |
| Command refusals (Nov 14) | A plain sentence on stderr and exit code 1; usage mistakes exit 2 | Readable at the terminal; the codes stay for the MCP tools | The code; both |
| Adding a deadline (Nov 14) | `--due YYYY-MM-DD [--at HH:MM]`, checked against the exact shape before parsing; `--at` alone is refused | Python's ISO parser also takes `20261120` and `1700` | One combined `--due` option |
| Command repeats (Nov 14) | `t3 is already done.` with exit code 0; nothing written | A repeat is harmless, so a script or a double press sees no error | The change sentence again; exit 1 |
| Plan and edit forms (Nov 14) | `plan t3 2026-11-20 14:00 [--minutes N]` with `--clear`; in `edit`, `--at` needs `--due` as in `add`, and `--no-due` clears | Positional date and time read naturally; one deadline rule everywhere | Options only; `--at` alone keeping the date |
| Edit output (Nov 14) | The task after the change (`Updated t3: Pay rent, due Sat Nov 21 09:00 EST`, or `..., no deadline`); `plan` prints the span or `Cleared the work time of t3.`; a repeat `Nothing changed for t3.` | One line you can read at a glance, like `add` | A before-and-after line per field |
| Empty edit (Nov 14) | Refused: `Give --title, --due or --no-due.`, exit 1 | An edit naming nothing is a mistake, not a repeat | `Nothing changed`, exit 0 |
| Retry key scope (Nov 14) | Per client: the same key from the email service and from Conductor are two requests | Each client makes its own keys (`<provider>:<message id>`, `<run id>:<step id>`) | One global key space |
| Links and keys kept (Nov 14) | Pruned a year after their task ended, by the service's daily job; tasks and the audit log stay forever | Small tables stay bounded; a retry a year late is not a risk worth keeping rows for | Keeping everything; links as audit rows |
| Keyed intake (Nov 14) | The key check, the write and recording the key in one transaction in `docket.core`; the same key and request answer with what they made, another request is `key_reused`; the source is the client; links only from the email client, ended tasks included, with no audit row | Retries can never duplicate, and the same path serves the API and the MCP tools | Matching on title and date; checking keys in the HTTP layer |
| Intake zone names (Nov 14) | A deadline's `time_zone` must be an exact name; a wrong-case one is 422 `invalid_deadline`, never rewritten | Same rule everywhere in the app; the email service checks its own setting instead | Mapping case-only differences to the exact name |
| Intake answers (Nov 14) | `{"id": ...}` or `{"error": <code>}` only; shape (and JSON types) before the deadline before the core's checks; a link's task before its body, as the email service's fake does | The email service reads only status and id; nothing from the request is echoed | Error text with values |
| HTTP library (Nov 14) | FastAPI 0.162, as Conductor; `httpx2` for its test client | One stack across the projects; Starlette's test client warns with plain `httpx` | Starlette alone; `http.server` |
| FastAPI telemetry (Nov 14) | Switched off in code (`telemetry={...: False}`); no OpenTelemetry SDK or exporter ever installed | FastAPI 0.162 records telemetry by default and can add exporters from the environment; the project sends nothing | Relying on no SDK being present |
| Client tokens (Nov 14) | `docket clients add email` prints a 32-byte URL-safe token once, kept in the Keychain item `client.email`; a second one needs `--replace` | A slip can't cut the email service off; each app keeps its own Keychain item | Always replacing; a shared item |
| Serving (Nov 14) | `docket serve` runs uvicorn 0.54 on 127.0.0.1 at `DOCKET_WEB_PORT` (1024 to 65535, default 8767) with warnings only, no access log, no server header and no forwarded headers; it refuses to start when no client has a token | Same server as the siblings; nothing per request in a log; a forgotten token shows at start, not as 401s | A start that answers 401 to everything; uvicorn's defaults |
| Intake cross-check (Nov 14) | The email service's requests are checked against the real app by a manual run the owner does once (the roadmap's "Manual checks") | Tests never reach the email service; its token is its own Phase 3c | A test importing the email service |
| Phase tooling (Nov 14) | The coder and verifier work through the `phase-coder` and `phase-verifier` skills; Phase 2e adds `check.py --quiet`, an acceptance digest, a spot-check runner and a progress appender | Their notes (`docs/coder-token-use.md`, `docs/verification-process.md`) found most tokens went on repeated reading and full logs; judging spot checks stays with the verifier | Long pasted prompts; scripting the verdict |
| Request size (Nov 14) | A body over 64 KiB is refused (413) before parsing | An approved task is under 1 KiB | The server's defaults |
| Concurrent access (Nov 14) | WAL mode, a 5-second busy timeout, every write in `BEGIN IMMEDIATE` | The service, the CLI and the MCP server each open the file | One process owning the file |
| Storage (*proposed*, Nov 14) | One SQLite file, standard library `sqlite3`, plain SQL, numbered migrations | Same as the email service; every query visible | SQLAlchemy and Alembic |
| HTTP (*proposed*, Nov 14) | FastAPI on 127.0.0.1 for the API; httpx for outgoing calls | Same as Conductor's page and the email service's client | The standard library server |
| Package (*proposed*, Nov 14) | `docket`, command `docket`, settings prefixed `DOCKET_`, port 8767 | Short and unused here; `finances` has 8765 and Conductor 8766 | |

## Reference safety decisions (Nov 17, Phase 2g)

- **Owner: caps.** Message IDs have at most 512 Unicode code points and links at most 2,048, both nonempty. Larger limits of 1,024/8,192 were not chosen. The existing 200-character retry-key rule remains separate.
- **Owner: upgrades.** Invalid existing references stop the upgrade without changing data; report only task/link ID and field. Grandfathering with escaped display was not chosen. A repair is separate and requires explicit authorization.
- **Architect: character policy.** Reject Cc, Cf, Zl and Zp in both fields, using the same category rule as titles. Preserve valid spaces and text; no trimming, normalization or URL-scheme validation.
- **Architect: storage.** Apply the given append-only rebuild with a preflight inside the write transaction. Disable foreign keys only around migration 3, check them before commit and restore enforcement on every exit; preserve IDs, retry JSON, audit history and sequences.

## HTTP execution decisions (architect, Nov 17, Phase 2h)

No new owner choice changes the wire contract. Keep the existing 64 KiB actual-body limit and refusal order. Read incrementally and check the incoming total before accumulating a chunk; never use Content-Length as the size decision. Decode only after the bounded body is complete, so UTF-8 may span chunks.

Await one synchronous operation in the installed framework's worker pool for the whole store context and intake call. Open, use and close the connection on that same worker; preserve SQLite's thread check and five-second busy timeout. Do not add an executor, queue, request timeout, retry policy, dependency or error mapping.

## Store startup and read decisions (Nov 17, Phase 2i)

- **Owner: startup coordination.** Use a private startup lock file with a standard-library exclusive file lock; wait until initialization finishes. Keep the existing SQLite five-second busy timeout. The SQLite-only bounded-retry alternative was not chosen.
- **Architect: gate artifact.** Derive `<database filename>.startup.lock` beside the database, empty and mode 0600. Acquire before SQLite opens and release after initialization/cleanup. Keep its inode across opens; no PID, age check, stale-file deletion or new setting. Gate acquisition OSError becomes `store startup unavailable` with no library-error chain.
- **Architect: migrations.** Recheck schema versions under immediate write transactions, keeping each migration atomic and foreign-key relaxation scoped to migration 3. Close every failed constructor's created connection once; preserve other original initialization failures.
- **Architect: corrupt task times.** Refuse non-UTC/unparseable task instants and invalid zones with `invalid stored task time: <task id>`, no chained library text, no automatic repair and no partial list. Extend the private CLI context guard so these errors use its existing plain refusal style. No new owner time policy is introduced.

## Creation and serialization decisions (architect, Nov 17, Phase 2j)

No new owner choice changes product behaviour. Both public create functions call one private insertion/create-audit helper; public callers retain validation, clock reads, their transaction and request-key handling. The helper receives the timestamp and validated values and returns the task.

`docket.serialization.canonical_json(value: dict[str, object]) -> str` is the single writer for audit snapshots, request-key bodies and retry comparisons. Core and store call it through the module. Preserve sorted keys, unescaped Unicode, compact separators and every other existing standard-library default, including numeric and failure behaviour. No stricter JSON policy or historic-row rewrite is introduced. Add the shared writer to the 100% critical coverage gate because retry safety depends on it.

## Domain and parsing decisions (architect, Nov 17, Phase 2k)

No new owner policy choice. Put current domain collections and repeated limits in `docket.domain` as immutable tuples, read-only mappings and a forbidden-category frozenset. Keep reference caps in `docket.references` and re-export the existing deadline work-limit names. Keep email-only token issuance and intake separate from the core's email/agent client set. SQL remains an unchanged deliberate copy, checked against the shared values.

`docket.parsing` supplies strict ASCII date/time readers and a typed ParseError with fixed text `invalid date or time`. CLI/intake call through that module and retain their optional-value handling, refusal order and existing public messages. Settings and deadlines use the same cached exact `domain.zone_names()` set; there is no normalization or time-policy change.

Explicit settings error priority remains data_dir, time_zone, work_minutes, web_port, independent of error-list order. A recognized field wins over unknown fields; when none is recognized, including root/empty errors, use the new constant `Invalid docket settings.` without a library-error chain. This prevents future validation errors from being mislabeled as web-port failures without adding a setting.

## Store table boundary decisions (architect, Nov 17, Phase 2l)

Split the planned store refactor into two implementation phases to keep each within the phase budget. Phase 2l extracts ordinary audit/link/request-key SQL; Phase 2m extracts ordinary task SQL. Only unshipped later rows are shifted; the roadmap records the new order. No owner product choice is required.

The private SQL modules receive the existing SQLite connection and bound values and return SQLite data for Store to convert. Store keeps the public records/sentinel/errors, validation, ID checks, canonical JSON and time policy, one transaction owner, task SQL until 2m, startup and migrations. Migration reference preflight remains with startup. Helpers do not import product modules, open/close connections, own transactions or change SQLite settings. No generic repository or shared records module is introduced.

## Task table boundary decisions (architect, Nov 17, Phase 2m)

No new owner choice. Complete the existing split with `_store_tasks`, moving ordinary task SQL, its column list and SQL assembly while retaining public records, guards, encoded-value selection, sentinel semantics and safe task-time conversion in Store. Store supplies an update map of fixed internal column names; the private helper constructs the SQL and binds all values. External keys/fragments are never used as identifiers. Ordinary task reads/existence/readback use the same connection; migration/preflight task reads stay local to startup. Existing 2l modules, schema and public APIs remain unchanged.

## Repository tooling decisions (architect, Nov 17, Phase 2n)

Use a root docket_tools package outside src, keeping src-only package discovery unchanged. Move the three utilities byte-identically and update explicit consumers/bootstrap; no shims, installation, dependency, parser rewrite or test consolidation. A manifest preserves utility bytes and earlier consumer ASTs. Historical fixture strings naming old modules remain data.

Preserve the product critical list except for removing the three moved utilities, and give those utilities a separate immutable repository-relative coverage list. Full pytest measures docket and docket_tools; critical coverage and tooling coverage independently require all listed lines/branches, refusing absent measurements. Keep the overall 90% floor and existing command behavior. Wheel build tools are absent, so packaging evidence is the unchanged discovery configuration plus an isolated src-copy CLI smoke test with external access blocked.

## Shared product test support decisions (architect, Nov 18, Phase 2o)

Separate helper reuse from file consolidation to preserve historical selectors and existing manifests. Phase 2o shares explicit local path/store fixtures and a strict refusal helper across eight product-test modules, retaining their 304 node IDs and test bodies. Product and tooling consolidation follow separately as 2p/2q; unshipped type checking shifts to 2r. No owner product choice or dependency is introduced.

Shared fixtures use default function scope, no explicit pytest decorator name or global plugin, allowing the existing seeded module to import store as base_store and keep its exact seed adapter. One context owns/cleans the empty temporary Store. The shared refusal helper follows the original strict core helper: require CoreError, equal code and string, fail on no error and propagate other exception types. The existing support runner/functions, product/tooling source, global guards and coverage configuration remain unchanged.

## Phase 2o fixture correction (architect, Nov 18)

The original store(path) design collided with the existing plain/keyed/link path parameters. The coder followed the spec and correctly stopped; preserve those case parameters, test bodies and IDs. Store instead depends on builtin tmp_path and opens its fixed temporary filename directly. Use an explicit __all__ = ["base_store"] in the seeded consumer instead of a no-op decorator to preserve the imported fixture alias for Ruff. The given normalizer permits only that exact export declaration; seed/test bodies and the manifest remain pinned. Corrected givens/probe execute the real reference cases, not collection alone.

## Cleanup sequencing (2026-11-18)

The owner approved stopping further subdivision of audit test cleanup and preventing it from postponing the reminder engine. Complete independent verification of already implemented Phase 2q, then plan Stage 3 after settling its persistent-ID contract. Phase 2r tooling test organization is deferred maintenance, not a reminder prerequisite. Phase 2s type checking remains separate and requires the owner’s checker/dependency decision. No further prerequisite phases for file organization without explicit owner agreement. Existing phase IDs and historical evidence remain unchanged.

## Reminder IDs and planning (2026-11-18)

Owner chose SQLite IDs for internal rows and generated IDs for outbound retry keys. Preserve existing task/link IDs; durable reminder IDs use r1, r2, onward from never-reused SQLite numbers. Generate each outbound retry key once through docket.ids.new_id(), persist it, and reuse it for every attempt/restart. The alternative of generated IDs for both reminder rows and retry keys was not chosen. AGENTS.md and architecture.md are reconciled with this policy; no database change or ID allocation occurs in Phase 3a.

Architect scope: Stage 3 starts with the pure reminder plan, with exact UTC offset, boundary, state, work-start and tie-order contracts. Include past due/late/start instants as evidence for later catch-up coalescing; do not send them individually or repeatedly replan during polling. The finite late schedule ends at 12 elapsed hours; digest remains a later Stage 3 responsibility. Datetime overflow is explicit, never silently clipped. Durable core integration must handle it before committing changes. This phase adds no delivery, service connection or dependency.

## Durable reminder upgrade (2026-11-18, Phase 3b)

Owner chose backfill of existing open/in_progress tasks from their stored last-approved snapshots and updated_at. Preserve past slots for later catch-up coalescing and send no notifications during upgrade. The alternative of planning only on future task changes was not chosen. No real database is inspected by an agent.

Architect: append migration 4 and backfill in its existing startup transaction before committing version 4. Use startup-local active-task SQL, existing task conversion and a shared private reminder writer; no normal task-helper lookup, new connection, clock or generated ID. An invalid or unrepresentable active plan refuses the whole upgrade with safe identifier-only text, leaving the database at version 3. No repair or omission.

Architect: preserve immutable reminder history; void only pending rows, retain sent rows and earlier void timestamps, and replace only actually changed deadline/work groups. Creation, end, reopen, edits and keyed retry bookkeeping remain atomic with task/audit state. No-op, title, start and follow-up links do not replan. New overflow code invalid_reminder_plan maps to fixed CLI text and intake 422. The shared domain owns reminder-kind membership. Sending/claims/keys remain later work.

Earlier phase-wide byte freezes are migrated only where this feature requires edits: preserve old core/store nodes except the four named mutable bodies, retaining their signatures and existing import atoms. All other byte pins, case maps, seeds and historical contracts remain exact. This is a feature-local guard migration, not a new cleanup phase or permission to regenerate snapshots from the coder's result.

## Reminder sending (2026-11-18, Phase 3c)

Owner chose: two or more due reminders for a task in one pass go out as one status message, all marked sent, while a single due reminder goes out normally however late (not a lateness threshold, not newest-only). The status text is "Missed while docket was offline: N reminders." then the newest reminder's normal line (not the current phase, not a bare prefix). Only reminders that came due after they were planned (fire_at after planned_at) count as missed, so a task created or reopened after its deadline gets one normal line (not counting all, not a separate line). A send the notifier refuses is retried every pass with the same key (not a backoff).

Architect: migration 5 adds `posts` and `post_reminders` rather than a column on `reminders`, so a coalesced message is one outbound row with one persisted key, each reminder belongs to at most one post, and the Phase 3b columns stay as pinned. The claim is one UPDATE in a BEGIN IMMEDIATE transaction; a crashed claim is retried with the same key after 5 minutes, and a post whose reminders were all voided is never sent. The engine passes `Notice(key, task_id, title, text)` to a given `Notifier` protocol; Stage 4 implements it. Notice texts live in `reminders.py` because `views.py` is byte-frozen; Stage 4's cards render them. No loop runner, command, alert or digest in this phase.

## Daily digest (2026-11-18, Phase 3d)

Owner chose: a morning with nothing overdue sends nothing and stores nothing (not an "all clear" message). A missed 07:00 goes out on the first pass later that same home day; after days away only the current day's digest is sent (not a catch-up per missed day, not skipped until tomorrow). The heading is "Still open past their deadlines: N tasks.", one line per task with its title and "Was due" time. A refused or crashed digest is retried with the same key and leaves out tasks that ended or stopped being overdue since it was queued (not resent as first queued).

Architect: migration 6 adds `digests` (one per home day, unique key) and `digest_tasks`; contents are immutable and rows never removed, as for posts. A task is in the digest when it is open or in progress and its deadline plus the last late offset (720 minutes) is at or before the slot. The engine takes the zone and time as arguments rather than reading settings, so Stage 5 wires `DOCKET_TIME_ZONE` and `DOCKET_DIGEST_TIME`. The digest goes through `Notifier.send_digest` with the same once-per-key contract as `send`. Proposals are added in Stage 10.

## Reminder loop (2026-11-18, Phase 3e)

Owner chose: an unexpected error in a pass, such as a bug or a database locked by another writer, never stops the loop; it waits 30 seconds and tries again, and Stage 5 turns repeated failures into an alert (not ending the loop for launchd to restart, not ending it after 10 failures in a row). The reminder half and the digest half of a pass fail alone (not ending the pass at the first failure).

Architect: `run_pass` catches `Exception` once per half and records only the half's name, never the exception's text; `BaseException` passes through. `run_loop` pauses only on the caller's `Stop.wait(30)`, which a `threading.Event` satisfies, so Stage 5 stops it on shutdown without a sleep. The pause follows each pass. The loop reads no settings and starts nothing; Stage 5 wires it into `docket run`.

## MCP tools (2026-11-18, Stage 6)

Owner chose: Stage 6 before Stage 4, because the shared Discord service does not exist yet. The SDK pin is `mcp>=2.3,<2.4` in the project's dependencies. `list_proposals`, `list_events`, `check_availability` and `snooze_task` are left out until the stages that build proposals, calendar reads and the Snooze button (not stubbed now, not built early). `due` means open or in progress with a deadline later today in `DOCKET_TIME_ZONE` that has not passed, and `overdue` means its deadline has passed (not the 30-minute due window of `deadlines.status`). `get_task` lists sent and pending reminders with kind, fire time and sent time, and leaves voided ones out (not every row, not pending only).

Architect: Stage 6 splits into 6a (the SDK, `docket mcp serve`, `list_tasks`, `get_task`), 6b (`create_task`, `complete_task`, `cancel_task` with `request_key`) and 6c (`change_deadline`, `plan_work_time`). Results are typed pydantic models; parameters are plain strings checked in `docket.reads` with constant codes `invalid_status`, `invalid_cursor` and `unknown_task`. A wrong JSON type is answered by the SDK's validation message to the caller only, a known limit. Paging is 50 a page in id order with an `after` cursor. Each call opens its own store (the SDK runs plain tools on worker threads). The server logs at CRITICAL so nothing reaches stderr. `cli.py` imports the server inside `mcp serve`, so other commands never load the SDK. Each deadline carries `at` plus `date`, `time` and `time_zone` in its own zone, the shape Conductor's write actions send. Email links and the calendar event stay out of `get_task` for now. The OpenTelemetry API that `mcp` uses (already installed through `fastapi`) stays a no-op: no SDK or exporter may be installed. The MCP modules join `scripts/critical_modules.txt` with the write tools in 6b.

## Nov 21 audit (2026-11-21)

Owner chose: retire the freezes and prepare 6b's inputs first (Phase 6b freezes, 6c core input checks), then the MCP write tools as 6d and 6e, then the store and loop work as 5a to 5d before `docket run` (not all remediation first, not Stage 6 first). Replace the freeze manifests with one manifest pinning `docs/reviews/`; verifiers judge given files with `git diff` against the phase's base commit (not every pin retired, not kept). Split `Store` by aggregate behind thin delegating methods (not helpers only). Defer the lockfile and decide its tool with the 2s type-checker dependency (not a hashed requirements file now, not uv now).

Architect: Phase 6a's strict `xfail` markers on committed given tests are the standard, which settles finding 2 without phase branches. The MCP modules join `scripts/critical_modules.txt` with the write tools in 6d (was 6b). Probes stay frozen given files, excluded from ruff. `docs/architecture.md` is rewritten as the present design (Nov 21): no phase changelog, planned parts marked by stage, reasons left to this file.

## Phase 6b review pins (2026-11-21)

Owner chose: the architect pins each passed phase's review in `tests/review_pins.json` in the next spec's commit, with `.claude/skills/phase-architect/pin_review.py` (not the verifier pinning its own review, not a test that fails while a review is unpinned).

Architect: the `docket_tools` byte pins and the tooling tests' AST pins retire with the product pins; the tooling-boundary behaviour stays tested. The fake coverage in `tests/tooling_boundary_cases.py` reads the two gate lists, so a new critical module needs no test edit. The kept shared-support tests stay in their files until 2r.

## Phase 6c core input checks (2026-11-21)

Owner chose: `create_task`, `create_task_once` and `edit_task` all refuse a deadline or work time that is not a `Deadline`, `WorkTime` or `None` (not `edit_task` only); two codes, `invalid_deadline` and `invalid_work` (not one shared code); `refusal_text` stays a strict lookup guarded by a test that walks every code `core` defines (no generic fallback sentence).

Architect: the deadline is checked before the work time, after each function's existing checks and before the clock read; `UNCHANGED` passed to a create function is a wrong value; signatures do not change; the five new sentences never echo the value.

## Phase 6d MCP write tools (2026-11-21)

Owner chose: `complete_task` and `cancel_task` keep their `request_key` in `request_keys`, as `create_task` does, so a retried step after the owner reopens a task changes nothing (not a stateless check); completing a done task or cancelling a cancelled one answers the task with `changed` false and keeps the key, not a refusal, which drops the `already_done` code from Conductor's handoff (work in Conductor's project); every write answers the task in `get_task`'s fields plus `changed` (not an id alone).

Architect: the deadline argument is null or exactly `{date, time, time_zone}` and is parsed first; the kept request names the tool, so a key moved to another tool is `key_reused`; the key is looked up before the task, and a refused change keeps no key; a non-string id is `unknown_task`; all three write tools are idempotent, not read-only, not destructive, closed-world; `reads.py`, `writes.py` and `mcp_server/server.py` become critical modules.
