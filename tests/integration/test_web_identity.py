from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from docket import clients, web
from docket.intake import Answer
from docket.store import Store
from tests.integration.test_web import Opened
from tests.support import fixed_times

NOW = "2026-11-17T14:00:00+00:00"
EMAIL_TOKEN = "synthetic-email-token-2f"
OTHER_TOKEN = "synthetic-other-token-2f"
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
def opened(tmp_path: Path) -> Opened:
    return Opened(tmp_path / "docket.sqlite3")


def headers(token: str, key: str = "k") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Idempotency-Key": key}


def client_for(opened: Opened, reverse: bool = False) -> TestClient:
    pairs = [(EMAIL_TOKEN, "email"), (OTHER_TOKEN, "agent")]
    if reverse:
        pairs.reverse()
    app = web.create_app(open_store=opened, tokens=dict(pairs), port=8767)
    return TestClient(app, base_url="http://127.0.0.1:8767")


@pytest.mark.parametrize("reverse", [False, True], ids=["email-first", "other-first"])
@pytest.mark.parametrize("path", ["/tasks", "/tasks/t1/links"], ids=["task", "link"])
def test_another_token_cannot_act_as_email(
    opened: Opened, monkeypatch: pytest.MonkeyPatch, path: str, reverse: bool
) -> None:
    fixed_times(monkeypatch, NOW)
    with client_for(opened, reverse) as client:
        assert client.post("/tasks", json=BODY, headers=headers(EMAIL_TOKEN)).status_code == 201
        response = client.post(
            path, json=BODY if path == "/tasks" else LINK, headers=headers(OTHER_TOKEN)
        )
    assert (response.status_code, response.json()) == (422, {"error": "invalid_client"})
    assert response.headers["cache-control"] == "no-store"
    assert "www-authenticate" not in response.headers
    assert opened.all_closed()
    with Store(opened.path) as store:
        assert [task.id for task in store.tasks()] == ["t1"]
        assert store.links("t1") == []
        assert [(row.action, row.actor) for row in store.audit("t1")] == [("create", "email")]
        assert store.request_key("agent", "k") is None
        assert store.request_key("email", "k").request == BODY


@pytest.mark.parametrize("path", ["/tasks", "/tasks/t1/links"], ids=["task", "link"])
@pytest.mark.parametrize("identity", ["email", "agent"], ids=["email", "other"])
def test_http_passes_the_matched_identity_to_intake(
    opened: Opened, monkeypatch: pytest.MonkeyPatch, path: str, identity: str
) -> None:
    seen = []

    def capture(*args, **kwargs) -> Answer:
        seen.append(kwargs.get("client"))
        return Answer(422, {"error": "invalid_client"})

    monkeypatch.setattr(web, "accept_task" if path == "/tasks" else "accept_link", capture)
    token = EMAIL_TOKEN if identity == "email" else OTHER_TOKEN
    with client_for(opened) as client:
        response = client.post(
            path, json=BODY if path == "/tasks" else LINK, headers=headers(token)
        )
    assert response.status_code == 422
    assert seen == [identity]
    assert opened.all_closed()


def test_two_token_map_keeps_email_retries_and_refuses_source_spoofing(
    opened: Opened, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_times(monkeypatch, NOW, NOW, NOW, NOW)
    with client_for(opened) as client:
        for status in (201, 200):
            response = client.post("/tasks", json=BODY, headers=headers(EMAIL_TOKEN))
            assert (response.status_code, response.json()) == (status, {"id": "t1"})
        for status in (201, 200):
            response = client.post("/tasks/t1/links", json=LINK, headers=headers(EMAIL_TOKEN, "l"))
            assert (response.status_code, response.json()) == (status, {"id": "l1"})
        for path, body in (("/tasks", BODY), ("/tasks/t1/links", LINK)):
            response = client.post(
                path, json={**body, "source": "agent"}, headers=headers(EMAIL_TOKEN, "spoof")
            )
            assert (response.status_code, response.json()) == (422, {"error": "invalid_source"})
    assert opened.all_closed()
    with Store(opened.path) as store:
        assert [task.id for task in store.tasks()] == ["t1"]
        assert [link.id for link in store.links("t1")] == ["l1"]
        assert len(store.audit("t1")) == 1
        assert store.request_key("email", "spoof") is None
        assert store.request_key("agent", "k") is None


@pytest.mark.parametrize("path", ["/tasks", "/tasks/t1/links"], ids=["task", "link"])
@pytest.mark.parametrize(
    "authorization",
    [None, "Bearer synthetic-wrong-token", "Bearer"],
    ids=["missing", "wrong", "malformed"],
)
def test_unknown_token_still_fails_before_body_or_store(
    opened: Opened, path: str, authorization: str | None
) -> None:
    sent = {} if authorization is None else {"Authorization": authorization}
    with client_for(opened) as client:
        response = client.post(path, content=b"{", headers=sent)
    assert (response.status_code, response.json()) == (401, {"error": "unauthorized"})
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.headers["cache-control"] == "no-store"
    assert opened.stores == []


def test_no_new_production_client_is_enabled() -> None:
    assert clients.CLIENTS == ("email",)
