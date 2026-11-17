import inspect
from pathlib import Path

import pytest

from docket import core
from docket.intake import Answer, accept_link, accept_task
from docket.store import Store
from tests.integration.test_core_identity import EqualText
from tests.support import fixed_times

NOW = "2026-11-17T14:00:00+00:00"
BODY = {
    "source": "email",
    "title": "Review invented invoice",
    "deadline": None,
    "provider": "gmail",
    "message_id": "synthetic/1",
    "link": "https://mail.example/1",
}
LINK = {
    "source": "email",
    "provider": "gmail",
    "message_id": "synthetic/2",
    "link": "https://mail.example/2",
}


@pytest.fixture
def store(tmp_path: Path):
    with Store(tmp_path / "docket.sqlite3") as opened:
        yield opened


@pytest.mark.parametrize("function", [accept_task, accept_link], ids=["task", "link"])
def test_client_is_a_required_keyword(function) -> None:
    parameter = inspect.signature(function).parameters["client"]
    assert parameter.kind == inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is inspect.Parameter.empty


@pytest.mark.parametrize(
    "client",
    ["agent", "other", None, ["email"], EqualText("email")],
    ids=["agent", "unknown", "null", "list", "equal-nonstring"],
)
def test_only_email_identity_can_enter_intake(
    store: Store, monkeypatch: pytest.MonkeyPatch, client: object
) -> None:
    fixed_times(monkeypatch)
    assert accept_task(store, client=client, key="k", body=BODY) == Answer(
        422, {"error": "invalid_client"}
    )
    assert accept_link(store, "t999", client=client, key="k", body=LINK) == Answer(
        422, {"error": "invalid_client"}
    )
    assert store.tasks() == []
    assert store.request_key("email", "k") is None
    assert store.request_key("agent", "k") is None


def test_key_then_client_then_existing_body_order(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_times(monkeypatch)
    assert accept_task(store, client="agent", key=None, body=None) == Answer(
        400, {"error": "missing_key"}
    )
    assert accept_link(store, "t999", client="agent", key=None, body=None) == Answer(
        400, {"error": "missing_key"}
    )
    assert accept_task(store, client="agent", key="k", body=None) == Answer(
        422, {"error": "invalid_client"}
    )
    assert accept_link(store, "t999", client="agent", key="k", body=None) == Answer(
        422, {"error": "invalid_client"}
    )
    assert accept_task(store, client="email", key="k", body=None) == Answer(
        422, {"error": "invalid_body"}
    )
    assert accept_link(store, "t999", client="email", key="k", body=None) == Answer(
        404, {"error": "unknown_task"}
    )


def test_email_identity_keeps_retries_links_and_key_conflicts(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_times(monkeypatch, NOW, NOW, NOW, NOW, NOW)
    assert accept_task(store, client="email", key="k", body=BODY) == Answer(201, {"id": "t1"})
    assert accept_task(store, client="email", key="k", body=BODY) == Answer(200, {"id": "t1"})
    assert accept_link(store, "t1", client="email", key="l", body=LINK) == Answer(201, {"id": "l1"})
    assert accept_link(store, "t1", client="email", key="l", body=LINK) == Answer(200, {"id": "l1"})
    assert accept_link(store, "t1", client="email", key="k", body=LINK) == Answer(
        409, {"error": "key_reused"}
    )
    assert [task.id for task in store.tasks()] == ["t1"]
    assert [link.id for link in store.links("t1")] == ["l1"]
    assert [(row.action, row.actor) for row in store.audit("t1")] == [("create", "email")]
    saved = store.request_key("email", "k")
    assert saved is not None and saved.request == BODY
    assert store.request_key("agent", "k") is None


def test_an_agent_core_key_does_not_reserve_the_email_key(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_times(monkeypatch, NOW, NOW)
    core.create_task_once(
        store,
        client="agent",
        key="k",
        request={"title": "Synthetic agent task"},
        title="Synthetic agent task",
        source="agent",
    )
    assert accept_task(store, client="email", key="k", body=BODY) == Answer(201, {"id": "t2"})
    assert store.request_key("agent", "k").task_id == "t1"
    assert store.request_key("email", "k").task_id == "t2"
    assert [task.source for task in store.tasks()] == ["agent", "email"]


def test_identity_is_not_taken_from_the_body(store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    fixed_times(monkeypatch, NOW)
    assert accept_task(store, client="email", key="k", body={**BODY, "source": "agent"}) == Answer(
        422, {"error": "invalid_source"}
    )
    assert accept_task(store, client="email", key="k", body=BODY) == Answer(201, {"id": "t1"})
    assert accept_link(
        store, "t1", client="email", key="l", body={**LINK, "source": "agent"}
    ) == Answer(422, {"error": "invalid_source"})
    assert store.links("t1") == []
    assert store.request_key("email", "l") is None
