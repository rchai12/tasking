"""Strict ASCII date and clock parsers for callers that already chose a refusal."""

import re
from datetime import date, time

_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_TIME = re.compile(r"[0-9]{2}:[0-9]{2}")
_MESSAGE = "invalid date or time"


class ParseError(ValueError):
    pass


def parse_date(value: object) -> date:
    if not isinstance(value, str) or _DATE.fullmatch(value) is None:
        raise ParseError(_MESSAGE) from None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ParseError(_MESSAGE) from None


def parse_time(value: object) -> time:
    if not isinstance(value, str) or _TIME.fullmatch(value) is None:
        raise ParseError(_MESSAGE) from None
    try:
        return time.fromisoformat(value)
    except ValueError:
        raise ParseError(_MESSAGE) from None
