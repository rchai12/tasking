from pathlib import Path

import pytest

from tests.support import fixed_times, run


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (
            ["add", "Synthetic task", "--due", "20261120", "--at", "1700"],
            "--due must be a date like 2026-11-20.\n",
        ),
        (
            ["add", "Synthetic task", "--due", "2026-11-31"],
            "--due must be a date like 2026-11-20.\n",
        ),
        (
            ["edit", "t99", "--due", "2026-11-20", "--at", "24:00"],
            "--at must be a time like 17:00.\n",
        ),
        (["plan", "t99", "20261120", "1700"], "The date must look like 2026-11-20.\n"),
        (["plan", "t99", "2026-11-20", "24:00"], "The start time must look like 14:00.\n"),
    ],
    ids=[
        "add-shape-order",
        "add-invalid-date",
        "edit-before-lookup",
        "plan-date-first",
        "plan-time",
    ],
)
def test_cli_keeps_exact_parse_messages_and_order(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, args, message: str
) -> None:
    monkeypatch.setenv("DOCKET_TIME_ZONE", "UTC")
    monkeypatch.setenv("DOCKET_DATA_DIR", str(tmp_path / "synthetic-data"))
    fixed_times(monkeypatch)
    result = run("tasks", *args)
    assert (result.exit_code, result.stdout, result.stderr) == (1, "", message)
    assert not (tmp_path / "synthetic-data").exists()
