"""Offline checks of shared rules, exact parsing, DST and safe settings errors."""

import argparse
import re
import sqlite3
from datetime import UTC, date, datetime, time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from docket import config
from docket.deadlines import make_deadline
from docket.store import Store

DATE_CASES = [
    ("2028-02-29", "2028-02-29"),
    ("2026-11-31", None),
    ("20261120", None),
    ("2026-11-20\n", None),
    ("２０２６-１１-２０", None),
]
TIME_CASES = [
    ("00:00", "00:00:00"),
    ("23:59", "23:59:00"),
    ("24:00", None),
    ("1700", None),
    ("17:00:00", None),
    ("17:00+00:00", None),
]
DST = [
    ("2026-11-01", "01:30", "2026-11-01T05:30:00+00:00"),
    ("2027-03-14", "02:30", "2027-03-14T07:30:00+00:00"),
]


def oracle() -> None:
    for cases, pattern, read in (
        (DATE_CASES, r"[0-9]{4}-[0-9]{2}-[0-9]{2}", date.fromisoformat),
        (TIME_CASES, r"[0-9]{2}:[0-9]{2}", time.fromisoformat),
    ):
        for value, expected in cases:
            actual = None
            if re.fullmatch(pattern, value):
                try:
                    actual = read(value).isoformat()
                except ValueError:
                    pass
            assert actual == expected
    for day, at, expected in DST:
        wall = datetime.fromisoformat(day + "T" + at).replace(
            tzinfo=ZoneInfo("America/New_York"), fold=0
        )
        assert wall.astimezone(UTC).isoformat() == expected


def grammar(_root: Path) -> None:
    from docket.parsing import ParseError, parse_date, parse_time

    for cases, read in ((DATE_CASES, parse_date), (TIME_CASES, parse_time)):
        for value, expected in cases:
            try:
                actual = read(value).isoformat()
            except ParseError as error:
                assert str(error) == "invalid date or time"
                actual = None
            assert actual == expected, f"value {value!r}: expected {expected!r}; actual {actual!r}"


def transitions(_root: Path) -> None:
    from docket.parsing import parse_date, parse_time

    for day, at, expected in DST:
        result = make_deadline(parse_date(day), parse_time(at), "America/New_York")
        actual = result.at.isoformat()
        assert actual == expected, f"{day} {at}: expected {expected}; actual {actual}"


def schema(root: Path) -> None:
    from docket import domain

    path = root / "docket.sqlite3"
    with Store(path):
        with sqlite3.connect(path) as connection:
            for table in ("tasks", "links"):
                sql = connection.execute(
                    "SELECT sql FROM sqlite_master WHERE name=?", (table,)
                ).fetchone()[0]
                match = re.search(r"provider\s+IN\s*\(([^)]+)\)", sql)
                assert match is not None
                stored = set(re.findall(r"'([^']+)'", match[1]))
                assert stored == set(domain.PROVIDERS), (
                    f"{table}.provider: SQL {stored}; Python {domain.PROVIDERS}"
                )
    assert (domain.TITLE_MAX, domain.REQUEST_KEY_MAX) == (100, 200)
    assert (domain.WORK_MINUTES_MIN, domain.WORK_MINUTES_MAX) == (5, 720)


def fallback(_root: Path) -> None:
    for location in (("future_field",), ()):
        error = ValidationError.from_exception_data(
            "Synthetic",
            [
                {
                    "type": "value_error",
                    "loc": location,
                    "input": "PRIVATE_SYNTHETIC",
                    "ctx": {"error": ValueError("PRIVATE_SYNTHETIC")},
                }
            ],
        )
        with patch.object(config, "Settings", side_effect=error):
            try:
                config.get_settings()
            except config.ConfigError as refused:
                assert str(refused) == "Invalid docket settings.", (
                    f"location {location}: expected generic settings refusal; actual {refused}"
                )
                assert refused.__cause__ is None
            else:
                raise AssertionError("unknown settings error accepted")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--oracle-only", action="store_true")
    args = parser.parse_args()
    oracle()
    print("standard-library oracle ok")
    failures = 0
    if not args.oracle_only:
        for name, check in (
            ("strict grammar", grammar),
            ("DST instants", transitions),
            ("SQL policy parity", schema),
            ("safe fallback", fallback),
        ):
            with TemporaryDirectory() as folder:
                try:
                    check(Path(folder))
                    print(f"{name} ok")
                except Exception as error:
                    print(f"{name} FAIL: {type(error).__name__}: {error}")
                    failures += 1
    print(f"FAILURES {failures}")
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
