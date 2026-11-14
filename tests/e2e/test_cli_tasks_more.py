import sqlite3

import pytest

from docket.config import get_settings, prepare_data_dir
from docket.store import DB_FILENAME
from tests.support import fixed_times, run


@pytest.mark.parametrize(
    "args",
    [["add", "Pay rent"], ["list"], ["show", "t1"]],
    ids=["add", "list", "show"],
)
def test_a_newer_schema_is_refused(monkeypatch: pytest.MonkeyPatch, args: list[str]) -> None:
    monkeypatch.setenv("DOCKET_TIME_ZONE", "America/New_York")
    folder = prepare_data_dir(get_settings())
    connection = sqlite3.connect(folder / DB_FILENAME)
    connection.execute("PRAGMA user_version = 2")
    connection.close()
    fixed_times(monkeypatch)
    result = run("tasks", *args)
    assert (result.exit_code, result.stdout, result.stderr) == (
        1,
        "",
        "unsupported schema version: 2\n",
    )
