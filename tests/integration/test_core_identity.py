from pathlib import Path

import pytest

from docket import core
from docket.store import Store
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


class EqualText:
    """A non-string that previously passed equality or membership checks."""

    def __init__(self, text: str) -> None:
        self.text = text

    def __eq__(self, other: object) -> bool:
        return other == self.text

    def __hash__(self) -> int:
        return hash(self.text)


@pytest.fixture
def store(tmp_path: Path):
    with Store(tmp_path / "docket.sqlite3") as opened:
        yield opened


def assert_empty(store: Store) -> None:
    assert store.tasks() == []
    assert store.request_key("email", "identity/1") is None
    assert store.request_key("agent", "identity/1") is None
    assert store.audit("t1") == []
    assert store.links("t1") == []


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("client", ["email"], "invalid_client"),
        ("client", {"email": 1}, "invalid_client"),
        ("client", EqualText("email"), "invalid_client"),
        ("source", ["email"], "invalid_source"),
        ("source", EqualText("email"), "invalid_source"),
        ("provider", ["gmail"], "invalid_reference"),
        ("provider", {"gmail": 1}, "invalid_reference"),
        ("provider", EqualText("gmail"), "invalid_reference"),
    ],
    ids=[
        "list-client",
        "dict-client",
        "equal-client",
        "list-source",
        "equal-source",
        "list-provider",
        "dict-provider",
        "equal-provider",
    ],
)
def test_keyed_create_refuses_non_string_identity_fields(
    store: Store, monkeypatch: pytest.MonkeyPatch, field: str, value: object, code: str
) -> None:
    fixed_times(monkeypatch)
    fields = {
        "client": "email",
        "key": "identity/1",
        "request": BODY,
        "title": "Review invented invoice",
        "source": "email",
        "provider": "gmail",
        "message_id": "synthetic/1",
        "link": "https://mail.example/1",
        field: value,
    }
    with pytest.raises(core.CoreError) as raised:
        core.create_task_once(store, **fields)
    assert raised.value.code == code
    assert str(raised.value) == code
    assert_empty(store)


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("client", ["email"], "invalid_client"),
        ("client", EqualText("email"), "invalid_client"),
        ("provider", ["gmail"], "invalid_reference"),
        ("provider", {"gmail": 1}, "invalid_reference"),
        ("provider", EqualText("gmail"), "invalid_reference"),
    ],
    ids=["list-client", "equal-client", "list-provider", "dict-provider", "equal-provider"],
)
def test_links_refuse_non_string_identity_fields_before_the_clock(
    store: Store, monkeypatch: pytest.MonkeyPatch, field: str, value: object, code: str
) -> None:
    fixed_times(monkeypatch)
    fields = {
        "client": "email",
        "key": "identity/1",
        "request": BODY,
        "provider": "gmail",
        "message_id": "synthetic/1",
        "link": "https://mail.example/1",
        field: value,
    }
    with pytest.raises(core.CoreError) as raised:
        core.add_link(store, "t1", **fields)
    assert raised.value.code == code
    assert str(raised.value) == code
    assert_empty(store)


def test_valid_agent_core_create_remains_available(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_times(monkeypatch, NOW, NOW)
    fields = {
        "client": "agent",
        "key": "identity/1",
        "request": {"title": "Review invented invoice"},
        "title": "Review invented invoice",
        "source": "agent",
    }
    made = core.create_task_once(store, **fields)
    again = core.create_task_once(store, **fields)
    assert (made.task.id, made.changed, again.task.id, again.changed) == ("t1", True, "t1", False)
    assert [(row.action, row.actor) for row in store.audit("t1")] == [("create", "agent")]
    assert store.request_key("email", "identity/1") is None
    saved = store.request_key("agent", "identity/1")
    assert saved is not None and saved.request == {"title": "Review invented invoice"}
