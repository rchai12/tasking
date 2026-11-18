from datetime import UTC, datetime

import pytest

from docket import core
from docket.core import (
    INVALID_ACTION,
    INVALID_ACTOR,
    INVALID_REFERENCE,
    INVALID_SOURCE,
    INVALID_TITLE,
    TASK_ENDED,
    UNKNOWN_TASK,
    WORK_AFTER_DEADLINE,
    CoreError,
    Outcome,
    change_state,
    check_title,
    create_task,
    edit_task,
)
from docket.deadlines import Deadline, WorkTime
from docket.store import UNCHANGED, AuditEntry, Store, Task
from tests.support import fixed_times
from tests.support import path as path
from tests.support import refused as refused
from tests.support import store as store

NY = "America/New_York"
NOW = "2026-11-14T09:00:00+00:00"
LATER = "2026-11-14T09:30:00+00:00"
AT_NOW = datetime(2026, 11, 14, 9, 0, tzinfo=UTC)
AT_LATER = datetime(2026, 11, 14, 9, 30, tzinfo=UTC)
FRIDAY_5PM = Deadline(datetime(2026, 11, 20, 22, 0, tzinfo=UTC), NY, False)
FRIDAY_2PM = Deadline(datetime(2026, 11, 20, 19, 0, tzinfo=UTC), NY, True)
FRIDAY_WORK = WorkTime(datetime(2026, 11, 20, 19, 0, tzinfo=UTC), 60, NY)
LATE_WORK = WorkTime(datetime(2026, 11, 20, 21, 30, tzinfo=UTC), 60, NY)
EARLY_WORK = WorkTime(datetime(2026, 11, 20, 17, 0, tzinfo=UTC), 60, NY)
DEADLINE_TEXT = {"at": "2026-11-20T22:00:00.000000+00:00", "zone": NY, "time_given": False}
WORK_TEXT = {"start": "2026-11-20T19:00:00.000000+00:00", "minutes": 60, "zone": NY}
GMAIL = {"provider": "gmail", "message_id": "personal/18c2f0a1", "link": "https://mail.example/1"}


def seed(store: Store, state: str = "open", **fields: object) -> Task:
    """A task put straight into the store, as a state a person reaches; no clock read."""
    values: dict[str, object] = {
        "title": "Pay rent",
        "state": state,
        "deadline": None,
        "work": None,
        "source": "owner",
        "provider": None,
        "message_id": None,
        "link": None,
        "at": datetime(2026, 11, 13, 8, 0, tzinfo=UTC),
    }
    values.update(fields)
    with store.transaction():
        return store.insert_task(**values)  # type: ignore[arg-type]


def test_the_codes() -> None:
    assert (
        UNKNOWN_TASK,
        INVALID_TITLE,
        INVALID_SOURCE,
        INVALID_REFERENCE,
        INVALID_ACTOR,
        INVALID_ACTION,
        TASK_ENDED,
        WORK_AFTER_DEADLINE,
    ) == (
        "unknown_task",
        "invalid_title",
        "invalid_source",
        "invalid_reference",
        "invalid_actor",
        "invalid_action",
        "task_ended",
        "work_after_deadline",
    )
    assert issubclass(CoreError, Exception)


@pytest.mark.parametrize(
    "title",
    ["Pay rent", "x" * 100, "Café ☕ receipt", "Two  spaces", "No break inside", "t1"],
    ids=[
        "plain",
        "longest",
        "accents-and-emoji",
        "inner-double-space",
        "inner-no-break",
        "id-like",
    ],
)
def test_a_valid_title(title: str) -> None:
    assert check_title(title) is None


@pytest.mark.parametrize(
    "title",
    [
        "",
        " Pay rent",
        "Pay rent ",
        " Pay rent",
        "Pay rent\n",
        "Pay\trent",
        "Pay\nrent",
        "Pay​rent",
        "Pay﻿rent",
        "Pay rent",
        "Pay rent",
        "Pay\x00rent",
        "x" * 101,
        5,
        None,
    ],
    ids=[
        "empty",
        "leading-space",
        "trailing-space",
        "leading-no-break",
        "trailing-newline",
        "tab",
        "newline",
        "zero-width-space",
        "byte-order-mark",
        "line-separator",
        "paragraph-separator",
        "nul",
        "too-long",
        "number",
        "none",
    ],
)
def test_an_invalid_title_is_refused_never_rewritten(title: object) -> None:
    refused(INVALID_TITLE, lambda: check_title(title))


