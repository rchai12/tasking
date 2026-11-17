import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from docket import core
from docket.config import get_settings, prepare_data_dir
from docket.store import Store, open_store
from docket.web import create_app
from tests.reference_cases import BODY, LINK, NOW, snapshot, version_two
from tests.support import fixed_times, run


@pytest.mark.parametrize("kind", ["task", "link"])
@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("message_id", "x" * 513),
        ("link", "x" * 2049),
        ("message_id", "injected\x1b[2J"),
        ("link", "injected\u2028line"),
    ],
    ids=["id-long", "link-long", "escape", "line-separator"],
)
def test_http_refuses_unsafe_reference_without_consuming_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str, field: str, bad: str
) -> None:
    path = tmp_path / "docket.sqlite3"
    with Store(path):
        pass
    app = create_app(open_store=lambda: Store(path), tokens={"synthetic-token": "email"}, port=8767)
    fixed_times(monkeypatch, NOW)
    with TestClient(app, base_url="http://127.0.0.1:8767") as client:
        if kind == "link":
            made = client.post(
                "/tasks",
                json=BODY,
                headers={"Authorization": "Bearer synthetic-token", "Idempotency-Key": "task"},
            )
            assert made.status_code == 201
        fixed_times(monkeypatch)
        before = snapshot(path)
        response = client.post(
            "/tasks" if kind == "task" else "/tasks/t1/links",
            json={**(BODY if kind == "task" else LINK), field: bad},
            headers={"Authorization": "Bearer synthetic-token", "Idempotency-Key": "k"},
        )
        assert (response.status_code, response.json()) == (422, {"error": "invalid_reference"})
        assert response.headers["cache-control"] == "no-store"
        assert snapshot(path) == before
        fixed_times(monkeypatch, NOW, NOW)
        for status in (201, 200):
            response = client.post(
                "/tasks" if kind == "task" else "/tasks/t1/links",
                json=BODY if kind == "task" else LINK,
                headers={"Authorization": "Bearer synthetic-token", "Idempotency-Key": "k"},
            )
            assert (response.status_code, response.json()) == (
                status,
                {"id": "t1" if kind == "task" else "l1"},
            )


def test_cli_prints_valid_reference_text_without_rewriting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCKET_TIME_ZONE", "UTC")
    fixed_times(monkeypatch, NOW, NOW)
    with open_store(get_settings()) as opened:
        core.create_task(
            opened,
            title="Synthetic reference task",
            source="email",
            provider="gmail",
            message_id=" id with spaces ",
            link="https://mail.example/a?b=c#d",
        )
    response = run("tasks", "show", "t1")
    assert response.exit_code == 0
    assert response.stderr == ""
    assert response.stdout == (
        "t1  Synthetic reference task\nState: open\nDue: none\nWork: none\n"
        "Source: email, gmail  id with spaces \nLink: https://mail.example/a?b=c#d\n"
        "Created: Tue Nov 17 14:00 UTC\nUpdated: Tue Nov 17 14:00 UTC\n"
    )


def test_cli_refuses_unsafe_legacy_data_before_printing_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCKET_TIME_ZONE", "UTC")
    folder = prepare_data_dir(get_settings())
    path = folder / "docket.sqlite3"
    version_two(path)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE tasks SET message_id='synthetic-secret' || char(27) WHERE number=1")
    before = snapshot(path)
    fixed_times(monkeypatch)
    result = run("tasks", "show", "t1")
    assert (result.exit_code, result.stdout, result.stderr) == (
        1,
        "",
        "invalid stored reference: t1 message_id\n",
    )
    assert snapshot(path) == before
