import pytest
from pydantic import ValidationError

from docket import config


@pytest.mark.parametrize(
    ("locations", "expected"),
    [
        ([("future_field",)], "Invalid docket settings."),
        ([()], "Invalid docket settings."),
        ([], "Invalid docket settings."),
        ([("web_port",)], "DOCKET_WEB_PORT must be 1024 to 65535"),
        ([("web_port",), ("work_minutes",)], "DOCKET_WORK_MINUTES must be 5 to 720"),
        ([("web_port",), ("time_zone",)], "DOCKET_TIME_ZONE must be a time zone name"),
        (
            [("web_port",), ("time_zone",), ("data_dir",)],
            "DOCKET_DATA_DIR must be an absolute path",
        ),
        ([("future_field",), ("web_port",)], "DOCKET_WEB_PORT must be 1024 to 65535"),
        ([("time_zone", "nested")], "DOCKET_TIME_ZONE must be a time zone name"),
    ],
    ids=[
        "unknown",
        "root",
        "empty",
        "port",
        "minutes-before-port",
        "zone-before-port",
        "data-dir-first",
        "known-before-fallback",
        "nested-known",
    ],
)
def test_settings_mapping_is_explicit_and_safe(
    monkeypatch: pytest.MonkeyPatch, locations, expected: str, capsys: pytest.CaptureFixture[str]
) -> None:
    errors = [
        {
            "type": "value_error",
            "loc": location,
            "input": "PRIVATE_SYNTHETIC",
            "ctx": {"error": ValueError("PRIVATE_SYNTHETIC")},
        }
        for location in locations
    ]
    error = ValidationError.from_exception_data("Synthetic", errors)

    def invalid():
        raise error

    monkeypatch.setattr(config, "Settings", invalid)
    with pytest.raises(config.ConfigError) as raised:
        config.get_settings()
    assert str(raised.value) == expected
    assert raised.value.__cause__ is None
    assert raised.value.__suppress_context__
    captured = capsys.readouterr()
    assert (captured.out, captured.err) == ("", "")


def test_generic_settings_message_is_constant() -> None:
    assert config.SETTINGS_MESSAGE == "Invalid docket settings."
