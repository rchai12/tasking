from datetime import UTC, datetime

import pytest

from docket import core
from docket.core import (
    INVALID_CLIENT,
    INVALID_KEY,
    INVALID_REFERENCE,
    INVALID_SOURCE,
    INVALID_TITLE,
    KEY_REUSED,
    UNKNOWN_TASK,
    WORK_AFTER_DEADLINE,
    LinkOutcome,
    Outcome,
    add_link,
    create_task_once,
)
from docket.deadlines import Deadline, WorkTime
from docket.store import Link, Store, Task
from tests.support import fixed_times
from tests.support import path as path
from tests.support import refused as refused
from tests.support import store as store

NY = "America/New_York"
NOW = "2026-11-14T14:00:00+00:00"
LATER = "2026-11-14T14:30:00+00:00"
AT_NOW = datetime(2026, 11, 14, 14, 0, tzinfo=UTC)
AT_LATER = datetime(2026, 11, 14, 14, 30, tzinfo=UTC)
FRIDAY_5PM = Deadline(datetime(2026, 11, 20, 22, 0, tzinfo=UTC), NY, True)
LATE_WORK = WorkTime(datetime(2026, 11, 20, 21, 30, tzinfo=UTC), 60, NY)
GMAIL = {"provider": "gmail", "message_id": "personal/1", "link": "https://mail.example/1"}
FOLLOW = {"provider": "gmail", "message_id": "personal/2", "link": "https://mail.example/2"}
REQUEST = {"source": "email", "title": "Pay rent", "deadline": None, **GMAIL}


def from_email(store: Store, key: str = "gmail:personal/1", **fields: object) -> Outcome:
    values: dict[str, object] = {
        "client": "email",
        "key": key,
        "request": REQUEST,
        "title": "Pay rent",
        "source": "email",
        **GMAIL,
    }
    values.update(fields)
    return create_task_once(store, **values)  # type: ignore[arg-type]


def link_to(store: Store, task_id: str = "t1", key: str = "gmail:personal/2", **fields: object):
    values: dict[str, object] = {"client": "email", "key": key, "request": FOLLOW, **FOLLOW}
    values.update(fields)
    return add_link(store, task_id, **values)  # type: ignore[arg-type]


def test_the_new_codes() -> None:
    assert (INVALID_CLIENT, INVALID_KEY, KEY_REUSED) == (
        "invalid_client",
        "invalid_key",
        "key_reused",
    )


