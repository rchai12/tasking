import re

import pytest
from keyring.errors import KeyringError

from tests.fakes import FakeKeychain
from tests.support import run

TOKEN_LINE = re.compile(r"[A-Za-z0-9_-]{43}\n")


def test_adding_the_email_client_prints_its_token_once(fake_keychain: FakeKeychain) -> None:
    result = run("clients", "add", "email")
    assert (result.exit_code, result.stderr) == (0, "")
    assert TOKEN_LINE.fullmatch(result.stdout)
    assert fake_keychain.secrets[("docket", "client.email")] == result.stdout.strip()


def test_adding_it_again_is_refused_and_keeps_the_token(fake_keychain: FakeKeychain) -> None:
    first = run("clients", "add", "email").stdout.strip()
    result = run("clients", "add", "email")
    assert (result.exit_code, result.stdout, result.stderr) == (
        1,
        "",
        "email already has a token; use --replace to issue a new one.\n",
    )
    assert fake_keychain.secrets[("docket", "client.email")] == first


def test_replace_issues_a_new_token(fake_keychain: FakeKeychain) -> None:
    first = run("clients", "add", "email").stdout.strip()
    result = run("clients", "add", "email", "--replace")
    assert (result.exit_code, result.stderr) == (0, "")
    assert TOKEN_LINE.fullmatch(result.stdout)
    assert result.stdout.strip() != first
    assert fake_keychain.secrets[("docket", "client.email")] == result.stdout.strip()


def test_an_unknown_client_is_refused(fake_keychain: FakeKeychain) -> None:
    result = run("clients", "add", "camera")
    assert (result.exit_code, result.stdout, result.stderr) == (1, "", "Clients are: email.\n")
    assert fake_keychain.writes == []


def test_a_keychain_failure_is_reported_without_its_text(fake_keychain: FakeKeychain) -> None:
    fake_keychain.error = KeyringError("backend detail")
    result = run("clients", "add", "email")
    assert (result.exit_code, result.stdout, result.stderr) == (
        1,
        "",
        "keychain unavailable: client.email\n",
    )


def test_the_command_needs_no_time_zone(
    fake_keychain: FakeKeychain, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DOCKET_TIME_ZONE", raising=False)
    assert run("clients", "add", "email").exit_code == 0


def test_a_missing_client_is_a_usage_mistake(fake_keychain: FakeKeychain) -> None:
    result = run("clients", "add")
    assert (result.exit_code, result.stdout) == (2, "")
    assert "Missing argument 'client'." in result.stderr
