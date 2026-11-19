"""Phase 6a: `docket mcp serve` runs the MCP server on stdio and prints nothing of its own."""

import sqlite3
from pathlib import Path

import pytest
from keyring.errors import KeyringError

from tests.fakes import FakeKeychain
from tests.support import run


@pytest.fixture
def ran(monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    from mcp.server.mcpserver import MCPServer

    calls: list[tuple] = []

    def record(self: MCPServer, transport: str = "stdio", **kwargs: object) -> None:
        calls.append((self.name, transport, kwargs))

    monkeypatch.setattr(MCPServer, "run", record)
    return calls


def test_mcp_serve_runs_the_tools_on_stdio(ran: list, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCKET_TIME_ZONE", "America/New_York")
    result = run("mcp", "serve")
    assert (result.exit_code, result.stdout, result.stderr) == (0, "", "")
    assert ran == [("docket", "stdio", {})]


def test_mcp_serve_reads_no_secret(
    ran: list, monkeypatch: pytest.MonkeyPatch, fake_keychain: FakeKeychain
) -> None:
    monkeypatch.setenv("DOCKET_TIME_ZONE", "America/New_York")
    fake_keychain.error = KeyringError("backend detail")
    assert run("mcp", "serve").exit_code == 0
    assert ran == [("docket", "stdio", {})]


@pytest.mark.parametrize(
    ("setup", "message"),
    [
        ("zone", "DOCKET_TIME_ZONE is not set"),
        ("minutes", "DOCKET_WORK_MINUTES must be 5 to 720"),
        ("schema", "unsupported schema version: 99"),
    ],
    ids=["no-home-zone", "bad-setting", "newer-store"],
)
def test_mcp_serve_refuses_to_start(
    ran: list, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, setup: str, message: str
) -> None:
    if setup != "zone":
        monkeypatch.setenv("DOCKET_TIME_ZONE", "America/New_York")
    if setup == "minutes":
        monkeypatch.setenv("DOCKET_WORK_MINUTES", "3")
    if setup == "schema":
        (tmp_path / "data").mkdir(mode=0o700)
        connection = sqlite3.connect(tmp_path / "data" / "docket.sqlite3")
        connection.execute("PRAGMA user_version = 99")
        connection.close()
    result = run("mcp", "serve")
    assert (result.exit_code, result.stdout, result.stderr) == (1, "", message + "\n")
    assert ran == []
