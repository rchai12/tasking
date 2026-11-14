# Tasks, Scheduling and Calendar: Feature Decisions

Nov 9, 2026 · @Richard

## Purpose and scope

The tasks app is the single source of truth for tasks, proposals, reminders and calendar sync. It owns the approval flow, so a task or calendar event exists only after you approve it.

**In scope for v1**

- Tasks with optional deadlines and optional daily schedules
- Proposals from any source (email, the agent, later cameras)
- A deterministic reminder engine that posts to Discord
- One-way calendar writes and live calendar reads
- Read tools and gated write tools for the orchestrator

**Out of scope for v1**

- Email ingestion (separate service)
- Two-way calendar sync
- Tasks with no date written to calendars
- Any LLM in the reminder path

## Decisions at a glance

Tasks, reminders and calendar sync live in one app because they share state, and nothing reaches your calendar without your approval.

| Decision | Choice | Reason | Rejected |
| --- | --- | --- | --- |
| App boundary | One app for tasks, reminders, calendar sync | Shared state; avoids a task done but a reminder still firing | Separate reminder and calendar apps |
| Internal shape | Modular monolith | Easy to split later, hard to merge back | Many small services |
| Proposals | First-class object with a source and evidence | One approval path for email, agent and cameras | Each source creating tasks directly |
| Reminder engine | Deterministic code polling a durable table every 30 to 60 seconds | A missed reminder is the failure to avoid; no model in the path | LLM-driven or in-memory timers |
| Completion | Your button press is the source of truth | The system cannot verify the work itself | Auto-detecting completion |
| Calendar writes | One-way, task app to calendar | Simplest; no conflict rules | Two-way sync |
| Calendar reads | Live read at scheduling time | Agent always sees your current calendar | Cached copy |
| First backend | Google Calendar API | Mature, works headless | EventKit first (later, if iCloud events matter) |
| Moved or deleted events | Reconcile before reminding; ask, never auto-edit | Keeps approval rule intact | Silent two-way updates |
| Time handling | Deadlines stored in UTC with your time zone | Daylight-saving safe | Local time strings |
| Agent access | Typed MCP tools only | No shell, AppleScript runner or screen control | Agent driving the Apple apps directly |

## Data model and task states

Time passing can make a task overdue but never done; only your button press or a cancel ends it.

&#91;embedded content: task states · 6 states\]

The shaded box is the only state that stops reminders, along with cancelled.

**What each record holds**

- **Task:** title, optional deadline (stored in UTC with your time zone), optional daily schedule, state, linked calendar event ID, source proposal, audit trail.
- **Proposal:** source (email, agent, camera), title, optional deadline, evidence quote, confidence, and state (pending, approved, declined).
- **Planned reminder:** task, kind, fire time, and sent time, which stays empty until it is sent.

## Reminder engine

Reminders are plain code that polls a durable table, so a restart or a model outage can never lose one.

| When | Message | Buttons |
| --- | --- | --- |
| 1 hour before the deadline | "Are you working on this?" | Working on it, Done, Snooze, Edit deadline |
| At the deadline, if not done | "This is now due." | Done, Need more time, Cancel |
| After the deadline, repeating | "This is late." | Done, New deadline, Cancel |

**How it runs**

- Each task with a deadline gets planned reminders in a table, each with a fire time, a kind, and a sent time that starts empty.
- A loop every 30 to 60 seconds sends anything due and marks it sent in the same transaction. Nothing lives in memory.
- After downtime, one message states the current status instead of replaying every missed reminder.
- Late reminders back off (30 minutes, then hourly, then every few hours), then the task moves to a daily digest.
- "Working on it" moves the task to in progress. Only Done or Cancel stops the deadline and late reminders.
- Pressing Done voids every pending reminder at once, and the handler is safe to press twice.

**Rules to settle**

- Quiet hours, and whether a task can be marked urgent to break through them.
- A deadline under an hour away skips the 1-hour reminder and sends one "due soon" message.
- Editing a deadline regenerates its reminders and voids the old ones.
- A date with no time gets a default time of day, shown on the proposal.

## Calendar sync

Approved tasks are written one way to a single calendar, while the agent reads your calendars live whenever it proposes a time.

- **Write path:** approving a task or deadline makes the tasks app create or update the calendar event and store the event ID on the task, so retries update instead of duplicating.
- **Read path:** reads cover every calendar that holds real events, so proposals avoid conflicts even when you only write to one.
- **Backends behind one interface:** Google Calendar API first (headless, mature); Microsoft Graph for live.com; Apple EventKit through a small helper on the Mac only if you keep events in iCloud. Yahoo is not a calendar target.
- **What becomes an event:** scheduled items become timed events; deadlines become events with alerts; tasks with no date stay in the tasks app.
- **Reconcile before reminding:** before sending a reminder, fetch the linked event. If it moved or was deleted, hold the reminder and ask on Discord. A 15 to 30 minute check can flag mismatches too. The app never edits tasks from calendar changes on its own.
- **Calendar alerts are a convenience.** The Discord reminders remain the real system, because calendars cannot ask whether you finished.
- **Privacy:** only the approved title and time reach the calendar, never email text.

