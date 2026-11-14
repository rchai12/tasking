from datetime import UTC, datetime

import pytest

from docket.core import Outcome
from docket.deadlines import Deadline, WorkTime
from docket.store import Task
from docket.views import edited_text, planned_text

NY = "America/New_York"
CREATED = datetime(2026, 11, 13, 13, 0, tzinfo=UTC)
UPDATED = datetime(2026, 11, 14, 14, 0, tzinfo=UTC)
SATURDAY_9AM = Deadline(datetime(2026, 11, 21, 14, 0, tzinfo=UTC), NY, True)
FRIDAY_5PM = Deadline(datetime(2026, 11, 20, 22, 0, tzinfo=UTC), NY, False)
FRIDAY_WORK = WorkTime(datetime(2026, 11, 20, 19, 0, tzinfo=UTC), 60, NY)
SPRING_WORK = WorkTime(datetime(2027, 3, 14, 7, 30, tzinfo=UTC), 60, NY)


def outcome(changed: bool, **fields: object) -> Outcome:
    values: dict[str, object] = {
        "id": "t3",
        "title": "Pay rent",
        "state": "open",
        "deadline": None,
        "work": None,
        "source": "owner",
        "provider": None,
        "message_id": None,
        "link": None,
        "created_at": CREATED,
        "updated_at": UPDATED,
    }
    values.update(fields)
    return Outcome(task=Task(**values), changed=changed)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (outcome(True, deadline=SATURDAY_9AM), "Updated t3: Pay rent, due Sat Nov 21 09:00 EST"),
        (
            outcome(True, deadline=FRIDAY_5PM, title="Pay rent today"),
            "Updated t3: Pay rent today, due Fri Nov 20 17:00 EST, no time given",
        ),
        (outcome(True), "Updated t3: Pay rent, no deadline"),
        (outcome(False, deadline=SATURDAY_9AM), "Nothing changed for t3."),
    ],
    ids=["new-deadline", "new-title-and-date-only", "no-deadline", "nothing-changed"],
)
def test_an_edit_reads_as_the_task_after_it(result: Outcome, expected: str) -> None:
    assert edited_text(result, NY) == expected


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (outcome(True, work=FRIDAY_WORK), "Planned t3: Fri Nov 20 14:00 to 15:00 EST"),
        (outcome(True, work=SPRING_WORK), "Planned t3: Sun Mar 14 2027 03:30 to 04:30 EDT"),
        (outcome(True), "Cleared the work time of t3."),
        (outcome(False, work=FRIDAY_WORK), "Nothing changed for t3."),
        (outcome(False), "Nothing changed for t3."),
    ],
    ids=["planned", "planned-next-year", "cleared", "same-plan", "already-clear"],
)
def test_a_plan_reads_as_its_work_time(result: Outcome, expected: str) -> None:
    assert planned_text(result, NY) == expected


def test_the_texts_use_the_change_time_not_the_clock() -> None:
    later = outcome(True, work=SPRING_WORK, updated_at=datetime(2027, 1, 2, tzinfo=UTC))
    assert planned_text(later, NY) == "Planned t3: Sun Mar 14 03:30 to 04:30 EDT"
    dated = outcome(True, deadline=SATURDAY_9AM, updated_at=datetime(2025, 6, 1, tzinfo=UTC))
    assert edited_text(dated, NY) == "Updated t3: Pay rent, due Sat Nov 21 2026 09:00 EST"
