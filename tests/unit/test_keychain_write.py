import pytest
from keyring.errors import KeyringError, PasswordSetError

from docket.keychain import (
    NAME_MESSAGE,
    VALUE_MESSAGE,
    KeychainUnavailable,
    get_secret,
    set_secret,
)
from tests.fakes import FakeKeychain


def test_a_secret_is_written_under_the_apps_service_and_replaced(
    fake_keychain: FakeKeychain,
) -> None:
    assert VALUE_MESSAGE == "invalid secret value"
    assert set_secret("client.email", "token-1") is None
    assert fake_keychain.secrets[("docket", "client.email")] == "token-1"
    assert fake_keychain.writes == [("docket", "client.email")]
    assert get_secret("client.email") == "token-1"
    set_secret("client.email", "token-2")
    assert get_secret("client.email") == "token-2"


@pytest.mark.parametrize("name", ["", "Client", "client email", "../x", "a" * 65])
def test_an_invalid_name_is_refused_before_any_write(
    fake_keychain: FakeKeychain, name: str
) -> None:
    with pytest.raises(ValueError) as raised:
        set_secret(name, "token-1")
    assert str(raised.value) == NAME_MESSAGE
    assert fake_keychain.writes == []


@pytest.mark.parametrize(
    "value",
    ["", "token\n", "two\nlines", 5, None],
    ids=["empty", "trailing-newline", "two-lines", "a-number", "none"],
)
def test_an_invalid_value_is_refused_before_any_write(
    fake_keychain: FakeKeychain, value: object
) -> None:
    with pytest.raises(ValueError) as raised:
        set_secret("client.email", value)  # type: ignore[arg-type]
    assert str(raised.value) == VALUE_MESSAGE
    assert fake_keychain.writes == []


@pytest.mark.parametrize(
    "error",
    [KeyringError("backend said token-1"), PasswordSetError("token-1 refused")],
    ids=["error", "set-error"],
)
def test_a_failed_write_hides_the_backend_text(
    fake_keychain: FakeKeychain, error: Exception
) -> None:
    fake_keychain.error = error
    with pytest.raises(KeychainUnavailable) as raised:
        set_secret("client.email", "token-1")
    assert str(raised.value) == "keychain unavailable: client.email"
    assert raised.value.__cause__ is None
    assert raised.value.__suppress_context__ is True


def test_without_a_fake_the_real_keychain_is_never_written() -> None:
    with pytest.raises(KeychainUnavailable) as raised:
        set_secret("client.email", "token-1")
    assert str(raised.value) == "keychain unavailable: client.email"
