"""Literal plan oracle plus a deterministic boundary sweep; no database or sender."""

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def oracle() -> None:
    from tests.reminder_cases import CASES

    assert len(CASES) == 19
    deltas = (-7200, -3600, -3599, -1, 0, 1, 43201)
    assert sum(delta <= -3600 for delta in deltas) * 3 == 6
    assert sum(-3600 < delta < 0 for delta in deltas) * 3 == 6
    assert sum(delta >= 0 for delta in deltas) * 3 == 9
    assert CASES[0]["expected"][0] == ["before", "2026-11-20T17:00:00+00:00"]
    assert CASES[0]["expected"][-1] == ["late", "2026-11-21T06:00:00+00:00"]
    for case in CASES:
        rows = case["expected"]
        assert len({tuple(row) for row in rows}) == len(rows)
        if case["deadline"] and case["state"] in ("open", "in_progress"):
            due = datetime.fromisoformat(case["deadline"])
            late = [datetime.fromisoformat(at) for kind, at in rows if kind == "late"]
            assert [(at - due).total_seconds() for at in late] == [
                1800,
                3600,
                7200,
                10800,
                14400,
                28800,
                43200,
            ]
    zone = ZoneInfo("America/New_York")
    assert (
        datetime(2026, 11, 1, 1, 30, tzinfo=zone, fold=0).astimezone(UTC).isoformat()
        == "2026-11-01T05:30:00+00:00"
    )
    assert (
        datetime(2027, 3, 14, 2, 30, tzinfo=zone, fold=0).astimezone(UTC).isoformat()
        == "2027-03-14T07:30:00+00:00"
    )


def examples() -> None:
    from docket import reminders
    from tests.reminder_cases import CASES, projection, task_for

    for case in CASES:
        actual = projection(
            reminders.plan_reminders(task_for(case), datetime.fromisoformat(case["now"]))
        )
        assert actual == case["expected"], case["name"]


def sweep() -> None:
    from docket import reminders
    from tests.reminder_cases import CASES, task_for

    reached = {"before": 0, "due_soon": 0, "past": 0}
    for shift in (-14, 0, 114):
        due = datetime(2026, 11, 20, 18, tzinfo=UTC) + timedelta(days=shift)
        for delta in (-7200, -3600, -3599, -1, 0, 1, 43201):
            now = due + timedelta(seconds=delta)
            case = dict(CASES[0], deadline=due.isoformat())
            task = task_for(case)
            result = reminders.plan_reminders(task, now)
            assert result == reminders.plan_reminders(task, now)
            assert [row.fire_at for row in result] == sorted(row.fire_at for row in result)
            assert len({(row.kind, row.fire_at) for row in result}) == len(result)
            assert next(row.fire_at for row in result if row.kind == "due") == due
            assert sum(row.kind == "late" for row in result) == 7
            kinds = [row.kind for row in result]
            if delta <= -3600:
                assert "before" in kinds and "due_soon" not in kinds
                reached["before"] += 1
            elif delta < 0:
                assert "due_soon" in kinds and "before" not in kinds
                reached["due_soon"] += 1
            else:
                assert "before" not in kinds and "due_soon" not in kinds
                reached["past"] += 1
    assert reached == {"before": 6, "due_soon": 6, "past": 9}


def main() -> None:
    oracle()
    print("literal and DST oracle ok")
    if "--oracle-only" in sys.argv:
        print("FAILURES 0")
        return
    failures = 0
    for label, check in (("19 complete examples", examples), ("21 boundary plans", sweep)):
        try:
            check()
        except Exception as error:
            print(f"FAIL {label}: expected exact UTC plan; {type(error).__name__}")
            failures += 1
        else:
            print(label + " ok")
    print(f"FAILURES {failures}")


if __name__ == "__main__":
    main()
