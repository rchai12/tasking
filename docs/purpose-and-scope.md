# Purpose and Scope

## Purpose

The tasks app is the single source of truth for tasks, reminders and calendar sync. It makes sure you hear about every deadline, and that nothing reaches your task list or your calendar without your approval.

It takes tasks from three kinds of source:

- **Already approved:** the email service, after its Discord checkpoints, and Conductor, after you approve the step. These become tasks at once.
- **Proposals:** sources that cannot ask you themselves (cameras, later). These wait for your press on the app's own card.
- **You directly**, from the command line or a Discord command.

## In scope for v1

- Tasks with an optional deadline and an optional planned time to work on them, on one day
- An intake API for already approved tasks (the email service's contract) and follow-up links
- A deterministic reminder engine that posts through the shared Discord service
- One-way writes of approved deadlines to a dedicated Google calendar
- Live reads of every calendar that holds real events: Google, iCloud (through an EventKit helper) and Outlook
- Reconciling the calendar before a reminder is sent
- Read tools and approved write tools for Conductor over MCP
- Proposals with their own approval card, for sources that cannot ask you

## Out of scope for v1

- Email ingestion (the email service)
- The Discord bot itself (the shared Discord service)
- Two-way calendar sync
- Writing undated tasks to calendars
- Automatic time blocks (a dated task gets a due-date event; a work time appears only when you plan one)
- Schedules that repeat every day
- Any model, in the reminder path or anywhere else in the app

See [Roadmap](roadmap.md#deferred-items) for the full list of deferred items.
