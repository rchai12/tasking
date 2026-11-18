"""Literal scheduling examples and synthetic task inputs for Phase 3a."""

import json
from datetime import datetime
from pathlib import Path

from docket.deadlines import Deadline, WorkTime
from docket.store import Task

CASES = json.loads((Path(__file__).with_name("reminder_plan_cases.json")).read_text())


def task_for(case: dict) -> Task:
    deadline = case["deadline"]
    work = case["work"]
    return Task(
        id="t1",
        title="Synthetic task",
        state=case["state"],
        deadline=Deadline(datetime.fromisoformat(deadline), case["zone"], case["time_given"])
        if deadline
        else None,
        work=WorkTime(datetime.fromisoformat(work), 5, case["work_zone"]) if work else None,
        source="owner",
        provider=None,
        message_id=None,
        link=None,
        created_at=datetime.fromisoformat("2026-10-01T00:00:00+00:00"),
        updated_at=datetime.fromisoformat("2026-10-01T00:00:00+00:00"),
    )


def projection(rows: tuple) -> list[list[str]]:
    return [[row.kind, row.fire_at.isoformat()] for row in rows]
