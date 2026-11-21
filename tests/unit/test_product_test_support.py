import inspect
import sqlite3
from pathlib import Path

import pytest

from docket.core import CoreError
from docket.store import Store
from tests import support


class OtherError(Exception):
    code = "synthetic"

    def __str__(self):
        return "synthetic"


class WrongText(CoreError):
    def __str__(self):
        return "wrong text"


@pytest.mark.parametrize("case", ["correct", "wrong-code", "wrong-text", "no-error", "other-error"])
def test_shared_refusal_checks_code_text_and_exception_type(case: str) -> None:
    helper = support.refused
    error = CoreError("synthetic")
    if case == "wrong-code":
        error = CoreError("different")
    elif case == "wrong-text":
        error = WrongText("synthetic")
    elif case == "other-error":
        error = OtherError()

    def call():
        if case != "no-error":
            raise error

    if case == "correct":
        assert helper("synthetic", call) is None
    elif case == "other-error":
        with pytest.raises(OtherError) as raised:
            helper("synthetic", call)
        assert raised.value is error
    elif case == "no-error":
        with pytest.raises(pytest.fail.Exception):
            helper("synthetic", call)
    else:
        with pytest.raises(AssertionError):
            helper("synthetic", call)


def test_shared_path_is_a_function_scoped_explicit_fixture(tmp_path: Path) -> None:
    fixture = support.path
    marker = fixture._fixture_function_marker
    assert (marker.name, marker.scope, marker.autouse, marker.params) == (
        None,
        "function",
        False,
        None,
    )
    assert fixture.__wrapped__(tmp_path) == tmp_path / "docket.sqlite3"


class BodyFailure(Exception):
    pass


@pytest.mark.parametrize("failure", [False, True], ids=["normal", "body-exception"])
def test_shared_store_is_empty_and_closes_once_on_every_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: bool
) -> None:
    fixture = support.store
    assert list(inspect.signature(fixture.__wrapped__).parameters) == ["tmp_path"]
    marker = fixture._fixture_function_marker
    assert (marker.name, marker.scope, marker.autouse) == (None, "function", False)
    calls = []
    original = Store.close

    def close(self):
        calls.append("closed")
        return original(self)

    monkeypatch.setattr(Store, "close", close)
    generator = fixture.__wrapped__(tmp_path)
    opened = next(generator)
    try:
        assert opened.tasks() == []
        assert calls == []
        if failure:
            error = BodyFailure("synthetic")
            with pytest.raises(BodyFailure) as raised:
                generator.throw(error)
            assert raised.value is error
        else:
            with pytest.raises(StopIteration):
                next(generator)
        assert calls == ["closed"]
        with pytest.raises(sqlite3.ProgrammingError):
            opened.tasks()
    finally:
        generator.close()
