"""Phase 5f: `docket status` prints the reminder loop's stored row."""

import pytest

from docket.config import get_settings
from docket.store import open_store
from tests.support import fixed_times, run

MARK = "Phase 5f given test: remove this marker when the loop records its status"
COLUMNS = "number, pass_at, sent, digest, reminders_failures, digest_failures, skipped"


@pytest.fixture(autouse=True)
def home(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCKET_TIME_ZONE", "America/New_York")


def plant(row: tuple) -> None:
    with open_store(get_settings()) as store:
        store._connection.execute(
            f"INSERT INTO loop_status ({COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?)", row
        )


def test_status_before_any_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    fixed_times(monkeypatch, "2026-11-20T16:00:00+00:00")
    result = run("status")
    assert (result.exit_code, result.stdout, result.stderr) == (
        0,
        "Reminder loop: no pass recorded yet\n",
        "",
    )


@pytest.mark.parametrize(
    ("now", "first"),
    [
        ("2026-11-20T16:00:30+00:00", "Reminder loop: running, last pass Fri Nov 20 11:00 EST"),
        ("2026-11-20T16:05:01+00:00", "Reminder loop: not running, last pass Fri Nov 20 11:00 EST"),
    ],
    ids=["running", "stale"],
)
def test_status_prints_the_stored_row(
    monkeypatch: pytest.MonkeyPatch, now: str, first: str
) -> None:
    plant((1, "2026-11-20T16:00:00.000000+00:00", 2, 0, 0, 3, '["t4"]'))
    fixed_times(monkeypatch, now)
    result = run("status")
    assert (result.exit_code, result.stdout, result.stderr) == (
        0,
        f"{first}\nReminders: ok, 2 sent\nDigest: failing for 3 passes\nSkipped tasks: t4\n",
        "",
    )


def test_status_refuses_a_bad_stored_row(monkeypatch: pytest.MonkeyPatch) -> None:
    plant((1, "2026-11-20T16:00:00", 0, 0, 0, 0, "[]"))
    fixed_times(monkeypatch, "2026-11-20T16:00:30+00:00")
    result = run("status")
    assert (result.exit_code, result.stdout, result.stderr) == (
        1,
        "",
        "invalid stored loop status\n",
    )
