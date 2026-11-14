# Phase 1a: Time rules

## Goal

Give every later phase one tested place for the app's time rules: a deadline as a UTC instant plus the IANA zone it was given in (with 17:00 for a date with no time), a planned work time as a start and a length on one day, and whether a deadline is upcoming, due or overdue at a given moment. The module is pure: it reads no clock, settings, database or network. The database and the state rules come in Phase 1b, and the `docket tasks` commands, display text and settings (`DOCKET_TIME_ZONE`, `DOCKET_WORK_MINUTES`) in Phase 1c.

Sections: `core`. The `tooling` section runs in the full check.

Follow `docs/phase-conventions.md`. N is 96, the tests the previous phase left passing.

Start: `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_deadlines.py` must show `96 passed`. The ignored file imports the module you create.

## Facts

Each checked on this machine on 2026-11-14 with Python 3.12.16 and its `zoneinfo`.

- **A time that doesn't exist.** On 2027-03-14 New York's clocks jump from 02:00 to 03:00. `datetime.combine(date(2027, 3, 14), time(2, 30), tzinfo=ZoneInfo("America/New_York"))` with the default `fold=0` converts to `2027-03-14T07:30:00+00:00`, which reads back as 03:30 EDT. With `fold=1` it is 06:30 UTC (01:30 EST).
- **A time that happens twice.** On 2026-11-01 01:30 happens in EDT and again in EST. `fold=0` gives `2026-11-01T05:30:00+00:00` (the first), `fold=1` gives 06:30 UTC.
- **Zone names.** `ZoneInfo("america/new_york")` loads on macOS, because the file system ignores case, so loading a zone is no check of its name. `zoneinfo.available_timezones()` returns the exact names (598 here): it holds `America/New_York`, `UTC`, `EST5EDT` and `US/Eastern`, and not `america/new_york` or `localtime`. `ZoneInfo("")` and `ZoneInfo("../etc/passwd")` raise `ValueError`, `ZoneInfo("Local")` raises `ZoneInfoNotFoundError`.
- **UTC.** `datetime.UTC is timezone.utc`, and `timezone(timedelta(0))` is that same object, as is the `tzinfo` of `datetime.fromisoformat("...+00:00")` and of any `astimezone(UTC)`. `ZoneInfo("UTC")` is a different object.
- **Midnight is not 24 hours later on a change day.** New York's 2027-03-14 runs from 05:00 UTC to 04:00 UTC the next day (23 hours); 2026-11-01 runs from 04:00 to 05:00 UTC the next day (25 hours).

## Owner's decisions

Decided 2026-11-14:

- **Split of stage 1:** 1a the time rules (this phase), 1b the database, state rules and audit log in `docket.core`, 1c the `docket tasks` commands.
- **A time that doesn't exist moves forward:** 02:30 on the spring-forward day becomes 03:30, Python's `fold=0` instant. The task keeps `time_given` true.
- **A time that happens twice is the first one** (the earlier instant, daylight time), so a deadline errs early.
- **A work time is 5 to 720 minutes, ends by the task's deadline, and ends by midnight** of its day in its zone.
- Earlier (in `docs/decisions.md`): a date with no time is 17:00 in its zone; a deadline is a fixed instant; there are no quiet hours.

## Architect's decisions

- **Exact zone names only.** A zone is accepted only when it is in `zoneinfo.available_timezones()`, compared as the exact string: no case folding, no trimming. Legacy names in that set (`EST5EDT`, `US/Eastern`) are accepted.
- **Due lasts 30 minutes** (`DUE_WINDOW`), until the first late reminder; after that a deadline is overdue.
- **Lengths are real minutes**: a work time's end is its start instant plus its minutes, so a 3-hour block on the fall-back day ends at the wall time 2 hours later.
- **Midnight** is the instant of 00:00 on the next day in the work time's zone, worked out by the same rule as any other wall time. A work time may end exactly at midnight.
- **Stored values check themselves.** `Deadline` and `WorkTime` refuse a non-UTC instant and an unknown zone when they are built, and `WorkTime` refuses a length outside 5 to 720, so a value read back from the database in Phase 1b is held to the same rules. Day and deadline rules need inputs a stored value doesn't have, so only `make_work_time` checks them.
- **The order of checks is fixed**, so the first broken rule is the one reported: the time's shape, then the zone, then the length, then midnight, then the deadline.
- **Critical module:** `deadlines.py` (added to `scripts/critical_modules.txt`).

