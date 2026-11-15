import pytest

from docket.config import WEB_PORT_MESSAGE, WORK_MINUTES_MESSAGE, ConfigError, get_settings


def test_the_port_setting_and_its_message(monkeypatch: pytest.MonkeyPatch) -> None:
    assert WEB_PORT_MESSAGE == "DOCKET_WEB_PORT must be 1024 to 65535"
    assert get_settings().web_port == 8767
    monkeypatch.setenv("DOCKET_WEB_PORT", "9000")
    assert get_settings().web_port == 9000


@pytest.mark.parametrize("value", ["1024", "65535"], ids=["lowest", "highest"])
def test_the_ends_of_the_range(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("DOCKET_WEB_PORT", value)
    assert get_settings().web_port == int(value)


@pytest.mark.parametrize(
    "value",
    ["1023", "80", "65536", "0", "-1", "abc", ""],
    ids=["1023", "privileged", "65536", "zero", "negative", "letters", "empty"],
)
def test_a_bad_port_is_refused(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("DOCKET_WEB_PORT", value)
    with pytest.raises(ConfigError) as raised:
        get_settings()
    assert str(raised.value) == WEB_PORT_MESSAGE
    assert raised.value.__cause__ is None


def test_the_port_is_reported_after_the_work_length(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCKET_WORK_MINUTES", "4")
    monkeypatch.setenv("DOCKET_WEB_PORT", "80")
    with pytest.raises(ConfigError) as raised:
        get_settings()
    assert str(raised.value) == WORK_MINUTES_MESSAGE
