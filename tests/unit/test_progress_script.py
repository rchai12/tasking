from pathlib import Path

import pytest

from tests.support import load_script

progress = load_script("progress")
HEAD = "# Progress\n\nOne entry per phase.\n\n"
EARLIER = (
    "## Phase 2d: Serve (2026-11-14)\n"
    "- Tests: 703 -> 732 (given 24)\n"
    "- New public names: None\n"
    "- Changed files: 7\n"
    "- Deviations:\n"
    "  - None\n"
    "- Follow-ups:\n"
    "  - None\n"
)
ENTRY = (
    "## Phase 2e: Phase tooling (2026-11-15)\n"
    "- Tests: 732 -> 790 (given 40)\n"
    "- New public names: `docket.spotcheck`: `mutate`\n"
    "- Changed files: 9\n"
    "- Deviations:\n"
    "  - One handler\n"
    "- Follow-ups:\n"
    "  - Stopped: G3 | 1 failed | a fix to the probe\n"
    "  - Check the log folder\n"
)


def argv(path: Path, *, title: str = "Phase tooling", after: str = "790") -> list[str]:
    return [
        "--file",
        str(path),
        "--phase",
        "2e",
        "--title",
        title,
        "--date",
        "2026-11-15",
        "--tests-before",
        "732",
        "--tests-after",
        after,
        "--given",
        "40",
        "--names",
        "`docket.spotcheck`: `mutate`",
        "--changed",
        "9",
        "--deviation",
        "One handler",
        "--follow-up",
        "Stopped: G3 | 1 failed | a fix to the probe",
        "--follow-up",
        "Check the log folder",
    ]


def test_the_entry_is_appended_then_replaced(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "progress.md"
    path.write_text(HEAD + EARLIER, encoding="utf-8")
    assert progress.main(argv(path, after="760")) == 0
    assert progress.main(argv(path)) == 0
    assert path.read_text(encoding="utf-8") == HEAD + EARLIER + "\n" + ENTRY
    assert capsys.readouterr().out == "Progress entry for Phase 2e written.\n" * 2


def test_no_lists_are_written_as_none(tmp_path: Path) -> None:
    path = tmp_path / "progress.md"
    path.write_text(HEAD + EARLIER, encoding="utf-8")
    plain = argv(path)[: argv(path).index("--deviation")]
    assert progress.main(plain) == 0
    assert path.read_text(encoding="utf-8").endswith(
        "- Deviations:\n  - None\n- Follow-ups:\n  - None\n"
    )


def test_an_entry_out_of_form_changes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "progress.md"
    path.write_text(HEAD + EARLIER, encoding="utf-8")
    assert progress.main(argv(path, title="")) == 2
    assert capsys.readouterr().err == "Error: the entry does not match the progress form\n"
    assert path.read_text(encoding="utf-8") == HEAD + EARLIER
