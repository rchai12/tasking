from datetime import UTC, datetime

import pytest

from docket.core import Outcome
from docket.store import Task
from docket.views import change_text

AT = datetime(2026, 11, 13, 13, 0, tzinfo=UTC)


def outcome(state: str, changed: bool, task_id: str = "t3") -> Outcome:
    task = Task(task_id, "Pay rent", state, None, None, "owner", None, None, None, AT, AT)
    return Outcome(task=task, changed=changed)


@pytest.mark.parametrize(
    ("action", "state", "changed", "expected"),
    [
        ("start", "in_progress", True, "Started t3: Pay rent"),
        ("done", "done", True, "Done t3: Pay rent"),
        ("cancel", "cancelled", True, "Cancelled t3: Pay rent"),
        ("reopen", "open", True, "Reopened t3: Pay rent"),
        ("start", "in_progress", False, "t3 is already in progress."),
        ("done", "done", False, "t3 is already done."),
        ("cancel", "cancelled", False, "t3 is already cancelled."),
        ("reopen", "open", False, "t3 is already open."),
        ("reopen", "in_progress", False, "t3 is already in progress."),
    ],
    ids=[
        "started",
        "done",
        "cancelled",
        "reopened",
        "already-started",
        "already-done",
        "already-cancelled",
        "already-open",
        "reopen-while-in-progress",
    ],
)
def test_a_change_reads_as_a_sentence(
    action: str, state: str, changed: bool, expected: str
) -> None:
    assert change_text(action, outcome(state, changed)) == expected


def test_the_id_and_title_come_from_the_task() -> None:
    task = Task("t1234", "Book flights", "done", None, None, "agent", None, None, None, AT, AT)
    assert change_text("done", Outcome(task=task, changed=True)) == "Done t1234: Book flights"
    assert change_text("done", Outcome(task=task, changed=False)) == "t1234 is already done."
