# Phase 1d: Settings and display text

## Goal

Give the app your time zone and the default length of a work time as settings, and one place that turns a time, a deadline, a work time and a task's status into text. The `docket tasks` commands (Phase 1e) and later the Discord cards both show times through these functions, so a deadline reads the same everywhere. Times show in your zone, and also in the zone a deadline or work time was set in when that differs. The task list line, the task detail view and the commands themselves are Phase 1e.

Sections: `core`. The `tooling` section runs in the full check.

Follow `docs/phase-conventions.md`. N is 291, the tests the previous phase left passing.

Start: `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_settings.py --ignore=tests/unit/test_views.py` must show `291 passed`. The ignored files import names you create.

## Facts

Each checked on this machine on 2026-11-14 with Python 3.12.16, pydantic-settings 2.16.3 and pydantic 2.14.

- **`strftime` follows the locale.** Under `fr_FR.UTF-8`, `strftime("%a %b")` gives `ven. nov.`, so day and month names must come from fixed English tables, not `strftime`. `fr_FR.UTF-8` is installed here.
- **Zone abbreviations** come from `tzname()` and are not always letters: `EST`/`EDT`, `JST`, `IST` (Asia/Kolkata), `GMT`/`BST`, `UTC`, `-03` (America/Sao_Paulo), `+11` and `+1030` (Australia/Lord_Howe).
- **pydantic reads an `int` setting leniently**: `"60"`, `" 60"` and `"60.0"` are 60; `""`, `"abc"`, `"1e2"` and `"5.5"` fail with a `ValidationError`.
- **An empty variable** (`DOCKET_TIME_ZONE=""`) reaches a `str | None` field as `""`, not `None`.
- **Today's `get_settings()`** turns every `ValidationError` into `DATA_DIR_MESSAGE`. With new fields, each needs its own message.
- **`ZoneInfo("america/new_york")` loads on macOS** (Phase 1a's fact), so a zone setting is checked against `zoneinfo.available_timezones()`, exactly.
- The expected strings in the given tests were all computed with `datetime.astimezone`, `weekday()` and `tzname()`, not by hand.

## Owner's decisions

Decided 2026-11-14:

- **Split of the rest of stage 1:** 1d the settings and display text (this phase), 1e the `docket tasks` commands.
- **Times show in your zone, and also where set:** a deadline or work time set in another zone also shows that zone's time, as `(... where set)`.
- **Commands take ISO dates and times** (`2026-11-20`, `17:00`) in your zone; words like "Friday" come later with the Discord deadline form. (Used by Phase 1e; nothing in 1d reads input.)
- **`DOCKET_TIME_ZONE` has no default.** A command that needs it refuses with `DOCKET_TIME_ZONE is not set`. The app never reads the machine's zone.

## Architect's decisions

- **An empty `DOCKET_TIME_ZONE` counts as not set**, so an empty line in a launchd file means the same as no line.
- **The format of a time** is `<Day> <Mon> <day>[ <year>] <HH:MM> <abbreviation>`: English three-letter names, the day without a leading zero, a 24-hour clock, the year only when it differs from `now`'s year in the same zone. For example `Fri Nov 20 17:00 EST`, `Fri Jan 8 2027 17:00 EST`.
- **A work time is a span**: one date when it starts and ends on the same local day, one abbreviation when it doesn't change in between (`Fri Nov 20 14:00 to 15:00 EST`, `Sun Nov 1 00:30 EDT to 02:30 EST`), and two full times otherwise.
- **A no-time-given deadline says so** (`, no time given`), so a 17:00 you never typed is never mistaken for one you did.
- **The first bad setting wins**, in the order `data_dir`, `time_zone`, `work_minutes`.
- **`views.py` is not critical** (it decides no rule), but its coverage gate is 100% like this phase's other module; `config.py` stays critical.

## Requirements

1. **`src/docket/config.py`, messages**: `TIME_ZONE_MESSAGE = "DOCKET_TIME_ZONE must be a time zone name"`, `TIME_ZONE_UNSET_MESSAGE = "DOCKET_TIME_ZONE is not set"`, `WORK_MINUTES_MESSAGE = "DOCKET_WORK_MINUTES must be 5 to 720"`. `DATA_DIR_MESSAGE` and everything Phase 0 gave `data_dir` stay as they are.
2. **`Settings.time_zone: str | None`**, from `DOCKET_TIME_ZONE`, default `None`. An empty value is `None`. Any other value must be a member of `zoneinfo.available_timezones()` exactly (no trimming, no case folding).
3. **`Settings.work_minutes: int`**, from `DOCKET_WORK_MINUTES`, default 60: a whole number as pydantic reads an `int`, from 5 to 720.
4. **`get_settings()`** raises `ConfigError` with the message of the first field that fails, in the order `data_dir` (`DATA_DIR_MESSAGE`), `time_zone` (`TIME_ZONE_MESSAGE`), `work_minutes` (`WORK_MINUTES_MESSAGE`), and never chains the pydantic error (`from None`).
5. **`home_zone(settings: Settings) -> str`** returns `settings.time_zone`, or raises `ConfigError(TIME_ZONE_UNSET_MESSAGE)` when it is `None`.
6. **`src/docket/views.py`, `when(at: datetime, zone: str, now: datetime) -> str`**: `at` in `zone`, as `<Day> <Mon> <day>[ <year>] <HH:MM> <abbreviation>`. Day names are `Mon` to `Sun` by `weekday()`, month names `Jan` to `Dec`; the day of the month has no leading zero; hours and minutes have two digits; the abbreviation is `tzname()` of the local time; the year (four digits) appears only when the local year of `at` differs from the year of `now` in `zone`. The result never depends on the locale.
7. **`deadline_text(deadline: Deadline, home: str, now: datetime) -> str`**: `when(deadline.at, home, now)`; then, when `deadline.zone != home`, ` (<when(deadline.at, deadline.zone, now)> where set)`; then, when `time_given` is false, `, no time given`.
8. **`work_text(work: WorkTime, home: str, now: datetime) -> str`**: the span of `work.start` to `work.end` in `home`; then, when `work.zone != home`, ` (<the span in work.zone> where set)`. The span of `start` to `end` in a zone is:
   - when they fall on different local dates: `<when(start)> to <when(end)>`;
   - else when their abbreviations differ: `<when(start)> to <HH:MM> <end's abbreviation>`;
   - else: `<when(start)> without its abbreviation`, ` to <HH:MM> <abbreviation>` (`Fri Nov 20 14:00 to 15:00 EST`).
9. **`status_text(task: Task, now: datetime) -> str`**: `open`, `in progress`, `done` or `cancelled` for the stored state; for an `open` or `in_progress` task with a deadline whose `deadlines.status(deadline, now)` is `due` or `overdue`, followed by `, due` or `, overdue`.
10. **Pure views.** `views.py` reads no clock, settings, store or environment, and calls no `strftime` and nothing from `locale`.
11. **Progress entry** for `## Phase 1d: Settings and display text (YYYY-MM-DD)` at the end of `docs/progress.md`.

## Given files

Already committed with this spec; never change them.

| File | What it is |
|---|---|
| `tests/unit/test_settings.py` | 24 tests from 8 functions (requirements 1 to 5). Two rows, `test_the_first_bad_setting_is_reported[data-dir-first]` and `[data-dir-before-length]`, already pass today: they guard that the data folder's message stays first once the new fields exist |
| `tests/unit/test_views.py` | 30 tests from 6 functions (requirements 6 to 10) |
| `docs/verification/probe-01d.py` | The verifier's probe |

Given test count: **54**.

## Tests to write

The given tests cover every requirement's main cases. To reach full coverage, add behaviour tests in new `tests/unit/test_settings_more.py` or `tests/unit/test_views_more.py` files, never by changing a given test.

## Scope

| Path | Change |
|---|---|
| `src/docket/config.py` | edit: the two settings, the messages, `get_settings`'s mapping, `home_zone` |
| `src/docket/views.py` | create |
| `tests/unit/test_settings_more.py`, `tests/unit/test_views_more.py` | create, only if coverage needs them |
| `docs/progress.md` | append your entry |

## Out of scope

- The task list line, the task detail view, and every `docket tasks` command (Phase 1e).
- Reading a typed date, time or duration; words like "today" or "Friday".
- Any other setting (the port, the owner's Discord id, the digest time).
- Reading the machine's time zone, `TZ`, or `time.tzname`, as a default or otherwise.
- Relative text ("in 2 hours", "tomorrow"), colour, or column alignment.
- Any change to `deadlines.py`, `store.py`, `core.py`, a given file, `AGENTS.md` or the design docs.

## Rules that bite

- **No machine zone and no locale**: every zone comes from an argument or the setting; names come from fixed tables.
- **Error messages are constant text**: the three new messages exactly, never with the value that was set.
- **Pure views**: every instant, zone and `now` is an argument.
- Commands start with `.venv/bin/python`; no bare `python3`, `pytest` or `ruff`.

## Acceptance

| Command | Must show |
|---|---|
| `.venv/bin/python -m pytest --no-cov -q --ignore=tests/unit/test_settings.py --ignore=tests/unit/test_views.py` (before you start) | `291 passed` |
| `.venv/bin/python scripts/check.py --first core` | last line `All checks passed.`; summary lists `tests (core): passed`; at least 345 passed, 0 failed, 0 skipped |
| `.venv/bin/python -m pytest tests/unit/test_settings.py tests/unit/test_views.py --no-cov -q` | `54 passed` |
| `.venv/bin/python -m coverage report --include=src/docket/config.py,src/docket/views.py --fail-under=100`, right after `check.py` | exit 0, `TOTAL` at `100%` |
| `.venv/bin/python docs/verification/probe-01d.py` | last line `FAILURES 0` |
| `grep -c "^## Phase 1d: " docs/progress.md` | `1` |
| `.venv/bin/python scripts/check_reports.py --phase 1d` | `Reports OK.` |
| `git diff HEAD --stat -- tests/unit/test_settings.py tests/unit/test_views.py docs/verification/probe-01d.py` | no output |
| `git status --short` | only the Scope paths |

### Searches

Each prints nothing.

```zsh
git grep --untracked -n -E 'import (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)|from (socket|ssl|http|urllib|requests|httpx)([^A-Za-z_]|$)' -- src
git grep --untracked -n -E 'print\(|logging|logger|warnings\.warn' -- src ':!src/docket/cli.py'
git grep --untracked -n -E 'datetime\.now|datetime\.utcnow|date\.today|time\.time\(|from docket\.(clock|ids) import' -- src ':!src/docket/clock.py'
git grep --untracked -n -E 'strftime\(|import locale|from locale|clock\.now|get_settings\(|os\.environ|getenv\(' -- src/docket/views.py
git grep --untracked -n -E 'tzlocal|time\.tzname|localtime\(|astimezone\(\)|environ\[.TZ.\]' -- src
git grep --untracked -n -E 'ollama|anthropic|openai|langchain' -- src
git grep --untracked -n -E 'pragma: no cover|noqa' -- src/docket/config.py src/docket/views.py
```
