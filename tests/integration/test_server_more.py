import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from docket.clients import issue_token
from docket.config import get_settings
from docket.server import build_app
from tests.fakes import FakeKeychain
from tests.support import fixed_times

NOW = "2026-11-14T14:00:00+00:00"
BODY = {
    "source": "email",
    "title": "Pay rent",
    "deadline": None,
    "provider": "gmail",
    "message_id": "personal/1",
    "link": "https://mail.example/1",
}


def test_a_request_uses_the_settings_store(
    fake_keychain: FakeKeychain, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    folder = tmp_path / "data"
    monkeypatch.setenv("DOCKET_DATA_DIR", str(folder))
    token = issue_token("email")
    fixed_times(monkeypatch, NOW)
    app = build_app(get_settings())
    client = TestClient(app, base_url="http://127.0.0.1:8767")
    answer = client.post(
        "/tasks",
        json=BODY,
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "gmail:personal/1"},
    )
    assert answer.status_code == 201
    connection = sqlite3.connect(folder / "docket.sqlite3")
    assert connection.execute("SELECT title FROM tasks").fetchall() == [("Pay rent",)]
