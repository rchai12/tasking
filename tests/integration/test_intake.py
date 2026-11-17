from datetime import UTC, datetime
from pathlib import Path

import pytest

from docket import core
from docket.deadlines import Deadline
from docket.intake import (
    INVALID_BODY,
    INVALID_DEADLINE,
    MISSING_KEY,
    Answer,
    accept_link,
    accept_task,
)
from docket.store import Store
from tests.support import fixed_times

NY = "America/New_York"
NOW = "2026-11-14T14:00:00+00:00"
LATER = "2026-11-14T14:30:00+00:00"
KEY = "gmail:personal/18c2f0a1"
LINK_KEY = "gmail:personal/18c2f0b7"
BODY = {
    "source": "email",
    "title": "Pay rent",
    "deadline": {"date": "2026-11-20", "time": "17:00", "time_zone": NY},
    "provider": "gmail",
    "message_id": "personal/18c2f0a1",
    "link": "https://mail.google.com/mail/?authuser=me@example.com#all/18c2f0a1",
}
LINK = {
    "source": "email",
    "provider": "gmail",
    "message_id": "personal/18c2f0b7",
    "link": "https://mail.google.com/mail/?authuser=me@example.com#all/18c2f0b7",
}


@pytest.fixture
def store(tmp_path: Path):
    with Store(tmp_path / "docket.sqlite3") as opened:
        yield opened


def changed(**fields: object) -> dict[str, object]:
    body = dict(BODY)
    body.update(fields)
    return body


def without(name: str) -> dict[str, object]:
    return {key: value for key, value in BODY.items() if key != name}


def test_the_codes() -> None:
    assert (MISSING_KEY, INVALID_BODY, INVALID_DEADLINE) == (
        "missing_key",
        "invalid_body",
        "invalid_deadline",
    )


@pytest.mark.parametrize(
    ("body", "deadline"),
    [
        (BODY, Deadline(datetime(2026, 11, 20, 22, 0, tzinfo=UTC), NY, True)),
        (
            changed(deadline={"date": "2026-11-20", "time": None, "time_zone": NY}),
            Deadline(datetime(2026, 11, 20, 22, 0, tzinfo=UTC), NY, False),
        ),
        (
            changed(deadline={"date": "2027-03-14", "time": "02:30", "time_zone": NY}),
            Deadline(datetime(2027, 3, 14, 7, 30, tzinfo=UTC), NY, True),
        ),
        (changed(deadline=None), None),
    ],
    ids=["date-and-time", "date-only", "missing-time-moves-forward", "no-deadline"],
)
def test_an_approved_email_task_is_created(
    store: Store, monkeypatch: pytest.MonkeyPatch, body: dict[str, object], deadline: object
) -> None:
    fixed_times(monkeypatch, NOW)
    assert accept_task(store, client="email", key=KEY, body=body) == Answer(201, {"id": "t1"})
    task = store.task("t1")
    assert task is not None
    assert (task.title, task.state, task.source, task.deadline) == (
        "Pay rent",
        "open",
        "email",
        deadline,
    )
    assert (task.provider, task.message_id, task.link) == (
        "gmail",
        "personal/18c2f0a1",
        BODY["link"],
    )
    found = store.request_key("email", KEY)
    assert found is not None and found.request == body


