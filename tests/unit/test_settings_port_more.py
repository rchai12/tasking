import pytest

from docket.config import DATA_DIR_MESSAGE, TIME_ZONE_MESSAGE, ConfigError, get_settings


def test_a_bad_data_folder_is_reported_before_the_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCKET_DATA_DIR", "relative")
    monkeypatch.setenv("DOCKET_WEB_PORT", "80")
    with pytest.raises(ConfigError) as raised:
        get_settings()
    assert str(raised.value) == DATA_DIR_MESSAGE


def test_a_bad_time_zone_is_reported_before_the_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCKET_TIME_ZONE", "Mars/Base")
    monkeypatch.setenv("DOCKET_WEB_PORT", "80")
    with pytest.raises(ConfigError) as raised:
        get_settings()
    assert str(raised.value) == TIME_ZONE_MESSAGE
