"""Phase 1d probe: what the given tests do not reach. Run from the repository root:
.venv/bin/python docs/verification/probe-01d.py

It compares the display text with the standard library's local time on random instants in ten
zones under several locales, rebuilds deadline and work-time text by its own rule, and fuzzes the
two new settings. It sets its own environment and touches no network, Keychain or data folder.
"""

import locale
import os
import random
import re
import tempfile
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, available_timezones

FAILURES = 0
ZONES = [
    "America/New_York",
    "Europe/London",
    "Asia/Tokyo",
    "Asia/Kolkata",
    "America/Sao_Paulo",
    "Australia/Lord_Howe",
    "Pacific/Chatham",
    "America/Santiago",
    "Etc/GMT+12",
    "UTC",
]
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
SHAPE = re.compile(
    r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) "
    r"([1-9]|[12][0-9]|3[01])( [0-9]{4})? ([0-9]{2}):([0-9]{2}) (\S+)"
)


def oracle_when(at: datetime, zone: str, now: datetime) -> str:
    local = at.astimezone(ZoneInfo(zone))
    text = f"{DAYS[local.weekday()]} {MONTHS[local.month - 1]} {local.day}"
    if local.year != now.astimezone(ZoneInfo(zone)).year:
        text += f" {local.year}"
    return f"{text} {local.hour:02d}:{local.minute:02d} {local.tzname()}"


def oracle_span(start: datetime, end: datetime, zone: str, now: datetime) -> str:
    begin = start.astimezone(ZoneInfo(zone))
    finish = end.astimezone(ZoneInfo(zone))
    if begin.date() != finish.date():
        return f"{oracle_when(start, zone, now)} to {oracle_when(end, zone, now)}"
    tail = f"{finish.hour:02d}:{finish.minute:02d} {finish.tzname()}"
    if begin.tzname() != finish.tzname():
        return f"{oracle_when(start, zone, now)} to {tail}"
    head = oracle_when(start, zone, now).rsplit(" ", 1)[0]
    return f"{head} to {tail}"


NOW = datetime(2026, 11, 14, 14, 0, tzinfo=UTC)
FRI = datetime(2026, 11, 20, 22, 0, tzinfo=UTC)
assert oracle_when(FRI, "America/New_York", NOW) == "Fri Nov 20 17:00 EST"
assert oracle_when(datetime(2027, 1, 8, 22, tzinfo=UTC), "America/New_York", NOW).endswith(
    "2027 17:00 EST"
)
assert (
    oracle_span(
        datetime(2026, 11, 1, 4, 30, tzinfo=UTC),
        datetime(2026, 11, 1, 7, 30, tzinfo=UTC),
        "America/New_York",
        NOW,
    )
    == "Sun Nov 1 00:30 EDT to 02:30 EST"
)
assert (
    oracle_span(
        datetime(2026, 11, 20, 19, tzinfo=UTC),
        datetime(2026, 11, 20, 20, tzinfo=UTC),
        "America/New_York",
        NOW,
    )
    == "Fri Nov 20 14:00 to 15:00 EST"
)
assert SHAPE.fullmatch("Fri Jan 8 2027 17:00 EST") and not SHAPE.fullmatch("Fri Jan 08 17:00 EST")
print("oracle: ok")


def check(label: str, function) -> None:
    global FAILURES
    try:
        passed = function()
    except Exception as error:  # noqa: BLE001
        passed = False
        label = f"{label} (raised {type(error).__name__})"
    if not passed:
        FAILURES += 1
    print(f"{label}: {'ok' if passed else 'FAIL'}")


def instant(rng: random.Random) -> datetime:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return start + timedelta(minutes=rng.randrange(2 * 366 * 24 * 60))


def locales() -> list[str]:
    found = []
    for name in ("C", "fr_FR.UTF-8", "de_DE.UTF-8", "ja_JP.UTF-8", "tr_TR.UTF-8"):
        try:
            locale.setlocale(locale.LC_TIME, name)
            found.append(name)
        except locale.Error:
            continue
    locale.setlocale(locale.LC_TIME, "C")
    return found


