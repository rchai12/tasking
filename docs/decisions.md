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
