import pytest

from docket.config import (
    DATA_DIR_MESSAGE,
    TIME_ZONE_MESSAGE,
    TIME_ZONE_UNSET_MESSAGE,
    WORK_MINUTES_MESSAGE,
    ConfigError,
    get_settings,
    home_zone,
)


def test_the_messages() -> None:
    assert TIME_ZONE_MESSAGE == "DOCKET_TIME_ZONE must be a time zone name"
    assert TIME_ZONE_UNSET_MESSAGE == "DOCKET_TIME_ZONE is not set"
    assert WORK_MINUTES_MESSAGE == "DOCKET_WORK_MINUTES must be 5 to 720"


def test_the_defaults() -> None:
    settings = get_settings()
    assert (settings.time_zone, settings.work_minutes) == (None, 60)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("America/New_York", "America/New_York"), ("UTC", "UTC"), ("", None)],
    ids=["new-york", "utc", "empty-is-unset"],
)
def test_the_time_zone_comes_from_the_environment(
    monkeypatch: pytest.MonkeyPatch, value: str, expected: str | None
) -> None:
    monkeypatch.setenv("DOCKET_TIME_ZONE", value)
    assert get_settings().time_zone == expected


@pytest.mark.parametrize(
    "value",
    ["america/new_york", "Mars/Base", " UTC", "UTC ", "Local", "../etc/passwd"],
    ids=["lower-case", "made-up", "leading-space", "trailing-space", "not-a-zone", "path"],
)
def test_a_bad_time_zone_is_refused(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("DOCKET_TIME_ZONE", value)
    with pytest.raises(ConfigError) as raised:
        get_settings()
    assert str(raised.value) == TIME_ZONE_MESSAGE
    assert raised.value.__cause__ is None


def test_home_zone_needs_the_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ConfigError) as raised:
        home_zone(get_settings())
    assert str(raised.value) == TIME_ZONE_UNSET_MESSAGE
    monkeypatch.setenv("DOCKET_TIME_ZONE", "Asia/Tokyo")
    assert home_zone(get_settings()) == "Asia/Tokyo"


@pytest.mark.parametrize(
    ("value", "expected"),
    [("90", 90), ("5", 5), ("720", 720)],
    ids=["ninety", "shortest", "longest"],
)
def test_the_work_length_comes_from_the_environment(
    monkeypatch: pytest.MonkeyPatch, value: str, expected: int
) -> None:
    monkeypatch.setenv("DOCKET_WORK_MINUTES", value)
    assert get_settings().work_minutes == expected


@pytest.mark.parametrize(
    "value",
    ["4", "721", "0", "-60", "abc", ""],
    ids=["four", "721", "zero", "negative", "letters", "empty"],
)
def test_a_bad_work_length_is_refused(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("DOCKET_WORK_MINUTES", value)
    with pytest.raises(ConfigError) as raised:
        get_settings()
    assert str(raised.value) == WORK_MINUTES_MESSAGE
    assert raised.value.__cause__ is None


@pytest.mark.parametrize(
    ("data_dir", "zone", "minutes", "expected"),
    [
        ("data", "Mars/Base", "4", DATA_DIR_MESSAGE),
        (None, "Mars/Base", "4", TIME_ZONE_MESSAGE),
        ("data", None, "4", DATA_DIR_MESSAGE),
    ],
    ids=["data-dir-first", "zone-before-length", "data-dir-before-length"],
)
def test_the_first_bad_setting_is_reported(
    monkeypatch: pytest.MonkeyPatch,
    data_dir: str | None,
    zone: str | None,
    minutes: str,
    expected: str,
) -> None:
    if data_dir is not None:
        monkeypatch.setenv("DOCKET_DATA_DIR", data_dir)
    if zone is not None:
        monkeypatch.setenv("DOCKET_TIME_ZONE", zone)
    monkeypatch.setenv("DOCKET_WORK_MINUTES", minutes)
    with pytest.raises(ConfigError) as raised:
        get_settings()
    assert str(raised.value) == expected
