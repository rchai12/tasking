from datetime import date, time

import pytest

from docket.parsing import ParseError, parse_date, parse_time


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-11-20", date(2026, 11, 20)),
        ("2028-02-29", date(2028, 2, 29)),
        ("0001-01-01", date(1, 1, 1)),
        ("9999-12-31", date(9999, 12, 31)),
    ],
    ids=["ordinary", "leap", "first-year", "last-year"],
)
def test_strict_date_values(value: str, expected: date) -> None:
    assert parse_date(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        20261120,
        "",
        "20261120",
        "2026-W47-5",
        "2026-1-20",
        "2026-11-2",
        "２０２６-１１-２０",
        "2026-11-20\n",
        " 2026-11-20",
        "2026-11-31",
        "2027-02-29",
        "0000-01-01",
        "2026-11-20T00:00",
        "PRIVATE_SYNTHETIC",
    ],
    ids=[
        "null",
        "bool",
        "int",
        "empty",
        "compact",
        "week",
        "short-month",
        "short-day",
        "unicode-digits",
        "newline",
        "space",
        "bad-day",
        "not-leap",
        "zero-year",
        "datetime",
        "private-marker",
    ],
)
def test_strict_date_refusals_do_not_echo_input(value: object) -> None:
    with pytest.raises(ParseError) as raised:
        parse_date(value)
    assert str(raised.value) == "invalid date or time"
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None or raised.value.__suppress_context__


@pytest.mark.parametrize(
    ("value", "expected"),
    [("00:00", time(0, 0)), ("17:00", time(17, 0)), ("23:59", time(23, 59))],
    ids=["midnight", "ordinary", "last-minute"],
)
def test_strict_time_values(value: str, expected: time) -> None:
    assert parse_time(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        None,
        False,
        1700,
        "",
        "1700",
        "7:00",
        "17:0",
        "１７:００",
        "17:00\n",
        "17:00 ",
        "24:00",
        "23:60",
        "17:00:00",
        "17:00:00.0",
        "17:00Z",
        "17:00+00:00",
    ],
    ids=[
        "null",
        "bool",
        "int",
        "empty",
        "compact",
        "short-hour",
        "short-minute",
        "unicode-digits",
        "newline",
        "space",
        "bad-hour",
        "bad-minute",
        "seconds",
        "fraction",
        "utc",
        "offset",
    ],
)
def test_strict_time_refusals_do_not_echo_input(value: object) -> None:
    with pytest.raises(ParseError) as raised:
        parse_time(value)
    assert str(raised.value) == "invalid date or time"
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None or raised.value.__suppress_context__


def test_the_parse_error_is_typed() -> None:
    assert issubclass(ParseError, ValueError)
