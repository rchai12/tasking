# Roadmap

Status (2026-11-14): Stage 1 is built and verified: Phases 0 and 1a to 1g (522 tests). Stage 2 (the intake API) is next to specify.

Build one stage at a time and move on only when its test passes. Stage N is Phase N, split into lettered sub-phases (`1a`, `1b`) when it is too big; numbers are never reused.

**Build order:** 0 → 1 → 2 → 3, then 4 once the shared Discord service exists, then 5 → 11. Stage 2 comes early because it unblocks the email service's Phase 3c; stage 3 needs no Discord, email or calendar, since it sends through a fake.

| # | Stage | Test |
| --- | --- | --- |
| 0 | **Skeleton**: the `docket` package, settings with a private data folder, clock, ids, Keychain reads, `scripts/check.py`, the report checker, test guards (no network, no Keychain, isolated settings) | The given tests pass, critical modules fully covered, `docket version` prints `docket 0.1.0` |
| 1 | **Tasks core and time rules**: the store and migrations, the state rules, deadlines (UTC plus zone, 17:00 default), planned work times, the audit log, `docket tasks list/show/done/cancel/plan`. Split (decided 2026-11-14): **1a** the time rules as pure functions ([phase-01a](phases/phase-01a-time-rules.md)); **1b** the task store: schema, private file, transactions, reads and writes ([phase-01b](phases/phase-01b-task-store.md)); **1c** `docket.core`: the state rules (with reopen), the title rule, one audit row per change ([phase-01c](phases/phase-01c-task-rules.md)); **1d** the `DOCKET_TIME_ZONE` and `DOCKET_WORK_MINUTES` settings and the shared display text ([phase-01d](phases/phase-01d-settings-and-display.md)); **1e** `docket tasks add`, `list` and `show`, with the list line, the detail view and the refusal sentences ([phase-01e](phases/phase-01e-adding-and-listing.md)); **1f** `start`, `done`, `cancel` and `reopen`, plus a given test that `add --due` reads no clock of its own (the gap Phase 1e's review found) ([phase-01f](phases/phase-01f-state-commands.md)); **1g** `edit` (title, `--due`/`--at`, `--no-due`) and `plan` (`plan t3 2026-11-20 14:00 [--minutes N]`, `--clear`) ([phase-01g](phases/phase-01g-edit-and-plan.md)) (split again 2026-11-14) | Every transition in the state table, and only those; a date-only deadline is 17:00 in its zone; a deadline across a daylight-saving change keeps its instant; a work time after the deadline is refused; every change writes one audit row |
| 2 | **Intake API**: `POST /tasks` and `/links` with the email service's contract, client tokens from the Keychain, the host check | A key sent twice makes one task and the same answer; a different body with the same key is refused; a token for one source cannot claim another; the email service's own `tasks_app` tests pass against it unchanged except for the token |
| 3 | **Reminder engine**: planning, the 30-second loop, claims, the late backoff, the work-time `start` reminder, Done voids, a new deadline or work time replans, the downtime summary, the 07:00 digest; sends through a fake notifier | Fake deadlines at 1, 2 and 3 minutes out fire in order; a work time's start reminder fires once; a restart mid-run loses nothing and sends one status message; two loops never send twice; Done voids everything pending; a press twice does nothing extra |
| 4 | **Discord through the shared service**: the service's client, cards, `POST /discord/press`, the owner check, the deadline form, `/tasks` and `/done` | Every button does what the reminder table says; a press from another user is ignored; a press on an old card changes nothing; a failed send is queued and retried |
| 5 | **The service**: `docket run` (API, loop, queues in one process), launchd, alerts, `docket status` | launchd restarts it after it is killed and nothing is lost; each failing part fails alone |
| 6 | **MCP tools for Conductor**: the read tools, the write tools with `request_key`, output schemas and `readOnlyHint` | Conductor's tool check passes against it; the same `request_key` twice changes nothing twice; no tool approves a proposal |
| 7 | **Google Calendar writes**: `docket google-login` (browser consent with PKCE on 127.0.0.1, as in the email service), the Tasks calendar, the write queue | Approving a task creates exactly one deadline event, and planning a work time exactly one timed event; a retry updates them; a new deadline or work time moves them; Done prefixes "Done: " and Cancel deletes; an expired token queues writes and raises one alert |
| 8 | **Calendar reads**: Google first, then the EventKit helper, then Microsoft Graph; `list_events`, `check_availability` | Availability sees an event you add by hand in each backend; a failing backend is named in the answer |
| 9 | **Reconcile before reminding** | Moving or deleting an event on your phone holds the reminder and posts a question instead; your answer is the only thing that changes the task |
| 10 | **Proposals**: `POST /proposals`, the proposal card, the 30-minute follow-up, the digest entry, `docket proposals` | A proposal becomes a task only through your press or command; a double tap does nothing extra; nothing is created on a timeout |
| 11 | **Hardening** | A flood of 200 approved tasks keeps every reminder on time; a title with markdown, mentions or links shows as plain text; every secret is absent from logs and errors |

Stage 10 can move earlier the moment a proposing source (cameras) is close.

## Work in the other projects

These are needed for the whole system; each belongs in that project's own roadmap.

| Project | Work | Needed before |
| --- | --- | --- |
| Shared Discord service (new) | A new project: owns the bot token and Gateway, posts and updates keyed cards for each app, forwards presses (with the presser's user id) to each app on 127.0.0.1, checks the owner id, answers within Discord's 3-second window and supports ephemeral replies (the email service's Show full text) | Tasks stage 4 |
| `emails` | Move the Gateway listener and the senders onto the shared service, keeping its card behaviour and tests | After the shared service exists |
| `emails` | Phase 3c: point `MAILROOM_TASKS_URL` at the tasks app and send its client token | Tasks stage 2 |
| `langgraph` | Phase 12: a tasks domain over `docket mcp serve` (the reads as `read`, the writes as `write`), with code filling `request_key` as `<run id>:<step id>` | Tasks stage 6 |
| `langgraph` | Discord as a third place to approve and answer escalations, through the shared service, recorded in the same store as the terminal and the page | After the shared service exists |

## Deferred items

These are later decisions, not rejections.

- Two-way calendar sync (edits on your phone updating the task)
- Automatic time blocks for dated tasks (a work time exists only when you plan one)
- Work times that repeat every day, or more than one work time per task
- Writing undated tasks to a calendar or a task list
- Outlook or Apple as write targets
- Quiet hours and an urgent flag
- Per-task reminder schedules
- Auto-verifying that work was completed
- Shared or multi-user tasks