def test_a_repeat_answers_200_with_the_same_id(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_times(monkeypatch, NOW, LATER)
    assert accept_task(store, client="email", key=KEY, body=BODY) == Answer(201, {"id": "t1"})
    assert accept_task(store, client="email", key=KEY, body=dict(reversed(BODY.items()))) == Answer(
        200, {"id": "t1"}
    )
    assert [task.id for task in store.tasks()] == ["t1"]


def test_a_reused_key_answers_409(store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    fixed_times(monkeypatch, NOW, LATER)
    accept_task(store, client="email", key=KEY, body=BODY)
    assert accept_task(
        store, client="email", key=KEY, body=changed(title="Pay rent today")
    ) == Answer(409, {"error": "key_reused"})
    assert [task.title for task in store.tasks()] == ["Pay rent"]


@pytest.mark.parametrize(
    "key",
    [None, "", "k" * 201],
    ids=["no-header", "empty", "too-long"],
)
def test_a_missing_or_overlong_key_answers_400(
    store: Store, monkeypatch: pytest.MonkeyPatch, key: str | None
) -> None:
    fixed_times(monkeypatch)
    assert accept_task(store, client="email", key=key, body=BODY) == Answer(
        400, {"error": "missing_key"}
    )
    assert accept_link(store, "t1", client="email", key=key, body=LINK) == Answer(
        400, {"error": "missing_key"}
    )
    assert store.tasks() == []


def test_the_longest_key_is_accepted(store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    fixed_times(monkeypatch, NOW)
    assert accept_task(store, client="email", key="k" * 200, body=BODY).status == 201


@pytest.mark.parametrize(
    ("body", "code"),
    [
        (["Pay rent"], INVALID_BODY),
        ("Pay rent", INVALID_BODY),
        (None, INVALID_BODY),
        (without("link"), INVALID_BODY),
        (changed(extra="x"), INVALID_BODY),
        (changed(evidence="Rent is due Friday"), INVALID_BODY),
        (changed(deadline="2026-11-20"), INVALID_DEADLINE),
        (changed(deadline={"date": "2026-11-20", "time": "17:00"}), INVALID_DEADLINE),
        (
            changed(deadline={"date": "2026-11-20", "time": "17:00", "time_zone": NY, "x": 1}),
            INVALID_DEADLINE,
        ),
        (changed(deadline={"date": "20261120", "time": None, "time_zone": NY}), INVALID_DEADLINE),
        (changed(deadline={"date": "2026-11-31", "time": None, "time_zone": NY}), INVALID_DEADLINE),
        (
            changed(deadline={"date": "２０２６-11-20", "time": None, "time_zone": NY}),
            INVALID_DEADLINE,
        ),
        (
            changed(deadline={"date": "2026-11-20", "time": "1700", "time_zone": NY}),
            INVALID_DEADLINE,
        ),
        (
            changed(deadline={"date": "2026-11-20", "time": "24:00", "time_zone": NY}),
            INVALID_DEADLINE,
        ),
        (
            changed(deadline={"date": "2026-11-20", "time": "17:00:00", "time_zone": NY}),
            INVALID_DEADLINE,
        ),
        (
            changed(deadline={"date": "2026-11-20", "time": None, "time_zone": "america/new_york"}),
            INVALID_DEADLINE,
        ),
        (changed(deadline={"date": "2026-11-20", "time": None, "time_zone": ""}), INVALID_DEADLINE),
        (changed(deadline={"date": 20261120, "time": None, "time_zone": NY}), INVALID_DEADLINE),
        (changed(source="agent"), "invalid_source"),
        (changed(source=None), INVALID_BODY),
        (changed(title=" Pay rent"), "invalid_title"),
        (changed(title="Pay\nrent"), "invalid_title"),
        (changed(title=7), INVALID_BODY),
        (changed(provider="aol"), "invalid_reference"),
        (changed(link=""), "invalid_reference"),
        (changed(message_id=None), INVALID_BODY),
        (changed(provider=["gmail"]), INVALID_BODY),
        (changed(title=" Pay rent", deadline="soon"), INVALID_DEADLINE),
        (changed(extra="x", deadline="soon"), INVALID_BODY),
    ],
    ids=[
        "a-list",
        "a-string",
        "null",
        "missing-field",
        "extra-field",
        "the-evidence-quote",
        "deadline-not-an-object",
        "deadline-missing-zone",
        "deadline-extra-field",
        "compact-date",
        "no-such-day",
        "fullwidth-digits",
        "compact-time",
        "hour-24",
        "time-with-seconds",
        "zone-wrong-case",
        "zone-empty",
        "date-not-text",
        "source-agent",
        "source-null",
        "title-space",
        "title-two-lines",
        "title-not-text",
        "provider",
        "empty-link",
        "message-id-null",
        "provider-a-list",
        "deadline-before-title",
        "shape-before-deadline",
    ],
)
def test_an_invalid_task_answers_422_and_writes_nothing(
    store: Store, monkeypatch: pytest.MonkeyPatch, body: object, code: str
) -> None:
    fixed_times(monkeypatch)
    assert accept_task(store, client="email", key=KEY, body=body) == Answer(422, {"error": code})
    assert store.tasks() == []
    assert store.request_key("email", KEY) is None


def test_a_follow_up_link_is_added_once(store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    fixed_times(monkeypatch, NOW, LATER, LATER)
    accept_task(store, client="email", key=KEY, body=BODY)
    assert accept_link(store, "t1", client="email", key=LINK_KEY, body=LINK) == Answer(
        201, {"id": "l1"}
    )
    assert accept_link(store, "t1", client="email", key=LINK_KEY, body=LINK) == Answer(
        200, {"id": "l1"}
    )
    assert [(link.id, link.message_id) for link in store.links("t1")] == [
        ("l1", "personal/18c2f0b7")
    ]


def test_a_link_follows_the_fakes_order(store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    fixed_times(monkeypatch, NOW, LATER, LATER)
    accept_task(store, client="email", key=KEY, body=BODY)
    assert accept_link(store, "t9", client="email", key=LINK_KEY, body={"bad": 1}) == Answer(
        404, {"error": "unknown_task"}
    )
    assert accept_link(store, "t1", client="email", key=LINK_KEY, body={"bad": 1}) == Answer(
        422, {"error": "invalid_body"}
    )
    accept_link(store, "t1", client="email", key=LINK_KEY, body=LINK)
    reused = {**LINK, "link": "https://mail.example/other"}
    assert accept_link(store, "t1", client="email", key=LINK_KEY, body=reused) == Answer(
        409, {"error": "key_reused"}
    )
    assert accept_link(store, "t9", client="email", key=LINK_KEY, body=LINK) == Answer(
        404, {"error": "unknown_task"}
    )


@pytest.mark.parametrize(
    ("task_id", "body", "answer"),
    [
        ("t9", LINK, Answer(404, {"error": "unknown_task"})),
        ("x", LINK, Answer(404, {"error": "unknown_task"})),
        ("../t1", LINK, Answer(404, {"error": "unknown_task"})),
        ("t1", {**LINK, "title": "x"}, Answer(422, {"error": "invalid_body"})),
        (
            "t1",
            {key: value for key, value in LINK.items() if key != "source"},
            Answer(422, {"error": "invalid_body"}),
        ),
        ("t1", ["x"], Answer(422, {"error": "invalid_body"})),
        ("t1", {**LINK, "source": "agent"}, Answer(422, {"error": "invalid_source"})),
        ("t1", {**LINK, "provider": "aol"}, Answer(422, {"error": "invalid_reference"})),
        ("t1", {**LINK, "provider": ["gmail"]}, Answer(422, {"error": "invalid_body"})),
        ("t1", {**LINK, "message_id": ""}, Answer(422, {"error": "invalid_reference"})),
    ],
    ids=[
        "unknown-task",
        "malformed-id",
        "a-path",
        "extra-field",
        "missing-source",
        "a-list",
        "source-agent",
        "provider",
        "provider-a-list",
        "empty-message-id",
    ],
)
def test_an_invalid_link_writes_nothing(
    store: Store, monkeypatch: pytest.MonkeyPatch, task_id: str, body: object, answer: Answer
) -> None:
    fixed_times(monkeypatch, NOW)
    accept_task(store, client="email", key=KEY, body=BODY)
    assert accept_link(store, task_id, client="email", key=LINK_KEY, body=body) == answer
    assert store.links("t1") == []


def test_a_link_may_follow_a_done_task(store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    fixed_times(monkeypatch, NOW, NOW, LATER)
    accept_task(store, client="email", key=KEY, body=BODY)
    core.change_state(store, "t1", "done", actor="owner")
    assert accept_link(store, "t1", client="email", key=LINK_KEY, body=LINK) == Answer(
        201, {"id": "l1"}
    )


def test_intake_reads_only_the_cores_clock(store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    fixed_times(monkeypatch, NOW, LATER)
    assert accept_task(store, client="email", key=KEY, body=BODY).status == 201
    assert accept_link(store, "t1", client="email", key=LINK_KEY, body=LINK).status == 201


def test_answers_never_echo_the_request(store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    fixed_times(monkeypatch, NOW)
    secret = "Rent for flat 4B, account 0042"
    answers = [
        accept_task(store, client="email", key=KEY, body=changed(title=secret + "\n")),
        accept_task(store, client="email", key=KEY, body=changed(extra=secret)),
        accept_task(store, client="email", key=secret, body=changed(provider=secret)),
        accept_link(store, secret, client="email", key=LINK_KEY, body=LINK),
    ]
    assert all(set(answer.body) == {"error"} for answer in answers)
    assert not any(secret in str(answer.body) for answer in answers)
