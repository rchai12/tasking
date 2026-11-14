"""Phase 1a probe: what the given tests do not reach. Run from the repository root:
.venv/bin/python docs/verification/probe-01a.py

It checks the time rules against its own oracle in nine zones, on every half hour of each zone's
daylight-saving change days in 2026 and 2027 and on random days, and fuzzes the zone name.
It reads no clock, keychain or data folder.
"""

import random
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

FAILURES = 0
ZONES = [
    "America/New_York",
    "Europe/London",
    "Australia/Sydney",
    "Australia/Lord_Howe",
    "America/Santiago",
    "America/Sao_Paulo",
    "Asia/Kolkata",
    "Pacific/Chatham",
    "UTC",
]
MESSAGES = {
    "unknown time zone",
    "a time is hours and minutes only",
    "a work time is 5 to 720 minutes",
    "a work time must end by midnight",
    "a work time must end by the deadline",
}


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


# Oracle: a wall time's instant, built from offsets, never from fold.
def offsets(zone: ZoneInfo, wall: datetime) -> set[timedelta]:
    found = set()
    for hours in range(-48, 49):
        instant = (wall - timedelta(hours=hours)).replace(tzinfo=UTC)
        found.add(instant.astimezone(zone).utcoffset())
    return found


def oracle_instant(day: date, at: time, name: str) -> datetime:
    zone = ZoneInfo(name)
    wall = datetime.combine(day, at)
    matches = []
    for offset in offsets(zone, wall):
        instant = (wall - offset).replace(tzinfo=UTC)
        if instant.astimezone(zone).replace(tzinfo=None) == wall:
            matches.append(instant)
    if matches:
        return min(matches)  # a repeated time is the first one
    before = (wall - timedelta(days=1)).replace(tzinfo=UTC).astimezone(zone).utcoffset()
    return (wall - before).replace(tzinfo=UTC)  # a missing time moves forward


def change_days(name: str) -> list[date]:
    zone = ZoneInfo(name)
    days, day = [], date(2026, 1, 1)
    while day < date(2028, 1, 1):
        start = datetime.combine(day, time(0), tzinfo=UTC).astimezone(zone).utcoffset()
        end = datetime.combine(day, time(23, 59), tzinfo=UTC).astimezone(zone).utcoffset()
        if start != end:
            days.extend([day - timedelta(days=1), day, day + timedelta(days=1)])
        day += timedelta(days=1)
    return sorted(set(days))


NY = "America/New_York"
assert oracle_instant(date(2027, 3, 14), time(2, 30), NY) == datetime(
    2027, 3, 14, 7, 30, tzinfo=UTC
)
assert oracle_instant(date(2026, 11, 1), time(1, 30), NY) == datetime(
    2026, 11, 1, 5, 30, tzinfo=UTC
)
assert oracle_instant(date(2026, 11, 20), time(17), NY) == datetime(2026, 11, 20, 22, 0, tzinfo=UTC)
assert date(2026, 11, 1) in change_days(NY) and date(2027, 3, 14) in change_days(NY)
assert change_days("UTC") == []
print("oracle: ok")

HALF_HOURS = [time(hour, minute) for hour in range(24) for minute in (0, 30)]


def deadlines_match_on_change_days() -> bool:
    from docket.deadlines import make_deadline

    cases = 0
    for name in ZONES:
        for day in change_days(name):
            for at in HALF_HOURS:
                found = make_deadline(day, at, name)
                if found.at != oracle_instant(day, at, name) or found.at.tzinfo is not UTC:
                    print(f"  {name} {day} {at}: {found.at} != {oracle_instant(day, at, name)}")
                    return False
                cases += 1
    return cases > 1000


def date_only_is_five_pm_everywhere() -> bool:
    from docket.deadlines import make_deadline

    rng = random.Random(1)
    for _ in range(500):
        name = rng.choice(ZONES)
        day = date(2026, 1, 1) + timedelta(days=rng.randrange(730))
        found = make_deadline(day, None, name)
        if found.time_given or found.at != oracle_instant(day, time(17), name):
            return False
    return True


