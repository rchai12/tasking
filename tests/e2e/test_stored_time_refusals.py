import sqlite3

import pytest

from docket import core
from docket.config import get_settings
from docket.store import open_store
from tests.reference_cases import NOW, snapshot
from tests.support import fixed_times, run


@pytest.mark.parametrize("command", ["list", "show"])
def test_cli_reports_only_the_task_id_for_corrupt_stored_time(
    monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    monkeypatch.setenv("DOCKET_TIME_ZONE", "UTC")
    settings = get_settings()
    fixed_times(monkeypatch, NOW, NOW)
    with open_store(settings) as store:
        core.create_task(store, title="First private synthetic title", source="owner")
        core.create_task(store, title="Second private synthetic title", source="owner")
    path = settings.data_dir / "docket.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("UPDATE tasks SET created_at='private-invalid-time' WHERE number=2")
    before = snapshot(path)
    fixed_times(monkeypatch, NOW)
    result = run("tasks", "list") if command == "list" else run("tasks", "show", "t2")
    assert (result.exit_code, result.stdout, result.stderr) == (
        1,
        "",
        "invalid stored task time: t2\n",
    )
    assert snapshot(path) == before
