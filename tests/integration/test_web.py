import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from docket.store import Store
from docket.web import (
    INVALID_JSON,
    MAX_BODY,
    NOT_FOUND,
    TOO_LARGE,
    UNAUTHORIZED,
    WRONG_HOST,
    create_app,
)
from tests.support import fixed_times

NOW = "2026-11-14T14:00:00+00:00"
LATER = "2026-11-14T14:30:00+00:00"
TOKEN = "tok-email-0123456789abcdefghijklmnopqrstuvw"
GOOD = {"Authorization": f"Bearer {TOKEN}", "Idempotency-Key": "gmail:personal/1"}
BODY = {
    "source": "email",
    "title": "Pay rent",
    "deadline": {"date": "2026-11-20", "time": "17:00", "time_zone": "America/New_York"},
    "provider": "gmail",
    "message_id": "personal/1",
    "link": "https://mail.example/1",
}
LINK = {"source": "email", "provider": "gmail", "message_id": "personal/2", "link": "https://m/2"}


class Opened:
    """Counts the stores the app opens and checks each one is closed."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.stores: list[Store] = []

    def __call__(self) -> Store:
        store = Store(self.path)
        self.stores.append(store)
        return store

    def all_closed(self) -> bool:
        closed = []
        for store in self.stores:
            try:
                store.tasks()
                closed.append(False)
            except Exception:  # noqa: BLE001
                closed.append(True)
        return all(closed)


@pytest.fixture
def opened(tmp_path: Path) -> Opened:
    return Opened(tmp_path / "docket.sqlite3")


@pytest.fixture
def client(opened: Opened) -> TestClient:
    app = create_app(open_store=opened, tokens={TOKEN: "email"}, port=8767)
    return TestClient(app, base_url="http://127.0.0.1:8767")


def stored(opened: Opened) -> list[str]:
    with Store(opened.path) as store:
        return [task.id for task in store.tasks()]


def test_the_names() -> None:
    assert (WRONG_HOST, NOT_FOUND, UNAUTHORIZED, TOO_LARGE, INVALID_JSON) == (
        "wrong_host",
        "not_found",
        "unauthorized",
        "too_large",
        "invalid_json",
    )
    assert MAX_BODY == 65536


def test_an_approved_task_is_created_then_repeated(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_times(monkeypatch, NOW, LATER, LATER)
    created = client.post("/tasks", json=BODY, headers=GOOD)
    assert (created.status_code, created.json()) == (201, {"id": "t1"})
    assert created.headers["content-type"] == "application/json"
    assert created.headers["cache-control"] == "no-store"
    again = client.post("/tasks", json=BODY, headers=GOOD)
    assert (again.status_code, again.json()) == (200, {"id": "t1"})
    reused = client.post("/tasks", json={**BODY, "title": "Pay rent today"}, headers=GOOD)
    assert (reused.status_code, reused.json()) == (409, {"error": "key_reused"})


def test_a_follow_up_link_is_added(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    fixed_times(monkeypatch, NOW, LATER, LATER)
    client.post("/tasks", json=BODY, headers=GOOD)
    headers = {**GOOD, "Idempotency-Key": "gmail:personal/2"}
    first = client.post("/tasks/t1/links", json=LINK, headers=headers)
    assert (first.status_code, first.json()) == (201, {"id": "l1"})
    again = client.post("/tasks/t1/links", json=LINK, headers=headers)
    assert (again.status_code, again.json()) == (200, {"id": "l1"})
    unknown = client.post("/tasks/t9/links", json=LINK, headers=headers)
    assert (unknown.status_code, unknown.json()) == (404, {"error": "unknown_task"})


@pytest.mark.parametrize(
    "host",
    ["example.com", "127.0.0.1:9999", "localhost", "127.0.0.1", "docket.local:8767"],
    ids=["other-name", "other-port", "no-port", "address-without-port", "lookalike"],
)
def test_a_request_for_another_host_is_refused_first(
    client: TestClient, opened: Opened, host: str
) -> None:
    for path in ("/tasks", "/nowhere"):
        answer = client.post(path, json=BODY, headers={**GOOD, "Host": host})
        assert (answer.status_code, answer.json()) == (400, {"error": "wrong_host"})
    answer = client.post("/tasks", content=b"{", headers={"Host": host})
    assert answer.status_code == 400
    assert opened.stores == []


def test_localhost_with_the_port_is_allowed(
    opened: Opened, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_times(monkeypatch, NOW)
    app = create_app(open_store=opened, tokens={TOKEN: "email"}, port=8767)
    answer = TestClient(app, base_url="http://localhost:8767").post(
        "/tasks", json=BODY, headers=GOOD
    )
    assert answer.status_code == 201


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/tasks"),
        ("PUT", "/tasks"),
        ("POST", "/"),
        ("POST", "/tasks/t1"),
        ("POST", "/tasks/a/b/links"),
        ("POST", "/tasks/../links"),
        ("GET", "/tasks/t1/links"),
        ("POST", "/proposals"),
    ],
    ids=[
        "get-tasks",
        "put-tasks",
        "root",
        "a-task",
        "slash-in-id",
        "dot-dot",
        "get-links",
        "proposals",
    ],
)
def test_anything_but_the_two_routes_is_not_found(
    client: TestClient, opened: Opened, method: str, path: str
) -> None:
    answer = client.request(method, path, json=BODY)
    assert (answer.status_code, answer.json()) == (404, {"error": "not_found"})
    assert opened.stores == []


@pytest.mark.parametrize(
    "authorization",
    [
        None,
        "",
        "Bearer",
        "Bearer wrong-token",
        f"bearer {TOKEN}",
        f"Basic {TOKEN}",
        f"Bearer  {TOKEN}",
        f"Bearer {TOKEN} ",
        f"Bearer {TOKEN[:-1]}",
    ],
    ids=[
        "none",
        "empty",
        "scheme-only",
        "wrong-token",
        "lower-case-scheme",
        "basic",
        "two-spaces",
        "trailing-space",
        "short-token",
    ],
)
def test_a_request_without_the_token_is_refused(
    client: TestClient, opened: Opened, authorization: str | None
) -> None:
    headers = {"Idempotency-Key": "k"}
    if authorization is not None:
        headers["Authorization"] = authorization
    for path in ("/tasks", "/tasks/t1/links"):
        answer = client.post(path, json=BODY, headers=headers)
        assert (answer.status_code, answer.json()) == (401, {"error": "unauthorized"})
        assert answer.headers["www-authenticate"] == "Bearer"
    assert opened.stores == []


def test_a_body_over_64_kib_is_refused_before_anything_else(
    client: TestClient, opened: Opened, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_times(monkeypatch, NOW)
    text = json.dumps(BODY)
    exact = (text + " " * (MAX_BODY - len(text))).encode()
    over = exact + b" "
    answer = client.post("/tasks", content=over, headers={"Authorization": GOOD["Authorization"]})
    assert (answer.status_code, answer.json()) == (413, {"error": "too_large"})
    assert opened.stores == []
    answer = client.post("/tasks", content=exact, headers=GOOD)
    assert (answer.status_code, answer.json()) == (201, {"id": "t1"})


@pytest.mark.parametrize(
    ("content", "key", "answer"),
    [
        (b"{", None, (400, {"error": "missing_key"})),
        (b"{", "k" * 201, (400, {"error": "missing_key"})),
        (b"{", "k", (422, {"error": "invalid_json"})),
        (b"", "k", (422, {"error": "invalid_json"})),
        (b"\xff\xfe{}", "k", (422, {"error": "invalid_json"})),
        (b'"Pay rent"', "k", (422, {"error": "invalid_body"})),
        (b"[]", "k", (422, {"error": "invalid_body"})),
    ],
    ids=[
        "key-before-json",
        "overlong-key-before-json",
        "broken-json",
        "empty-body",
        "not-utf-8",
        "a-json-string",
        "a-json-array",
    ],
)
def test_the_key_comes_before_the_json(
    client: TestClient, opened: Opened, content: bytes, key: str | None, answer: tuple
) -> None:
    headers = {"Authorization": GOOD["Authorization"]}
    if key is not None:
        headers["Idempotency-Key"] = key
    found = client.post("/tasks", content=content, headers=headers)
    assert (found.status_code, found.json()) == answer
    assert stored(opened) == []


def test_each_request_opens_and_closes_one_store(
    client: TestClient, opened: Opened, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_times(monkeypatch, NOW, LATER)
    client.post("/tasks", json=BODY, headers=GOOD)
    client.post("/tasks/t1/links", json=LINK, headers={**GOOD, "Idempotency-Key": "l"})
    client.post("/tasks", content=b"{", headers=GOOD)
    assert len(opened.stores) == 2
    assert opened.all_closed()


def test_a_token_for_no_known_client_is_refused(
    opened: Opened, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed_times(monkeypatch)
    app = create_app(open_store=opened, tokens={}, port=8767)
    answer = TestClient(app, base_url="http://127.0.0.1:8767").post(
        "/tasks", json=BODY, headers=GOOD
    )
    assert (answer.status_code, answer.json()) == (401, {"error": "unauthorized"})


def test_fastapis_own_telemetry_is_off(
    opened: Opened, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("FASTAPI_OTEL_AUTO_CONFIGURE", "true")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:4318")
    fixed_times(monkeypatch, NOW)
    app = create_app(open_store=opened, tokens={TOKEN: "email"}, port=8767)
    with caplog.at_level("DEBUG", logger="fastapi"):
        with TestClient(app, base_url="http://127.0.0.1:8767") as started:
            assert started.post("/tasks", json=BODY, headers=GOOD).status_code == 201
    assert [record.getMessage() for record in caplog.records if record.name == "fastapi"] == []