def test_a_keyed_task_is_created_once_and_its_key_recorded(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_times(monkeypatch, NOW)
    outcome = from_email(store, deadline=FRIDAY_5PM)
    task = Task(
        id="t1",
        title="Pay rent",
        state="open",
        deadline=FRIDAY_5PM,
        work=None,
        source="email",
        provider="gmail",
        message_id="personal/1",
        link="https://mail.example/1",
        created_at=AT_NOW,
        updated_at=AT_NOW,
    )
    assert outcome == Outcome(task=task, changed=True)
    assert [(entry.action, entry.actor) for entry in store.audit("t1")] == [("create", "email")]
    key = store.request_key("email", "gmail:personal/1")
    assert key is not None
    assert (key.request, key.task_id, key.link_id, key.created_at) == (REQUEST, "t1", None, AT_NOW)


def test_the_same_key_and_request_answer_with_the_task_again(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_times(monkeypatch, NOW, LATER)
    first = from_email(store)
    again = from_email(store)
    assert again == Outcome(task=first.task, changed=False)
    assert [task.id for task in store.tasks()] == ["t1"]
    assert len(store.audit("t1")) == 1


def test_a_repeat_answers_with_the_task_as_it_is_now(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_times(monkeypatch, NOW, LATER, LATER)
    from_email(store)
    core.edit_task(store, "t1", actor="owner", title="Pay rent today")
    again = from_email(store)
    assert (again.changed, again.task.title, again.task.updated_at) == (
        False,
        "Pay rent today",
        AT_LATER,
    )


def test_the_request_is_compared_as_data_not_as_text(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_times(monkeypatch, NOW, LATER)
    from_email(store)
    shuffled = dict(reversed(list(REQUEST.items())))
    assert from_email(store, request=shuffled).changed is False


@pytest.mark.parametrize(
    "request_",
    [
        {**REQUEST, "title": "Pay rent!"},
        {**REQUEST, "deadline": {"date": "2026-11-20", "time": None, "time_zone": NY}},
        {key: value for key, value in REQUEST.items() if key != "link"},
    ],
    ids=["other-title", "other-deadline", "missing-field"],
)
def test_a_key_reused_with_another_request_is_refused(
    store: Store, monkeypatch: pytest.MonkeyPatch, request_: dict[str, object]
) -> None:
    fixed_times(monkeypatch, NOW, LATER)
    from_email(store)
    refused(KEY_REUSED, lambda: from_email(store, request=request_, title="Pay rent!"))
    assert [task.title for task in store.tasks()] == ["Pay rent"]


def test_the_same_key_from_another_client_is_another_request(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_times(monkeypatch, NOW, LATER)
    from_email(store, key="shared")
    agent = create_task_once(
        store,
        client="agent",
        key="shared",
        request={"title": "Pay rent"},
        title="Pay rent",
        source="agent",
    )
    assert (agent.changed, agent.task.id, agent.task.source) == (True, "t2", "agent")
    assert [(entry.action, entry.actor) for entry in store.audit("t2")] == [("create", "agent")]


@pytest.mark.parametrize(
    ("fields", "code"),
    [
        ({"client": "owner"}, INVALID_CLIENT),
        ({"client": "camera"}, INVALID_CLIENT),
        ({"key": ""}, INVALID_KEY),
        ({"key": "k" * 201}, INVALID_KEY),
        ({"key": 7}, INVALID_KEY),
        ({"source": "agent", "provider": None, "message_id": None, "link": None}, INVALID_SOURCE),
        ({"title": " Pay rent"}, INVALID_TITLE),
        ({"link": ""}, INVALID_REFERENCE),
        (
            {
                "deadline": Deadline(datetime(2026, 11, 20, 19, 0, tzinfo=UTC), NY, True),
                "work": LATE_WORK,
            },
            WORK_AFTER_DEADLINE,
        ),
        ({"client": "camera", "key": ""}, INVALID_CLIENT),
        ({"key": "", "title": " Pay rent"}, INVALID_KEY),
        ({"source": "agent", "title": " Pay rent"}, INVALID_TITLE),
    ],
    ids=[
        "owner-is-not-a-client",
        "unknown-client",
        "empty-key",
        "long-key",
        "key-not-text",
        "source-not-the-client",
        "title",
        "reference",
        "work-after-deadline",
        "client-before-key",
        "key-before-title",
        "title-before-source",
    ],
)
def test_a_refused_keyed_create_writes_nothing(
    store: Store, monkeypatch: pytest.MonkeyPatch, fields: dict[str, object], code: str
) -> None:
    fixed_times(monkeypatch)
    refused(code, lambda: from_email(store, **fields))
    assert store.tasks() == []
    assert store.request_key("email", "gmail:personal/1") is None


def test_a_follow_up_link_is_added_once(store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    fixed_times(monkeypatch, NOW, LATER, LATER)
    from_email(store)
    first = link_to(store)
    again = link_to(store)
    link = Link(
        id="l1",
        task_id="t1",
        provider="gmail",
        message_id="personal/2",
        link="https://mail.example/2",
        created_at=AT_LATER,
    )
    assert (first, again) == (
        LinkOutcome(link=link, changed=True),
        LinkOutcome(link=link, changed=False),
    )
    assert store.links("t1") == [link]
    key = store.request_key("email", "gmail:personal/2")
    assert key is not None and (key.task_id, key.link_id, key.request) == ("t1", "l1", FOLLOW)
    assert len(store.audit("t1")) == 1


def test_a_link_may_follow_an_ended_task(store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    fixed_times(monkeypatch, NOW, NOW, LATER)
    from_email(store)
    core.change_state(store, "t1", "done", actor="owner")
    assert link_to(store).changed is True
    found = store.task("t1")
    assert found is not None and found.state == "done"


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ({}, {"task_id": "t2"}),
        ({}, {"request": {**FOLLOW, "link": "https://mail.example/3"}}),
        ({}, {"key": "gmail:personal/1"}),
        ({}, {"task_id": "t99"}),
    ],
    ids=["another-task", "another-request", "a-task-key", "key-before-unknown-task"],
)
def test_a_link_key_reused_differently_is_refused(
    store: Store,
    monkeypatch: pytest.MonkeyPatch,
    first: dict[str, object],
    second: dict[str, object],
) -> None:
    fixed_times(monkeypatch, NOW, NOW, LATER, LATER)
    from_email(store)
    from_email(
        store,
        key="gmail:personal/9",
        request={**REQUEST, "title": "Book flights"},
        title="Book flights",
    )
    link_to(store, **first)
    refused(KEY_REUSED, lambda: link_to(store, **second))
    assert store.links("t2") == []
    assert [link.message_id for link in store.links("t1")] == ["personal/2"]


def test_a_task_key_used_by_a_link_is_refused(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_times(monkeypatch, NOW, LATER, LATER)
    from_email(store)
    link_to(store)
    refused(KEY_REUSED, lambda: from_email(store, key="gmail:personal/2", request=FOLLOW))
    assert [task.id for task in store.tasks()] == ["t1"]


@pytest.mark.parametrize(
    ("task_id", "fields", "code", "reads"),
    [
        ("t9", {}, UNKNOWN_TASK, 1),
        ("x", {}, UNKNOWN_TASK, 1),
        ("t1", {"client": "agent"}, INVALID_CLIENT, 0),
        ("t1", {"client": "owner"}, INVALID_CLIENT, 0),
        ("t1", {"key": ""}, INVALID_KEY, 0),
        ("t1", {"provider": "aol"}, INVALID_REFERENCE, 0),
        ("t1", {"link": ""}, INVALID_REFERENCE, 0),
        ("t1", {"client": "agent", "key": ""}, INVALID_CLIENT, 0),
        ("t9", {"key": ""}, INVALID_KEY, 0),
    ],
    ids=[
        "unknown-task",
        "malformed-id",
        "agent",
        "owner",
        "empty-key",
        "provider",
        "empty-link",
        "client-before-key",
        "key-before-the-task",
    ],
)
def test_a_refused_link_writes_nothing(
    store: Store,
    monkeypatch: pytest.MonkeyPatch,
    task_id: str,
    fields: dict[str, object],
    code: str,
    reads: int,
) -> None:
    fixed_times(monkeypatch, NOW, *([LATER] * reads))
    from_email(store)
    refused(code, lambda: link_to(store, task_id, **fields))
    assert store.links("t1") == []
    assert store.request_key("email", "gmail:personal/2") is None


def test_a_keyed_write_commits_whole_or_not_at_all(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_times(monkeypatch, NOW, LATER, LATER)
    from_email(store, key="kept")

    class DiskFull(Exception):
        pass

    def broken(*args: object, **kwargs: object) -> None:
        raise DiskFull

    monkeypatch.setattr(store, "insert_request_key", broken)
    with pytest.raises(DiskFull):
        from_email(store)
    with pytest.raises(DiskFull):
        link_to(store)
    assert [task.id for task in store.tasks()] == ["t1"]
    assert store.links("t1") == []
    assert len(store.audit("t1")) == 1