def test_creating_a_task_writes_it_and_one_audit_row(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_times(monkeypatch, NOW)
    made = create_task(store, title="Pay rent", source="owner")
    assert made == Task(
        id="t1",
        title="Pay rent",
        state="open",
        deadline=None,
        work=None,
        source="owner",
        provider=None,
        message_id=None,
        link=None,
        created_at=AT_NOW,
        updated_at=AT_NOW,
    )
    assert store.task("t1") == made
    assert store.audit("t1") == [
        AuditEntry(
            task_id="t1",
            at=AT_NOW,
            action="create",
            actor="owner",
            before={},
            after={
                "title": "Pay rent",
                "state": "open",
                "deadline": None,
                "work": None,
                "source": "owner",
                "provider": None,
                "message_id": None,
                "link": None,
            },
        )
    ]


def test_a_new_task_records_its_deadline_and_work_time(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_times(monkeypatch, NOW)
    made = create_task(
        store, title="Pay rent", source="agent", deadline=FRIDAY_5PM, work=FRIDAY_WORK
    )
    assert (made.deadline, made.work, made.source) == (FRIDAY_5PM, FRIDAY_WORK, "agent")
    (entry,) = store.audit(made.id)
    assert (entry.actor, entry.after["deadline"], entry.after["work"]) == (
        "agent",
        DEADLINE_TEXT,
        WORK_TEXT,
    )


@pytest.mark.parametrize(
    ("source", "reference", "actor"),
    [
        ("email", GMAIL, "email"),
        ("agent", {}, "agent"),
        ("proposal", {}, "owner"),
        ("owner", {}, "owner"),
    ],
    ids=["email", "agent", "proposal", "owner"],
)
def test_the_audit_actor_follows_the_source(
    store: Store,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    reference: dict[str, str],
    actor: str,
) -> None:
    fixed_times(monkeypatch, NOW)
    made = create_task(store, title="Pay rent", source=source, **reference)
    (entry,) = store.audit(made.id)
    assert entry.actor == actor
    assert (made.provider, made.message_id, made.link) == (
        reference.get("provider"),
        reference.get("message_id"),
        reference.get("link"),
    )
    assert (entry.after["provider"], entry.after["source"]) == (reference.get("provider"), source)


@pytest.mark.parametrize(
    ("fields", "code"),
    [
        ({"title": " Pay rent", "source": "owner"}, INVALID_TITLE),
        ({"title": "Pay rent", "source": "camera"}, INVALID_SOURCE),
        ({"title": "Pay rent", "source": "email"}, INVALID_REFERENCE),
        (
            {"title": "Pay rent", "source": "email", **GMAIL, "link": ""},
            INVALID_REFERENCE,
        ),
        (
            {"title": "Pay rent", "source": "email", **GMAIL, "provider": "aol"},
            INVALID_REFERENCE,
        ),
        ({"title": "Pay rent", "source": "owner", **GMAIL}, INVALID_REFERENCE),
        ({"title": "Pay rent", "source": "agent", "message_id": "personal/1"}, INVALID_REFERENCE),
        (
            {"title": "Pay rent", "source": "owner", "deadline": FRIDAY_2PM, "work": LATE_WORK},
            WORK_AFTER_DEADLINE,
        ),
        ({"title": " Pay rent", "source": "camera"}, INVALID_TITLE),
        ({"title": "Pay rent", "source": "camera", **GMAIL}, INVALID_SOURCE),
    ],
    ids=[
        "title",
        "source",
        "email-without-reference",
        "empty-link",
        "unknown-provider",
        "reference-on-owner",
        "part-reference-on-agent",
        "work-after-deadline",
        "title-before-source",
        "source-before-reference",
    ],
)
def test_a_refused_task_is_never_written(
    store: Store, monkeypatch: pytest.MonkeyPatch, fields: dict[str, object], code: str
) -> None:
    fixed_times(monkeypatch)
    refused(code, lambda: create_task(store, **fields))  # type: ignore[arg-type]
    assert store.tasks() == []


def test_work_ending_at_the_deadline_and_past_dates_are_allowed(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_times(monkeypatch, "2026-11-25T09:00:00+00:00", "2026-11-25T09:00:00+00:00")
    ending = WorkTime(datetime(2026, 11, 20, 21, 0, tzinfo=UTC), 60, NY)
    first = create_task(store, title="Pay rent", source="owner", deadline=FRIDAY_5PM, work=ending)
    second = create_task(store, title="Book flights", source="email", deadline=FRIDAY_5PM, **GMAIL)
    assert [task.id for task in store.tasks()] == [first.id, second.id]
    assert first.work == ending


@pytest.mark.parametrize(
    ("state", "action", "expected"),
    [
        ("open", "start", ("in_progress", True)),
        ("open", "done", ("done", True)),
        ("open", "cancel", ("cancelled", True)),
        ("open", "reopen", ("open", False)),
        ("in_progress", "start", ("in_progress", False)),
        ("in_progress", "done", ("done", True)),
        ("in_progress", "cancel", ("cancelled", True)),
        ("in_progress", "reopen", ("in_progress", False)),
        ("done", "start", TASK_ENDED),
        ("done", "done", ("done", False)),
        ("done", "cancel", TASK_ENDED),
        ("done", "reopen", ("open", True)),
        ("cancelled", "start", TASK_ENDED),
        ("cancelled", "done", TASK_ENDED),
        ("cancelled", "cancel", ("cancelled", False)),
        ("cancelled", "reopen", ("open", True)),
    ],
    ids=[
        "open-start",
        "open-done",
        "open-cancel",
        "open-reopen",
        "in-progress-start",
        "in-progress-done",
        "in-progress-cancel",
        "in-progress-reopen",
        "done-start",
        "done-done",
        "done-cancel",
        "done-reopen",
        "cancelled-start",
        "cancelled-done",
        "cancelled-cancel",
        "cancelled-reopen",
    ],
)
def test_every_state_change(
    store: Store, monkeypatch: pytest.MonkeyPatch, state: str, action: str, expected: object
) -> None:
    before = seed(store, state)
    fixed_times(monkeypatch, NOW)
    if isinstance(expected, str):
        refused(expected, lambda: change_state(store, before.id, action, actor="owner"))
        assert store.task(before.id) == before
        assert store.audit(before.id) == []
        return
    new_state, changed = expected
    outcome = change_state(store, before.id, action, actor="owner")
    assert (outcome.task.state, outcome.changed) == (new_state, changed)
    assert store.task(before.id) == outcome.task
    if changed:
        assert outcome.task.updated_at == AT_NOW
        assert store.audit(before.id) == [
            AuditEntry(
                task_id=before.id,
                at=AT_NOW,
                action=action,
                actor="owner",
                before={"state": state},
                after={"state": new_state},
            )
        ]
    else:
        assert outcome.task == before
        assert store.audit(before.id) == []


def test_pressing_done_twice_changes_nothing_the_second_time(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    made = seed(store)
    fixed_times(monkeypatch, NOW, LATER)
    first = change_state(store, made.id, "done", actor="owner")
    second = change_state(store, made.id, "done", actor="agent")
    assert (first.changed, second.changed) == (True, False)
    assert second == Outcome(task=first.task, changed=False)
    assert [entry.actor for entry in store.audit(made.id)] == ["owner"]


def test_reopening_keeps_the_deadline_and_work_time(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    made = seed(store, "done", deadline=FRIDAY_5PM, work=FRIDAY_WORK)
    fixed_times(monkeypatch, NOW)
    outcome = change_state(store, made.id, "reopen", actor="agent")
    assert (outcome.task.state, outcome.task.deadline, outcome.task.work) == (
        "open",
        FRIDAY_5PM,
        FRIDAY_WORK,
    )
    assert store.audit(made.id)[0].actor == "agent"


@pytest.mark.parametrize(
    ("action", "actor", "code"),
    [
        ("finish", "owner", INVALID_ACTION),
        ("create", "owner", INVALID_ACTION),
        ("retitle", "owner", INVALID_ACTION),
        ("done", "system", INVALID_ACTOR),
        ("done", "proposal", INVALID_ACTOR),
        ("finish", "system", INVALID_ACTION),
    ],
    ids=["unknown", "create", "an-edit", "system", "proposal", "action-before-actor"],
)
def test_a_bad_action_or_actor_is_refused_before_anything(
    store: Store, monkeypatch: pytest.MonkeyPatch, action: str, actor: str, code: str
) -> None:
    made = seed(store)
    fixed_times(monkeypatch)
    refused(code, lambda: change_state(store, made.id, action, actor=actor))
    assert store.task(made.id) == made


@pytest.mark.parametrize("task_id", ["t9", "x1", ""], ids=["missing", "malformed", "empty"])
def test_an_unknown_task_is_refused(
    store: Store, monkeypatch: pytest.MonkeyPatch, task_id: str
) -> None:
    seed(store)
    fixed_times(monkeypatch, NOW, NOW)
    refused(UNKNOWN_TASK, lambda: change_state(store, task_id, "done", actor="owner"))
    refused(UNKNOWN_TASK, lambda: edit_task(store, task_id, actor="owner", title="New"))


def test_an_edit_writes_one_row_per_field_in_a_fixed_order(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    made = seed(store, "in_progress")
    fixed_times(monkeypatch, NOW)
    outcome = edit_task(
        store,
        made.id,
        actor="agent",
        work=FRIDAY_WORK,
        title="Pay rent today",
        deadline=FRIDAY_5PM,
    )
    assert outcome.changed is True
    assert outcome.task == Task(
        id="t1",
        title="Pay rent today",
        state="in_progress",
        deadline=FRIDAY_5PM,
        work=FRIDAY_WORK,
        source="owner",
        provider=None,
        message_id=None,
        link=None,
        created_at=datetime(2026, 11, 13, 8, 0, tzinfo=UTC),
        updated_at=AT_NOW,
    )
    assert store.audit(made.id) == [
        AuditEntry(
            "t1", AT_NOW, "retitle", "agent", {"title": "Pay rent"}, {"title": "Pay rent today"}
        ),
        AuditEntry(
            "t1", AT_NOW, "deadline", "agent", {"deadline": None}, {"deadline": DEADLINE_TEXT}
        ),
        AuditEntry("t1", AT_NOW, "work_time", "agent", {"work": None}, {"work": WORK_TEXT}),
    ]


def test_an_edit_can_clear_and_only_changed_fields_are_recorded(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    made = seed(store, deadline=FRIDAY_5PM, work=FRIDAY_WORK)
    fixed_times(monkeypatch, NOW)
    outcome = edit_task(
        store, made.id, actor="owner", title="Pay rent", deadline=FRIDAY_5PM, work=None
    )
    assert (outcome.changed, outcome.task.work, outcome.task.deadline) == (True, None, FRIDAY_5PM)
    assert store.audit(made.id) == [
        AuditEntry("t1", AT_NOW, "work_time", "owner", {"work": WORK_TEXT}, {"work": None})
    ]


@pytest.mark.parametrize(
    "fields",
    [{}, {"title": "Pay rent"}, {"deadline": None, "work": None}, {"title": UNCHANGED}],
    ids=["nothing", "same-title", "already-clear", "unchanged-sentinel"],
)
def test_an_edit_that_changes_nothing_writes_nothing(
    store: Store, monkeypatch: pytest.MonkeyPatch, fields: dict[str, object]
) -> None:
    made = seed(store)
    fixed_times(monkeypatch, NOW)
    outcome = edit_task(store, made.id, actor="owner", **fields)  # type: ignore[arg-type]
    assert outcome == Outcome(task=made, changed=False)
    assert store.task(made.id) == made
    assert store.audit(made.id) == []


@pytest.mark.parametrize(
    ("start", "fields"),
    [
        ({"deadline": FRIDAY_5PM, "work": FRIDAY_WORK}, {"deadline": FRIDAY_2PM}),
        ({"deadline": FRIDAY_2PM}, {"work": LATE_WORK}),
        ({}, {"deadline": FRIDAY_2PM, "work": LATE_WORK}),
    ],
    ids=["earlier-deadline", "later-work", "both-at-once"],
)
def test_an_edit_that_puts_work_past_the_deadline_is_refused(
    store: Store,
    monkeypatch: pytest.MonkeyPatch,
    start: dict[str, object],
    fields: dict[str, object],
) -> None:
    made = seed(store, **start)
    fixed_times(monkeypatch, NOW)
    refused(WORK_AFTER_DEADLINE, lambda: edit_task(store, made.id, actor="owner", **fields))
    assert store.task(made.id) == made
    assert store.audit(made.id) == []


def test_moving_both_together_is_allowed(store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    made = seed(store, deadline=FRIDAY_2PM, work=EARLY_WORK)
    fixed_times(monkeypatch, NOW)
    outcome = edit_task(store, made.id, actor="owner", deadline=FRIDAY_5PM, work=FRIDAY_WORK)
    assert (outcome.task.deadline, outcome.task.work) == (FRIDAY_5PM, FRIDAY_WORK)
    assert [entry.action for entry in store.audit(made.id)] == ["deadline", "work_time"]


@pytest.mark.parametrize("state", ["done", "cancelled"])
@pytest.mark.parametrize(
    "fields",
    [{"title": "Pay rent today"}, {"deadline": FRIDAY_5PM}, {"work": None}, {}],
    ids=["title", "deadline", "clear-work", "nothing"],
)
def test_an_ended_task_must_be_reopened_before_an_edit(
    store: Store, monkeypatch: pytest.MonkeyPatch, state: str, fields: dict[str, object]
) -> None:
    made = seed(store, state)
    fixed_times(monkeypatch, NOW)
    refused(TASK_ENDED, lambda: edit_task(store, made.id, actor="owner", **fields))
    assert store.task(made.id) == made


@pytest.mark.parametrize(
    ("fields", "code"),
    [
        ({"actor": "owner", "title": "Pay rent "}, INVALID_TITLE),
        ({"actor": "system", "title": "New"}, INVALID_ACTOR),
        ({"actor": "system", "title": "Pay rent "}, INVALID_ACTOR),
    ],
    ids=["title", "actor", "actor-before-title"],
)
def test_a_bad_edit_is_refused_before_anything(
    store: Store, monkeypatch: pytest.MonkeyPatch, fields: dict[str, object], code: str
) -> None:
    made = seed(store)
    fixed_times(monkeypatch)
    refused(code, lambda: edit_task(store, made.id, **fields))  # type: ignore[arg-type]
    assert store.task(made.id) == made


def test_a_change_and_its_audit_row_commit_together(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    made = seed(store)
    fixed_times(monkeypatch, NOW, NOW, NOW)

    class DiskFull(Exception):
        pass

    calls: list[str] = []

    def broken(*args: object, **kwargs: object) -> None:
        calls.append(str(kwargs["action"]))
        raise DiskFull

    monkeypatch.setattr(store, "append_audit", broken)
    for call in (
        lambda: create_task(store, title="Book flights", source="owner"),
        lambda: change_state(store, made.id, "done", actor="owner"),
        lambda: edit_task(store, made.id, actor="owner", title="Pay rent today"),
    ):
        with pytest.raises(DiskFull):
            call()
    assert calls == ["create", "done", "retitle"]
    assert store.tasks() == [made]


def test_the_core_reads_the_clock_once_per_write(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_times(monkeypatch, NOW, LATER, LATER)
    made = create_task(store, title="Pay rent", source="owner")
    change_state(store, made.id, "start", actor="owner")
    edit_task(store, made.id, actor="owner", deadline=FRIDAY_5PM)
    assert [entry.at for entry in store.audit(made.id)] == [AT_NOW, AT_LATER, AT_LATER]
    assert core.clock.now is not None
