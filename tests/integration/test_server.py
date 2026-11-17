import socket
import sqlite3
import threading
import time
from pathlib import Path

import httpx2
import pytest
import uvicorn

from docket import server
from docket.clients import issue_token
from docket.config import get_settings
from docket.server import NO_CLIENTS_MESSAGE, ServeError, build_app, run_app
from docket.store import StoreError
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


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_the_message() -> None:
    assert NO_CLIENTS_MESSAGE == "No clients yet: run docket clients add email."


def test_with_no_client_the_app_is_not_built(fake_keychain: FakeKeychain, tmp_path: Path) -> None:
    with pytest.raises(ServeError) as raised:
        build_app(get_settings())
    assert str(raised.value) == NO_CLIENTS_MESSAGE
    assert not (tmp_path / "data" / "docket.sqlite3").exists()


def test_building_the_app_opens_the_store_once_to_migrate_it(
    fake_keychain: FakeKeychain, tmp_path: Path
) -> None:
    issue_token("email")
    build_app(get_settings())
    connection = sqlite3.connect(tmp_path / "data" / "docket.sqlite3")
    assert connection.execute("PRAGMA user_version").fetchone() == (3,)


def test_a_newer_store_stops_the_build(fake_keychain: FakeKeychain, tmp_path: Path) -> None:
    issue_token("email")
    (tmp_path / "data").mkdir(mode=0o700)
    connection = sqlite3.connect(tmp_path / "data" / "docket.sqlite3")
    connection.execute("PRAGMA user_version = 99")
    connection.close()
    with pytest.raises(StoreError) as raised:
        build_app(get_settings())
    assert str(raised.value) == "unsupported schema version: 99"


def test_run_app_serves_on_loopback_only_and_quietly(
    fake_keychain: FakeKeychain, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[object, dict[str, object]]] = []
    monkeypatch.setattr(uvicorn, "run", lambda app, **kwargs: calls.append((app, kwargs)))
    issue_token("email")
    app = build_app(get_settings())
    run_app(app, 8767)
    assert calls == [
        (
            app,
            {
                "host": "127.0.0.1",
                "port": 8767,
                "access_log": False,
                "server_header": False,
                "proxy_headers": False,
                "log_level": "warning",
            },
        )
    ]
    assert server.uvicorn is uvicorn


def test_the_built_app_answers_over_real_loopback(
    fake_keychain: FakeKeychain, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    port = free_port()
    monkeypatch.setenv("DOCKET_WEB_PORT", str(port))
    token = issue_token("email")
    fixed_times(monkeypatch, NOW)
    app = build_app(get_settings())
    running = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", access_log=False)
    )
    thread = threading.Thread(target=running.run, daemon=True)
    thread.start()
    try:
        for _ in range(200):
            if running.started:
                break
            time.sleep(0.02)
        headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "gmail:personal/1"}
        answer = httpx2.post(f"http://127.0.0.1:{port}/tasks", json=BODY, headers=headers)
        assert (answer.status_code, answer.json()) == (201, {"id": "t1"})
        refused = httpx2.post(f"http://127.0.0.1:{port}/tasks", json=BODY)
        assert (refused.status_code, refused.json()) == (401, {"error": "unauthorized"})
    finally:
        running.should_exit = True
        thread.join(timeout=10)
    assert not thread.is_alive()
    connection = sqlite3.connect(tmp_path / "data" / "docket.sqlite3")
    assert connection.execute("SELECT title FROM tasks").fetchall() == [("Pay rent",)]
