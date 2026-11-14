# Open Questions

- [ ] **Package name.** `docket` is assumed; easy to change before Phase 0.

## Checked (Nov 14, 2026), still to confirm in a spike before each phase

- **Google sign-in lifetime.** Google's OAuth documentation says an External app in Testing gets refresh tokens that expire in 7 days. Setting the consent screen to In production avoids that; sign in again after the switch, since a token issued in Testing keeps its limit. A refresh token also stops working after six months unused, and each Google account keeps at most 100 per OAuth client (the oldest is dropped without warning). Still to confirm: what an unverified personal app in production shows at consent with calendar scopes. The email service has the same question for Gmail.
- **Google scopes.** Google's Calendar documentation lists `calendar.app.created` (create secondary calendars and manage events on calendars the app created), which fits the Tasks calendar exactly. Reads use `calendar.events.readonly`. Listing your calendars may also need `calendar.calendarlist.readonly` (one forum report), so it is included.
- **Microsoft Graph.** Microsoft's reference lists `Calendars.ReadBasic` as the least-privileged delegated permission for personal accounts, with no admin consent. One Q&A thread reports a known problem with `/me/calendars` for outlook.com and live.com accounts; check it in the spike.
- **EventKit.** No Apple document found, but several projects report the same: under launchd the first EventKit call can wait forever on a permission prompt that cannot show, and the permission may be attributed to the app that launched the helper. Plan: a helper with an embedded Info.plist, permission granted once from Terminal (`docket eventkit-setup`), and a timeout on every call. Apple Reminders are reachable only through EventKit; not needed in v1.

## Resolved (Nov 14, 2026)

- [x] **Daily schedules.** A planned time to work on a task on one day; it becomes a timed event and a "Time to start" reminder.
- [x] **Done on the calendar.** Events stay, with "Done: " in front of the title; Cancel deletes them.
- [x] **Digest time.** 07:00.
- [x] **Quiet hours.** None.
- [x] **Date-only deadline.** 17:00 in your time zone.
- [x] **iCloud.** You keep some events there, so the EventKit helper is a planned read backend.
- [x] **Write calendar.** A dedicated Tasks calendar under one Google account, named in settings.
- [x] **Travel.** A deadline is a fixed instant.
- [x] **Late backoff.** 30 minutes twice, hourly 3 times, every 4 hours twice, then the daily digest.
- [x] **Time block.** A dated task gets a due-date event only; a work time only when you plan one.
- [x] **Email approvals.** The email service's approval is final; the tasks app does not ask again.
- [x] **Agent approvals.** Approving the Conductor step is final.
- [x] **Discord.** A shared Discord service of its own.
