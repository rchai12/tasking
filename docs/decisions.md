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
| Travel (Nov 14) | A deadline is a fixed instant; travelling does not move it | Simplest; matches how calendars store events | Following the local clock; per-task choice |
| Late backoff (Nov 14) | Late reminders at 30 minutes and 1 hour after the deadline, then hourly 3 times, then every 4 hours twice, then the daily digest | About half a day of pings, then one line a day | Gentler; every 30 minutes forever |
| Calendar writes | One-way, tasks app to calendar | Simplest; no conflict rules | Two-way sync |
| Write target (Nov 14) | A dedicated Tasks calendar under one Google account, named in settings | Easy to hide or recolor on your phone; the app never touches your own events | Your primary calendar |
| What becomes an event (Nov 14) | A dated task becomes one due-date event with an alert; the app never adds a time block on its own | Narrow v1 | A time block made automatically for every dated task |
| Planned work time (Nov 14) | A task may have one planned time to work on it, on one day (start and length), set by you or an approved Conductor step. It becomes a timed event on the Tasks calendar and gets a "Time to start" reminder | What "daily schedules" meant in the original doc | A schedule that repeats every day |
| Done on the calendar (Nov 14) | A done task's events stay, with "Done: " in front of the title; a cancelled task's events are deleted | The calendar keeps a record of what was finished | Deleting the event on Done |
| Daily digest (Nov 14) | 07:00 in your time zone | Your choice | 09:00 |
| Calendar reads | Live read at proposal and scheduling time, across every calendar that holds real events | The agent always sees your current calendar | Cached copy |
| Read backends (Nov 14) | Google first, then Apple EventKit through a small read-only helper on the Mac (you keep some events in iCloud), then Microsoft Graph | iCloud events must count when checking availability | EventKit deferred |
| Calendar scopes (Nov 14, to confirm in a spike) | Google: `calendar.app.created` (make the Tasks calendar and manage only its events), `calendar.calendarlist.readonly` and `calendar.events.readonly` (reads). Microsoft: `Calendars.ReadBasic` | The narrowest scopes Google and Microsoft document; ReadBasic leaves out event bodies | `calendar` or `calendar.events` (write to every calendar); `Calendars.Read` |
| Google sign-in lifetime (Nov 14) | Set the Google project's consent screen to In production before the real sign-in | Google documents that External apps in Testing get refresh tokens that expire in 7 days | A weekly sign-in |
| Moved or deleted events | Reconcile before reminding; ask, never auto-edit | Keeps the approval rule intact | Silent two-way updates |
| Agent access | Typed MCP tools over stdio only | No shell, AppleScript runner or screen control | The agent driving the Apple apps directly |
| Intake sign-in (*proposed*, Nov 14) | Each client has its own token in the Keychain, sent as a bearer token; the token fixes the source it may claim | Any local process can reach 127.0.0.1; a token stops one posing as another | No sign-in on loopback |
| Retry safety (*proposed*, Nov 14) | Every create is keyed; the same key with the same body returns the first answer, with a different body it is refused | Retries never duplicate, and a key reused by mistake is visible | Matching on title and date |
| Storage (*proposed*, Nov 14) | One SQLite file, standard library `sqlite3`, plain SQL, numbered migrations | Same as the email service; every query visible | SQLAlchemy and Alembic |
| HTTP (*proposed*, Nov 14) | FastAPI on 127.0.0.1 for the API; httpx for outgoing calls | Same as Conductor's page and the email service's client | The standard library server |
| Package (*proposed*, Nov 14) | `docket`, command `docket`, settings prefixed `DOCKET_`, port 8767 | Short and unused here; `finances` has 8765 and Conductor 8766 | |
