import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from docket.core import CoreError
from tests.support import refused

ROOT = Path(__file__).resolve().parents[2]
CHILD = textwrap.dedent(
    """\
    import socket
    import sqlite3
    from datetime import UTC, datetime
    from pathlib import Path

    def blocked(*_args, **_kwargs):
        raise AssertionError("network")

    socket.socket.connect = blocked
    socket.getaddrinfo = blocked

    import pytest

    import docket.clock as clock_mod
    import docket.config as config_mod
    import docket.store as store_mod

    def settings():
        raise AssertionError("settings")

    config_mod.get_settings = settings
    clocks = []

    def now():
        clocks.append("now")
        raise AssertionError("clock")

    clock_mod.now = now
    opens = []
    closes = []
    _init = store_mod.Store.__init__
    _close = store_mod.Store.close

    def init(self, path):
        opens.append(path)
        return _init(self, path)

    def close(self):
        closes.append(self)
        return _close(self)

    store_mod.Store.__init__ = init
    store_mod.Store.close = close

    from tests.support import path
    from tests.support import store
    from tests.support import store as base_store

    __all__ = ["base_store"]

    assert opens == [] and clocks == []

    held = []
    T0 = datetime(2026, 11, 14, 9, 0, tzinfo=UTC)

    def test_a_path_is_not_created_and_reads_no_clock(path):
        assert path.name == "docket.sqlite3"
        assert not path.exists()
        assert Path.home() not in path.parents
        assert opens == [] and clocks == []

    def test_b_first_store_is_empty(store, path):
        assert store.tasks() == []
        held.append((path, store))
        assert clocks == []

    def test_c_second_store_is_distinct_after_the_first_closes(store, path):
        assert store.tasks() == []
        first_path, first = held[0]
        assert path != first_path
        assert closes == [first]
        with pytest.raises(sqlite3.ProgrammingError):
            first.tasks()
        assert clocks == []

    @pytest.fixture
    def seeded(base_store):
        with base_store.transaction():
            for title in ("Pay rent", "Book flights"):
                base_store.insert_task(
                    title=title,
                    state="open",
                    deadline=None,
                    work=None,
                    source="owner",
                    provider=None,
                    message_id=None,
                    link=None,
                    at=T0,
                )
        yield base_store

    def test_d_seed_keeps_the_two_rows(seeded):
        tasks = seeded.tasks()
        assert [item.id for item in tasks] == ["t1", "t2"]
        assert [item.title for item in tasks] == ["Pay rent", "Book flights"]
        assert tasks[0].created_at == tasks[1].created_at == T0
        held.append((len(closes), seeded))

    def test_e_seed_closes_once():
        before, seeded = held[-1]
        assert len(closes) == before + 1
        with pytest.raises(sqlite3.ProgrammingError):
            seeded.tasks()
    """
)


class OtherError(Exception):
    code = "synthetic"

    def __str__(self) -> str:
        return "synthetic"


class WrongText(CoreError):
    def __str__(self) -> str:
        return "wrong text"


def test_two_pytest_tests_get_distinct_empty_stores_and_the_seed_closes_once(
    tmp_path: Path,
) -> None:
    consumer = tmp_path / "consumer.py"
    consumer.write_text(CHILD, encoding="utf-8")
    environment = {key: value for key, value in os.environ.items() if not key.startswith("DOCKET_")}
    environment["PYTHONPATH"] = os.pathsep.join((str(ROOT / "src"), str(ROOT)))
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--noconftest",
            "--no-cov",
            "-q",
            "--tb=line",
            str(consumer),
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "5 passed" in done.stdout


def test_refused_invokes_the_callback_once_and_does_not_catch_other_errors() -> None:
    calls: list[str] = []

    def correct() -> None:
        calls.append("called")
        raise CoreError("synthetic")

    assert refused("synthetic", correct) is None
    assert calls == ["called"]

    calls.clear()
    error = OtherError()

    def unexpected() -> None:
        calls.append("called")
        raise error

    with pytest.raises(OtherError) as raised:
        refused("synthetic", unexpected)
    assert raised.value is error
    assert calls == ["called"]

    calls.clear()

    def silent() -> None:
        calls.append("called")

    with pytest.raises(pytest.fail.Exception):
        refused("synthetic", silent)
    assert calls == ["called"]

    calls.clear()

    def wrong() -> None:
        calls.append("called")
        raise WrongText("synthetic")

    with pytest.raises(AssertionError):
        refused("synthetic", wrong)
    assert calls == ["called"]
