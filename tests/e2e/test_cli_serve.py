import sqlite3
from pathlib import Path

import pytest
import uvicorn
from keyring.errors import KeyringError

from docket.clients import issue_token
from tests.fakes import FakeKeychain
from tests.support import run


@pytest.fixture
def ran(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(uvicorn, "run", lambda app, **kwargs: calls.append(kwargs))
    return calls


def test_serve_says_where_and_runs(fake_keychain: FakeKeychain, ran: list) -> None:
    issue_token("email")
    result = run("serve")
    assert (result.exit_code, result.stdout, result.stderr) == (
        0,
        "Serving on http://127.0.0.1:8767\n",
        "",
    )
    assert [(call["host"], call["port"]) for call in ran] == [("127.0.0.1", 8767)]


def test_serve_uses_the_port_setting(
    fake_keychain: FakeKeychain, ran: list, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DOCKET_WEB_PORT", "9123")
    issue_token("email")
    assert run("serve").stdout == "Serving on http://127.0.0.1:9123\n"
    assert [call["port"] for call in ran] == [9123]


def test_serve_needs_no_time_zone(
    fake_keychain: FakeKeychain, ran: list, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DOCKET_TIME_ZONE", raising=False)
    issue_token("email")
    assert run("serve").exit_code == 0


@pytest.mark.parametrize(
    ("setup", "message"),
    [
        ("none", "No clients yet: run docket clients add email."),
        ("keychain", "keychain unavailable: client.email"),
        ("port", "DOCKET_WEB_PORT must be 1024 to 65535"),
        ("schema", "unsupported schema version: 99"),
    ],
    ids=["no-clients", "keychain-down", "bad-port", "newer-store"],
)
def test_serve_refuses_to_start(
    fake_keychain: FakeKeychain,
    ran: list,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    setup: str,
    message: str,
) -> None:
    if setup != "none":
        issue_token("email")
    if setup == "keychain":
        fake_keychain.error = KeyringError("backend detail")
    if setup == "port":
        monkeypatch.setenv("DOCKET_WEB_PORT", "80")
    if setup == "schema":
        (tmp_path / "data").mkdir(mode=0o700)
        connection = sqlite3.connect(tmp_path / "data" / "docket.sqlite3")
        connection.execute("PRAGMA user_version = 99")
        connection.close()
    result = run("serve")
    assert (result.exit_code, result.stdout, result.stderr) == (1, "", message + "\n")
    assert ran == []


def test_a_bad_port_leaves_no_data_folder(
    fake_keychain: FakeKeychain, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("DOCKET_WEB_PORT", "80")
    result = run("serve")
    assert (result.exit_code, result.stderr) == (
        1,
        "DOCKET_WEB_PORT must be 1024 to 65535\n",
    )
    assert not (tmp_path / "data").exists()


def test_a_down_keychain_leaves_no_data_folder(fake_keychain: FakeKeychain, tmp_path: Path) -> None:
    fake_keychain.error = KeyringError("backend detail")
    result = run("serve")
    assert (result.exit_code, result.stderr) == (1, "keychain unavailable: client.email\n")
    assert not (tmp_path / "data").exists()