def when_matches_the_library() -> bool:
    from docket.views import when

    rng = random.Random(21)
    names = locales()
    saved = locale.setlocale(locale.LC_TIME)
    try:
        for turn in range(4000):
            locale.setlocale(locale.LC_TIME, names[turn % len(names)])
            at, now, zone = instant(rng), instant(rng), rng.choice(ZONES)
            found = when(at, zone, now)
            if found != oracle_when(at, zone, now) or not SHAPE.fullmatch(found):
                print(f"  {at} {zone} {now}: {found!r}")
                return False
    finally:
        locale.setlocale(locale.LC_TIME, saved)
    return len(names) >= 2


def texts_are_built_from_when() -> bool:
    from docket.deadlines import Deadline, WorkTime
    from docket.views import deadline_text, work_text

    rng = random.Random(22)
    for _ in range(3000):
        home, zone = rng.choice(ZONES), rng.choice(ZONES)
        at, now = instant(rng), instant(rng)
        given = rng.random() < 0.5
        expected = oracle_when(at, home, now)
        if zone != home:
            expected += f" ({oracle_when(at, zone, now)} where set)"
        if not given:
            expected += ", no time given"
        if deadline_text(Deadline(at, zone, given), home, now) != expected:
            print(f"  deadline {at} {zone} in {home}")
            return False
        work = WorkTime(at, rng.choice((5, 30, 60, 90, 720)), zone)
        expected = oracle_span(work.start, work.end, home, now)
        if zone != home:
            expected += f" ({oracle_span(work.start, work.end, zone, now)} where set)"
        if work_text(work, home, now) != expected:
            print(f"  work {at} {work.minutes} {zone} in {home}: {work_text(work, home, now)!r}")
            return False
    return True


def status_follows_its_table() -> bool:
    from docket.deadlines import Deadline
    from docket.store import Task
    from docket.views import status_text

    rng = random.Random(23)
    words = {"open": "open", "in_progress": "in progress", "done": "done", "cancelled": "cancelled"}
    for _ in range(2000):
        state = rng.choice(list(words))
        at, now = instant(rng), instant(rng)
        deadline = Deadline(at, "UTC", True) if rng.random() < 0.7 else None
        expected = words[state]
        if deadline is not None and state in ("open", "in_progress") and now >= at:
            expected += ", due" if now < at + timedelta(minutes=30) else ", overdue"
        task = Task("t1", "Pay rent", state, deadline, None, "owner", None, None, None, now, now)
        if status_text(task, now) != expected:
            return False
    return True


def settings_are_checked_exactly() -> bool:
    from docket.config import ConfigError, get_settings

    rng = random.Random(24)
    zones = available_timezones()
    os.environ["DOCKET_DATA_DIR"] = tempfile.mkdtemp()
    values = ["", "UTC", "utc", "America/New_York", "America/New_York\n", "a" * 300]
    for _ in range(400):
        base = rng.choice(ZONES)
        where = rng.randrange(len(base) + 1)
        values.append(base[:where] + rng.choice("/._- \nAz9é") + base[where:])
    try:
        for value in values:
            os.environ["DOCKET_TIME_ZONE"] = value
            try:
                found = get_settings().time_zone
            except ConfigError as error:
                if (
                    str(error) != "DOCKET_TIME_ZONE must be a time zone name"
                    or value in zones
                    or value == ""
                ):
                    return False
                continue
            if found != (value or None) or (value and value not in zones):
                return False
        del os.environ["DOCKET_TIME_ZONE"]
        for number in list(range(-3, 730)) + ["", "x", "1e2", "5.5"]:
            os.environ["DOCKET_WORK_MINUTES"] = str(number)
            try:
                found = get_settings().work_minutes
            except ConfigError as error:
                if str(error) != "DOCKET_WORK_MINUTES must be 5 to 720":
                    return False
                if isinstance(number, int) and 5 <= number <= 720:
                    return False
                continue
            if not (isinstance(number, int) and 5 <= number <= 720 and found == number):
                return False
    finally:
        for key in ("DOCKET_TIME_ZONE", "DOCKET_WORK_MINUTES", "DOCKET_DATA_DIR"):
            os.environ.pop(key, None)
    return True


check("when matches the library in ten zones and every locale here", when_matches_the_library)
check("deadline and work-time text are built from when", texts_are_built_from_when)
check("the status word follows its table", status_follows_its_table)
check("the new settings accept exactly what they should", settings_are_checked_exactly)

print(f"FAILURES {FAILURES}")
