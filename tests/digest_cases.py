"""Synthetic tasks and instants for the Phase 3d daily digest tests."""

from datetime import UTC, date, datetime, time, timedelta

from docket.deadlines import Deadline
from docket.store import Store

ZONE = "America/New_York"
AT = time(7, 0)
DAY = date(2026, 11, 20)
SLOT = datetime(2026, 11, 20, 12, tzinfo=UTC)
CREATED = datetime(2026, 11, 16, 12, tzinfo=UTC)

TASKS = (
    (
        "Synthetic invoice",
        "open",
        Deadline(datetime(2026, 11, 18, 14, tzinfo=UTC), "Asia/Tokyo", True),
    ),
    ("Synthetic report", "open", Deadline(datetime(2026, 11, 17, 22, tzinfo=UTC), ZONE, True)),
    ("Synthetic boundary", "open", Deadline(datetime(2026, 11, 20, 0, tzinfo=UTC), ZONE, True)),
    (
        "Synthetic not yet",
        "open",
        Deadline(datetime(2026, 11, 20, 0, 0, 0, 1, tzinfo=UTC), "UTC", True),
    ),
    ("Synthetic finished", "done", Deadline(datetime(2026, 11, 17, 22, tzinfo=UTC), ZONE, True)),
    ("Synthetic undated", "open", None),
    ("Synthetic tie", "in_progress", Deadline(datetime(2026, 11, 17, 22, tzinfo=UTC), ZONE, True)),
    (
        "Synthetic dropped",
        "cancelled",
        Deadline(datetime(2026, 11, 17, 22, tzinfo=UTC), ZONE, True),
    ),
    ("Synthetic future", "open", Deadline(datetime(2026, 11, 25, 22, tzinfo=UTC), ZONE, True)),
)
"""t1 to t9. At SLOT, t2, t7, t1 and t3 are past their last late reminder, in deadline order."""


def iso(moment: datetime) -> str:
    return moment.isoformat()


def later(minutes: float) -> str:
    """The ISO instant `minutes` after SLOT, for fixed_times."""
    return iso(SLOT + timedelta(minutes=minutes))


def seed(opened: Store, tasks=TASKS) -> None:
    """Insert `tasks` directly, so no clock is read and no reminder is planned."""
    with opened.transaction():
        for title, state, deadline in tasks:
            opened.insert_task(
                title=title,
                state=state,
                deadline=deadline,
                work=None,
                source="owner",
                provider=None,
                message_id=None,
                link=None,
                at=CREATED,
            )
