from datetime import UTC, datetime

import pytest

from docket.deadlines import Deadline, WorkTime
from docket.store import Task
from docket.views import refusal_text, task_detail, task_line

NY = "America/New_York"
NOW = datetime(2026, 11, 14, 14, 0, tzinfo=UTC)
CREATED = datetime(2026, 11, 13, 13, 0, tzinfo=UTC)
UPDATED = datetime(2026, 11, 13, 14, 0, tzinfo=UTC)
THURSDAY_5PM = Deadline(datetime(2026, 11, 12, 22, 0, tzinfo=UTC), NY, True)
FRIDAY_5PM = Deadline(datetime(2026, 11, 20, 22, 0, tzinfo=UTC), NY, False)


def task(**fields: object) -> Task:
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
    return Task(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        ({}, "t3    open                  Pay rent"),
        (
            {"deadline": THURSDAY_5PM},
            "t3    open, overdue         Pay rent  due Thu Nov 12 17:00 EST",
        ),
        (
            {"id": "t2", "title": "Book flights", "state": "in_progress", "deadline": FRIDAY_5PM},
            "t2    in progress           Book flights  due Fri Nov 20 17:00 EST, no time given",
        ),
        (
            {"state": "done", "deadline": THURSDAY_5PM},
            "t3    done                  Pay rent  due Thu Nov 12 17:00 EST",
        ),
        (
            {"id": "t12345", "state": "in_progress", "deadline": THURSDAY_5PM},
            "t12345 in progress, overdue  Pay rent  due Thu Nov 12 17:00 EST",
        ),
        ({"id": "t1234567", "title": "Long id"}, "t1234567 open                  Long id"),
    ],
    ids=["undated", "overdue", "no-time-given", "done", "long-id", "longer-id"],
)
def test_a_task_line(fields: dict[str, object], expected: str) -> None:
    assert task_line(task(**fields), NY, NOW) == expected


def test_the_detail_of_an_owner_task() -> None:
    assert task_detail(task(deadline=THURSDAY_5PM), NY, NOW) == [
        "t3  Pay rent",
        "State: open, overdue",
        "Due: Thu Nov 12 17:00 EST",
        "Work: none",
        "Source: owner",
        "Created: Fri Nov 13 08:00 EST",
        "Updated: Fri Nov 13 09:00 EST",
    ]


def test_the_detail_of_an_email_task_with_a_work_time() -> None:
    found = task(
        title="Book flights",
        deadline=FRIDAY_5PM,
        work=WorkTime(datetime(2026, 11, 20, 5, 0, tzinfo=UTC), 60, "Asia/Tokyo"),
        source="email",
        provider="gmail",
        message_id="personal/18c2f0a1",
        link="https://mail.example/18c2f0a1",
    )
    assert task_detail(found, NY, NOW) == [
        "t3  Book flights",
        "State: open",
        "Due: Fri Nov 20 17:00 EST, no time given",
        "Work: Fri Nov 20 00:00 to 01:00 EST (Fri Nov 20 14:00 to 15:00 JST where set)",
        "Source: email, gmail personal/18c2f0a1",
        "Link: https://mail.example/18c2f0a1",
        "Created: Fri Nov 13 08:00 EST",
        "Updated: Fri Nov 13 09:00 EST",
    ]


@pytest.mark.parametrize(
    ("source", "expected"),
    [("agent", "Source: agent"), ("proposal", "Source: proposal")],
    ids=["agent", "proposal"],
)
def test_the_source_line(source: str, expected: str) -> None:
    assert task_detail(task(source=source), NY, NOW)[4] == expected
    assert len(task_detail(task(source=source), NY, NOW)) == 7


@pytest.mark.parametrize(
    ("code", "task_id", "expected"),
    [
        ("unknown_task", "t9", "There is no task t9."),
        ("unknown_task", None, "There is no such task."),
        (
            "invalid_title",
            None,
            "A title is 1 to 100 characters on one line, with no space at either end.",
        ),
        ("invalid_source", None, "That source is not allowed."),
        ("invalid_reference", None, "That email reference is not complete."),
        ("invalid_actor", None, "That actor is not allowed."),
        ("invalid_action", None, "That is not a state change."),
        ("task_ended", "t4", "Task t4 has ended; reopen it first."),
        ("task_ended", None, "That task has ended; reopen it first."),
        ("work_after_deadline", "t4", "The work time must end by the deadline."),
    ],
    ids=[
        "unknown",
        "unknown-without-id",
        "title",
        "source",
        "reference",
        "actor",
        "action",
        "ended",
        "ended-without-id",
        "work-after-deadline",
    ],
)
def test_every_refusal_reads_as_a_sentence(code: str, task_id: str | None, expected: str) -> None:
    assert refusal_text(code, task_id) == expected
