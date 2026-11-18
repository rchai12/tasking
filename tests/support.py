"""Helpers shared by tests: running a command, fixed times and ids, and loading a script.

New tests import these instead of copying them.
"""

import importlib.util
from collections.abc import Callable, Iterator
from datetime import datetime
from pathlib import Path
from types import ModuleType

import pytest
from typer.testing import CliRunner

from docket import clock, ids
from docket.cli import app
from docket.core import CoreError
from docket.store import Store

runner = CliRunner(env={"COLUMNS": "200"})


def run(*args: object):
    """Run `docket` with these arguments, each turned into text."""
    return runner.invoke(app, [str(arg) for arg in args])


def fixed_times(monkeypatch: pytest.MonkeyPatch, *moments: str) -> None:
    """Make `clock.now()` return these ISO moments, one per call, in order."""
    times = iter([datetime.fromisoformat(moment) for moment in moments])
    monkeypatch.setattr(clock, "now", lambda: next(times))


def fixed_ids(monkeypatch: pytest.MonkeyPatch, *values: str) -> None:
    """Make `ids.new_id()` return these values, one per call, in order."""
    found = iter(values)
    monkeypatch.setattr(ids, "new_id", lambda: next(found))


def load_script(name: str) -> ModuleType:
    """Load `scripts/<name>.py` as a module, so a test can call its `main`."""
    path = Path(__file__).resolve().parent.parent / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"scripts_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def path(tmp_path: Path) -> Path:
    return tmp_path / "docket.sqlite3"


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    with Store(tmp_path / "docket.sqlite3") as opened:
        yield opened


def refused(code: str, call: Callable[[], object]) -> None:
    with pytest.raises(CoreError) as raised:
        call()
    assert (raised.value.code, str(raised.value)) == (code, code)
