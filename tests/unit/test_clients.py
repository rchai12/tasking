import re

import pytest

from docket.clients import (
    ALREADY_MESSAGE,
    CLIENTS,
    UNKNOWN_CLIENT_MESSAGE,
    ClientError,
    client_tokens,
    issue_token,
    token_name,
)
from docket.keychain import KeychainUnavailable
from tests.fakes import FakeKeychain

TOKEN = re.compile(r"[A-Za-z0-9_-]{43}")


def test_the_names() -> None:
    assert CLIENTS == ("email",)
    assert token_name("email") == "client.email"
    assert ALREADY_MESSAGE == "email already has a token; use --replace to issue a new one."
    assert UNKNOWN_CLIENT_MESSAGE == "Clients are: email."


def test_a_token_is_issued_and_kept(fake_keychain: FakeKeychain) -> None:
    token = issue_token("email")
    assert TOKEN.fullmatch(token)
    assert fake_keychain.secrets[("docket", "client.email")] == token


def test_a_second_token_needs_replace(fake_keychain: FakeKeychain) -> None:
    first = issue_token("email")
    with pytest.raises(ClientError) as raised:
        issue_token("email")
    assert str(raised.value) == ALREADY_MESSAGE
    assert fake_keychain.secrets[("docket", "client.email")] == first
    second = issue_token("email", replace=True)
    assert second != first
    assert fake_keychain.secrets[("docket", "client.email")] == second


@pytest.mark.parametrize("client", ["camera", "agent", "owner", "", "Email"])
def test_an_unknown_client_is_refused(fake_keychain: FakeKeychain, client: str) -> None:
    with pytest.raises(ClientError) as raised:
        issue_token(client)
    assert str(raised.value) == UNKNOWN_CLIENT_MESSAGE
    assert fake_keychain.writes == []


def test_replace_issues_a_first_token_and_tokens_are_random(fake_keychain: FakeKeychain) -> None:
    first = issue_token("email", replace=True)
    assert fake_keychain.secrets[("docket", "client.email")] == first
    tokens = {issue_token("email", replace=True) for _ in range(50)}
    assert len(tokens | {first}) == 51


def test_the_tokens_the_service_accepts(fake_keychain: FakeKeychain) -> None:
    assert client_tokens() == {}
    token = issue_token("email")
    assert client_tokens() == {token: "email"}


def test_a_keychain_failure_is_not_hidden(fake_keychain: FakeKeychain) -> None:
    fake_keychain.error = KeychainUnavailable("keychain unavailable: client.email")
    with pytest.raises(KeychainUnavailable):
        issue_token("email")
    with pytest.raises(KeychainUnavailable):
        client_tokens()