## Requirements

1. **`src/docket/deadlines.py`, constants**: `DEFAULT_TIME = time(17, 0)`; `DUE_WINDOW = timedelta(minutes=30)`; `WORK_MINUTES_MIN = 5`; `WORK_MINUTES_MAX = 720`; and the messages, exactly:
   - `ZONE_MESSAGE = "unknown time zone"`
   - `TIME_MESSAGE = "a time is hours and minutes only"`
   - `INSTANT_MESSAGE = "an instant must be in UTC"`
   - `WORK_LENGTH_MESSAGE = "a work time is 5 to 720 minutes"`
   - `WORK_DAY_MESSAGE = "a work time must end by midnight"`
   - `WORK_DEADLINE_MESSAGE = "a work time must end by the deadline"`
2. **`DeadlineError(ValueError)`**. Every refusal in this module raises it with exactly one of the messages above, and nothing else; no other exception escapes for a refused input.
3. **Zones.** A zone name is valid only if it is a member of `zoneinfo.available_timezones()` (exact string). An invalid one raises `DeadlineError(ZONE_MESSAGE)` before `ZoneInfo` is called with it.
4. **`Deadline`**: a frozen dataclass with fields in this order: `at: datetime`, `zone: str`, `time_given: bool`. On construction it raises `DeadlineError(INSTANT_MESSAGE)` unless `at.tzinfo is datetime.UTC`, then `DeadlineError(ZONE_MESSAGE)` for an invalid zone.
5. **`make_deadline(day: date, at: time | None, zone: str) -> Deadline`**:
   - A time with seconds, microseconds or a `tzinfo` raises `DeadlineError(TIME_MESSAGE)`; then an invalid zone raises `DeadlineError(ZONE_MESSAGE)`.
   - `None` means `DEFAULT_TIME`, and `time_given` is false; otherwise `time_given` is true.
   - The wall time `day` at that time in `zone` becomes its instant with `fold=0`: a time that doesn't exist moves forward, and a time that happens twice is the first one. `at` is that instant in UTC.
6. **`WorkTime`**: a frozen dataclass with fields in this order: `start: datetime`, `minutes: int`, `zone: str`, and a property `end -> datetime` (`start + timedelta(minutes=minutes)`). On construction it raises, in this order: `DeadlineError(INSTANT_MESSAGE)` unless `start.tzinfo is datetime.UTC`; `DeadlineError(ZONE_MESSAGE)` for an invalid zone; `DeadlineError(WORK_LENGTH_MESSAGE)` unless `WORK_MINUTES_MIN <= minutes <= WORK_MINUTES_MAX`.
7. **`make_work_time(day: date, start: time, minutes: int, zone: str, deadline: Deadline | None) -> WorkTime`** checks in this order, raising the first that fails:
   - the time's shape (`TIME_MESSAGE`, as in requirement 5);
   - the zone (`ZONE_MESSAGE`);
   - the length (`WORK_LENGTH_MESSAGE`);
   - the end after midnight, the instant of 00:00 on the next day in `zone` (`WORK_DAY_MESSAGE`);
   - the end after `deadline.at`, when there is a deadline (`WORK_DEADLINE_MESSAGE`).

   The start is the wall time's instant by the rule of requirement 5. An end equal to midnight or to the deadline is accepted. The deadline may be in another zone; instants are compared.