def oracle_midnight(day: date, name: str) -> datetime:
    return oracle_instant(day + timedelta(days=1), time(0), name)


def work_times_follow_the_rules() -> bool:
    from docket.deadlines import DeadlineError, make_deadline, make_work_time

    rng = random.Random(2)
    reached = {
        message: 0
        for message in MESSAGES - {"unknown time zone", "a time is hours and minutes only"}
    }
    reached["accepted"] = 0
    for turn in range(4000):
        name = rng.choice(ZONES)
        days = change_days(name) or [date(2026, 6, 1)]
        day = (
            rng.choice(days) if turn % 2 else date(2026, 1, 1) + timedelta(days=rng.randrange(730))
        )
        start = time(rng.randrange(24), rng.choice((0, 15, 30, 45)))
        minutes = rng.choice((rng.randrange(-5, 800), 5, 720, 4, 721))
        deadline = None
        if rng.random() < 0.5:
            deadline = make_deadline(day, time(rng.randrange(24), rng.choice((0, 30))), name)
        begins = oracle_instant(day, start, name)
        ends = begins + timedelta(minutes=minutes)
        if not 5 <= minutes <= 720:
            expected = "a work time is 5 to 720 minutes"
        elif ends > oracle_midnight(day, name):
            expected = "a work time must end by midnight"
        elif deadline is not None and ends > deadline.at:
            expected = "a work time must end by the deadline"
        else:
            expected = "accepted"
        try:
            work = make_work_time(day, start, minutes, name, deadline)
            found = "accepted"
            if (work.start, work.end, work.minutes, work.zone) != (begins, ends, minutes, name):
                print(f"  {name} {day} {start} {minutes}: wrong value {work}")
                return False
        except DeadlineError as error:
            found = str(error)
        if found != expected:
            print(f"  {name} {day} {start} {minutes} {deadline}: {found!r} != {expected!r}")
            return False
        reached[expected] += 1
    return all(count >= 20 for count in reached.values())


def status_follows_the_window() -> bool:
    from docket.deadlines import make_deadline, status

    rng = random.Random(3)
    for _ in range(2000):
        found = make_deadline(date(2026, 11, 20), time(17), NY)
        now = found.at + timedelta(seconds=rng.randrange(-7200, 7200))
        if rng.random() < 0.3:
            now = now.astimezone(ZoneInfo(rng.choice(ZONES)))
        if now < found.at:
            expected = "upcoming"
        elif now < found.at + timedelta(minutes=30):
            expected = "due"
        else:
            expected = "overdue"
        if status(found, now) != expected:
            return False
    return True


def odd_zone_names_are_refused_cleanly() -> bool:
    from docket.deadlines import DeadlineError, make_deadline, make_work_time

    rng = random.Random(4)
    names = ["", " ", "\x00", "UTC\x00", "/etc/localtime", "..", "America/../UTC", "a" * 5000]
    names += ["America/New_York".swapcase(), "utc", "Etc/UTC/", "Europe/London\n"]
    for _ in range(300):
        base = rng.choice(ZONES)
        where = rng.randrange(len(base) + 1)
        names.append(base[:where] + rng.choice("/._- \x00\nAz9é") + base[where:])
    for name in names:
        for call in (
            lambda name=name: make_deadline(date(2026, 11, 20), time(9), name),
            lambda name=name: make_work_time(date(2026, 11, 20), time(9), 60, name, None),
        ):
            try:
                found = call()
            except DeadlineError as error:
                if str(error) != "unknown time zone":
                    return False
                continue
            try:
                ZoneInfo(name)
            except Exception:  # noqa: BLE001
                return False
            if found.zone != name:
                return False
    return True


check("deadlines match the oracle on every change day's half hours", deadlines_match_on_change_days)
check("a date-only deadline is 17:00 in every zone", date_only_is_five_pm_everywhere)
check("work times follow the length, midnight and deadline rules", work_times_follow_the_rules)
check("status follows the 30-minute window from any zone", status_follows_the_window)
check("odd zone names are refused with the zone message only", odd_zone_names_are_refused_cleanly)

print(f"FAILURES {FAILURES}")
