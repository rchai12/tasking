"""Synthetic core input properties: a wrong-typed value is refused before any read or write."""

import sqlite3
import sys
from contextlib import closing
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

NY = "America/New_York"
NOW = datetime(2026, 11, 14, 14, 0, tzinfo=UTC)
FUNCTIONS = ("create_task", "create_task_once", "edit_task")
FIELDS = ("deadline", "work")
CODES = {"deadline": "invalid_deadline", "work": "invalid_work"}


class ClockRead(Exception):
    """Raised when the probe's clock is read on a path that must not read it."""


class Opaque:
    """An object of no type core knows."""


def junk() -> list[object]:
    """Values of every kind an agent's JSON or a careless caller could hand core."""
    return [
        "",
        "2026-11-20",
        "2026-11-20T17:00:00-05:00",
        "none",
        0,
        -1,
        1795219200,
        0.0,
        float("nan"),
        True,
        False,
        b"2026-11-20",
        [],
        ["2026-11-20", "17:00"],
        (),
        {},
        {"date": "2026-11-20", "time": "17:00", "time_zone": NY},
        {"start": "2026-11-20T19:00:00Z", "minutes": 60},
        date(2026, 11, 20),
        datetime(2026, 11, 20, 22, 0, tzinfo=UTC),
        timedelta(minutes=60),
        Opaque(),
        object(),
    ]


def expected(field: str, value: object, deadline_type: type, work_type: type) -> str | None:
    """The oracle: the code core must give for one value in one field, or None to accept it."""
    wanted = deadline_type if field == "deadline" else work_type
    if value is None or isinstance(value, wanted):
        return None
    return CODES[field]


def oracle() -> None:
    class D:
        pass

    class W:
        pass

    assert expected("deadline", None, D, W) is None
    assert expected("deadline", D(), D, W) is None
    assert expected("deadline", W(), D, W) == "invalid_deadline"
    assert expected("work", D(), D, W) == "invalid_work"
    assert expected("work", W(), D, W) is None
    assert expected("work", 60, D, W) == "invalid_work"
    assert expected("deadline", True, D, W) == "invalid_deadline"
    assert len(junk()) == 23


def dump(path: Path) -> list[str]:
    with closing(sqlite3.connect(path)) as connection:
        return list(connection.iterdump())


def no_clock() -> datetime:
    raise ClockRead


def call(name: str, store: object, field: str, value: object, key: str) -> object:
    from docket import core

    if name == "create_task":
        return core.create_task(store, title="Synthetic task", source="owner", **{field: value})
    if name == "create_task_once":
        return core.create_task_once(
            store,
            client="agent",
            key=key,
            request={"title": "Synthetic task", "source": "agent"},
            title="Synthetic task",
            source="agent",
            **{field: value},
        )
    return core.edit_task(store, "t1", actor="agent", **{field: value})


def wrong_values_are_refused_before_any_read(root: Path) -> None:
    from docket import clock, core
    from docket.deadlines import Deadline, WorkTime
    from docket.store import UNCHANGED, Store

    reached = 0
    for name in FUNCTIONS:
        path = root / f"{name}.sqlite3"
        with Store(path) as store:
            if name == "edit_task":
                with patch.object(clock, "now", lambda: NOW):
                    core.create_task(store, title="Synthetic task", source="owner")
            values = junk() + ([] if name == "edit_task" else [UNCHANGED])
            for field in FIELDS:
                other = WorkTime(NOW + timedelta(days=1), 60, NY)
                if field == "work":
                    other = Deadline(NOW + timedelta(days=2), NY, True)
                for number, value in enumerate([*values, other]):
                    code = expected(field, value, Deadline, WorkTime)
                    assert code is not None, f"probe value {value!r} is accepted by the oracle"
                    before = dump(path)
                    with patch.object(clock, "now", no_clock):
                        try:
                            call(name, store, field, value, f"probe:{field}:{number}")
                        except core.CoreError as raised:
                            got = raised.code
                        except ClockRead:
                            got = "a clock read"
                        except Exception as raised:
                            got = type(raised).__name__
                        else:
                            got = "no refusal"
                    shown = type(value).__name__
                    assert got == code, f"{name} {field}={shown}: expected {code}, got {got}"
                    assert dump(path) == before, f"{name} {field}={shown}: the database changed"
                    reached += 1
    assert reached >= 140, f"reached {reached} wrong values, expected 140 or more"


def right_values_still_pass(root: Path) -> None:
    from docket import clock, core
    from docket.deadlines import Deadline, WorkTime
    from docket.store import Store

    deadline = Deadline(NOW + timedelta(days=6, hours=8), NY, True)
    work = WorkTime(NOW + timedelta(days=6, hours=5), 60, NY)
    with Store(root / "docket.sqlite3") as store, patch.object(clock, "now", lambda: NOW):
        number = 0
        for chosen_deadline in (None, deadline):
            for chosen_work in (None, work):
                number += 1
                task = core.create_task(
                    store,
                    title="Synthetic task",
                    source="owner",
                    deadline=chosen_deadline,
                    work=chosen_work,
                )
                assert (task.deadline, task.work) == (chosen_deadline, chosen_work), task.id
                once = core.create_task_once(
                    store,
                    client="agent",
                    key=f"probe:{number}",
                    request={"number": number},
                    title="Synthetic task",
                    source="agent",
                    deadline=chosen_deadline,
                    work=chosen_work,
                )
                assert once.changed, f"probe:{number} was not created"
                edited = core.edit_task(
                    store, task.id, actor="owner", deadline=chosen_deadline, work=chosen_work
                )
                assert not edited.changed, f"{task.id}: an edit to the same values changed it"
        cleared = core.edit_task(store, "t3", actor="owner", deadline=None, work=None)
        assert (cleared.task.deadline, cleared.task.work) == (None, None), "t3 kept a value"


def every_code_has_a_sentence(root: Path) -> None:
    from docket import core
    from docket.views import refusal_text

    found = sorted(
        value
        for name, value in vars(core).items()
        if name.isupper() and not name.startswith("_") and isinstance(value, str)
    )
    missing = sorted({"invalid_deadline", "invalid_work"} - set(found))
    assert not missing, f"docket.core defines no code {missing}"
    for code in found:
        for task_id in (None, "t7"):
            try:
                sentence = refusal_text(code, task_id)
            except KeyError:
                raise AssertionError(f"no sentence for {code}") from None
            assert sentence.endswith(".") and "\n" not in sentence, f"{code}: {sentence!r}"


def main() -> None:
    oracle()
    print("type oracle ok")
    if "--oracle-only" in sys.argv:
        print("FAILURES 0")
        return
    failures = 0
    for name, check in (
        ("wrong values are refused before any read", wrong_values_are_refused_before_any_read),
        ("right values still pass", right_values_still_pass),
        ("every code has a sentence", every_code_has_a_sentence),
    ):
        with TemporaryDirectory() as directory:
            try:
                check(Path(directory))
            except Exception as raised:
                detail = str(raised) if isinstance(raised, AssertionError) else ""
                print(f"FAIL {name}: {detail or type(raised).__name__}")
                failures += 1
            else:
                print(name + " ok")
    print(f"FAILURES {failures}")


if __name__ == "__main__":
    main()