8. **`status(deadline: Deadline, now: datetime) -> str`** returns `"upcoming"` when `now < deadline.at`, `"due"` when `deadline.at <= now < deadline.at + DUE_WINDOW`, and `"overdue"` otherwise. `now` is any aware datetime; instants are compared.
9. **Pure.** The module reads no clock (`docket.clock` included), settings, environment, file, database or network, and keeps no state between calls other than a cache of the zone names.
10. **Progress entry** for `## Phase 1a: Time rules (YYYY-MM-DD)` at the end of `docs/progress.md`.

## Given files

Already committed with this spec; never change them.

| File | What it is |
|---|---|
| `tests/unit/test_deadlines.py` | 56 tests from 15 functions (requirements 1 to 9) |
| `scripts/critical_modules.txt` | Adds `deadlines.py` |
| `docs/verification/probe-01a.py` | The verifier's probe |

Given test count: **56**.

## Tests to write

The given tests cover every requirement's main cases. To reach full coverage, add behaviour tests in a new `tests/unit/test_deadlines_more.py`, never by changing a given test.

## Scope

| Path | Change |
|---|---|
| `src/docket/deadlines.py` | create |
| `tests/unit/test_deadlines_more.py` | create, only if coverage needs it |
| `docs/progress.md` | append your entry |

## Out of scope

- The database, storing or reading deadlines, the state rules, `docket.core`, the audit log (Phase 1b).
- Display text for a deadline or work time, the `docket tasks` commands, and any setting (`DOCKET_TIME_ZONE`, `DOCKET_WORK_MINUTES`) (Phase 1c).
- Reading a typed deadline ("Friday", "tomorrow 5 pm"): a later phase with the deadline form.
- Reminder plans, the late backoff, quiet hours, the digest (stage 3).
- Checking that a deadline or work time is in the future: it needs the clock, and belongs with the code that creates tasks.
- More than one work time per task, or one that repeats.
- Any change to a given file, `AGENTS.md` or the design docs.

## Rules that bite

- **Pure time rules**: no `clock.now()`, no `datetime.now()`, no settings. Every instant comes from the arguments.
- **No local time strings, no machine zone**: never call `astimezone()` without a zone, and never use `time.localtime` or `TZ`.
- **Error messages are constant text**: the six messages exactly, never with the zone name, the time or a library's error text.
- Commands start with `.venv/bin/python`; no bare `python3`, `pytest` or `ruff`.

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_deadlines.py` (before you start) | `96 passed` |
| `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 152 passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest tests/unit/test_deadlines.py --no-cov -q` | `56 passed` |
| `.venv/bin/python -m coverage report --include=src/docket/deadlines.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| `.venv/bin/python docs/verification/probe-01a.py` | last line `FAILURES 0` |
| `grep -c "^## Phase 1a: " docs/progress.md` | `1` |
| `.venv/bin/python scripts/check_reports.py --phase 1a` | `Reports OK.` |
| `git diff HEAD --stat -- tests/unit/test_deadlines.py scripts/critical_modules.txt docs/verification/probe-01a.py` | no output |
| `git status --short` | only the Scope paths |

### Searches

Each prints nothing.

```zsh
git grep --untracked -n -E 'import (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)|from (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)' -- src
git grep --untracked -n -E 'print\(|logging|logger|warnings\.warn' -- src ':!src/docket/cli.py'
git grep --untracked -n -E 'datetime\.now|datetime\.utcnow|date\.today|time\.time\(|from docket\.(clock|ids) import' -- src ':!src/docket/clock.py'
git grep --untracked -n -E '(from|import) docket|get_settings\(|os\.environ|getenv\(|localtime\(|astimezone\(\)' -- src/docket/deadlines.py
git grep --untracked -n -E 'ollama|anthropic|openai|langchain' -- src
git grep --untracked -n -E 'pragma: no cover|noqa' -- src/docket/deadlines.py
```