To verify before building: Google OAuth token lifetime for apps in testing mode, personal-account support when registering the Microsoft app, and whether Apple Reminders can be reached any way other than EventKit.

## Discord interaction

Discord is the only interface, and every approval is a button press handled by the tasks app, not by the agent.

- **One shared Discord layer** sends messages and routes button presses to the right app, so no app grows its own bot code.
- **Approvals live in the app.** The agent can propose; only your button press moves a proposal forward. The agent has no tool that approves.
- **Separate alert path.** Reminders go to a channel or DM that pings you, apart from the chatty agent thread, so they are not buried.
- **Same code path for chat and buttons.** Saying "mark it done" in chat calls the same task API as the Done button, with one audit log.
- **Idempotent buttons.** Double taps and late taps on old messages are safe.
- **Unanswered proposals.** One follow-up after a set time, then a pending-decisions list. Nothing is created on a timeout.
- **Access.** Restricted to your Discord user ID.

## Interfaces

The orchestrator gets typed read tools and a small set of gated write tools, with each approval enforced inside the app.

| Tool | Type | Notes |
| --- | --- | --- |
| list\_tasks(status) | Read | Open, in progress, overdue, done |
| get\_task(id) | Read | Includes reminder history and linked event |
| list\_events(range) | Read | Across every connected calendar |
| check\_availability(range) | Read | Used when proposing times |
| list\_proposals | Read | Pending decisions with their source and evidence |
| propose\_task(...) | Gated write | Creates a proposal only; nothing changes until you approve |
| propose\_change(task, change) | Gated write | Snooze, new deadline or cancel, also needs your approval |

Email, the agent and later cameras all submit proposals through the same API. The agent never receives a shell, an AppleScript runner or screen control, and no tool lets it approve its own proposal.

## Failure handling and edge cases

Each failure has a defined, visible outcome, because a silent failure here means a missed deadline.

- **Discord send fails:** retry with backoff, and raise an alert if retries keep failing.
- **Two loops overlap or a send is retried:** reminders are claimed before sending, so none is posted twice.
- **Calendar API down or token expired:** the task still exists and reminders still fire; the sync is queued and an alert is posted.
- **Event moved or deleted:** hold the reminder and ask on Discord.
- **Machine restarts:** on startup the engine sends anything overdue as one status message.
- **Daylight-saving changes:** offsets are computed in your local time zone from the stored UTC deadline.
- **Travel:** decide whether deadlines are fixed instants or follow your local clock.
- **Duplicate proposals:** a follow-up in an existing thread links to the existing task.
- **Testing:** use fake deadlines at 1, 2 and 3 minutes out, and restart the app halfway through.

## Non-goals and deferred items

These are later decisions, not rejections.

- Two-way calendar sync (edits on your phone updating the task)
- Writing undated tasks to calendars or a task list
- Auto-verifying that work was completed
- Outlook or Apple as write targets, until you find you need them
- Per-task custom reminder schedules
- Shared or multi-user tasks

## Open questions

Seven decisions are still yours to make before building.

- [ ] Quiet hours: when do they start and end, and can a task be flagged urgent to break through?
- [ ] Default time of day for a deadline given as a date only?
- [ ] Do you keep any events in iCloud, or does your iPhone only display Google and Outlook calendars?
- [ ] Which Google account and calendar receives the events?
- [ ] When you travel, do deadlines follow your local clock or stay fixed?
- [ ] Backoff for late reminders: confirm 30 minutes, then hourly, then every few hours, then a daily digest.
- [ ] Does a clearly dated task get a time block as well as a due date?

## Build order and acceptance tests

Build the data model and reminder engine first, since reminders do not depend on email or calendars.

1. **Data model, proposals and the Discord approval buttons.** Test: a proposal moves to a task only through your button press, and a double tap does nothing extra.
2. **Reminder engine.** Test: fake deadlines at 1, 2 and 3 minutes out fire in order, restarting mid-run loses nothing, and Done voids pending reminders.
3. **Google Calendar write, then live reads.** Test: approving a task creates exactly one event; retrying updates it; availability checks see an event you add by hand.
4. **Reconcile before reminding.** Test: moving or deleting an event on your phone holds the reminder and posts a question instead.
5. **MCP tools for the orchestrator.** Test: the agent can list and propose but has no way to approve.
6. **Optional backends** (Microsoft Graph reads, EventKit helper) only if you find you need them.
