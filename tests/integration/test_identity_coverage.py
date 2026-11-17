from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from docket import web
from docket.store import Store
from tests.integration.test_web import Opened

TOKEN = "synthetic-token-marker-2f"
OTHER = "synthetic-other-marker-2f"
TITLE = "synthetic-title-marker-2f"
REFERENCE = "synthetic-reference-marker-2f"
TASK = {
    "source": "email",
    "title": TITLE,
    "deadline": None,
    "provider": "gmail",
    "message_id": REFERENCE,
    "link": "https://mail.example/1",
}
LINK = {
    "source": "email",
    "provider": "gmail",
    "message_id": REFERENCE,
    "link": "https://mail.example/2",
}


@pytest.fixture
def opened(tmp_path: Path) -> Opened:
    return Opened(tmp_path / "docket.sqlite3")


def test_a_refused_non_email_request_returns_only_the_error(
    opened: Opened,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = web.create_app(
        open_store=opened,
        tokens={TOKEN: "email", OTHER: "agent"},
        port=8767,
    )
    headers = {"Authorization": f"Bearer {OTHER}", "Idempotency-Key": "k"}
    with caplog.at_level(0):
        with TestClient(app, base_url="http://127.0.0.1:8767") as client:
            task = client.post("/tasks", json=TASK, headers=headers)
            link = client.post("/tasks/t1/links", json=LINK, headers=headers)
    assert task.json() == {"error": "invalid_client"}
    assert link.json() == {"error": "invalid_client"}
    captured = capsys.readouterr()
    logged = "\n".join(record.getMessage() for record in caplog.records)
    for marker in (TOKEN, OTHER, TITLE, REFERENCE):
        assert marker not in task.text
        assert marker not in link.text
        assert marker not in captured.out
        assert marker not in captured.err
        assert marker not in logged
    with Store(opened.path) as store:
        assert store.tasks() == []
        assert store.links("t1") == []
        assert store.request_key("email", "k") is None
        assert store.request_key("agent", "k") is None
