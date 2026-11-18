import os
import subprocess
import sys
import tomllib
from pathlib import Path

from tests.support import load_script
from tests.tooling_boundary_cases import ROOT, CoverageRunner

check = load_script("check")
ENTRY = """\
# Progress

## Phase 9z: Synthetic tooling (2026-11-17)
- Tests: 1 -> 2 (given 1)
- New public names: None
- Changed files: 1
- Deviations:
  - None
- Follow-ups:
  - None
"""


def test_prefixed_gaps_keep_product_messages_and_each_gate_reports_itself(tmp_path: Path, capsys):
    report = {
        "files": {
            "src/docket/config.py": {"summary": {"missing_lines": 1, "missing_branches": 2}},
            "docket_tools/reports.py": {"summary": {"missing_lines": 3, "missing_branches": 4}},
        }
    }
    assert check.coverage_gaps(report, ["config.py"]) == [
        "config.py: 1 lines and 2 branches not covered"
    ]
    assert check.coverage_gaps(report, ["config.py"], prefix="src/docket") == [
        "config.py: 1 lines and 2 branches not covered"
    ]
    assert check.coverage_gaps(report, ["docket_tools/reports.py"], prefix="") == [
        "docket_tools/reports.py: 3 lines and 4 branches not covered"
    ]
    assert check.coverage_gaps({"files": {}}, ["config.py"]) == ["config.py: not measured"]
    assert check.coverage_gaps({"files": {}}, ["docket_tools/reports.py"], prefix="") == [
        "docket_tools/reports.py: not measured"
    ]
    assert (
        check.main(["--quiet", "--log-dir", str(tmp_path)], run=CoverageRunner("product-line")) == 1
    )
    failed = capsys.readouterr().out
    assert "  config.py: 1 lines and 0 branches not covered\n" in failed
    assert "  critical coverage: FAILED\n" in failed
    assert "  tooling coverage: not run\n" in failed
    assert "docket_tools/reports.py:" not in failed
    assert check.main(["--quiet", "--log-dir", str(tmp_path)], run=CoverageRunner("healthy")) == 0
    passed = capsys.readouterr().out
    assert "  critical coverage: passed\n  tooling coverage: passed\nAll checks passed.\n" in passed


def test_progress_and_check_reports_bootstrap_away_from_the_repository(tmp_path: Path) -> None:
    unrelated = tmp_path / "elsewhere"
    unrelated.mkdir()
    synthetic = tmp_path / "synthetic"
    progress = synthetic / "docs" / "progress.md"
    progress.parent.mkdir(parents=True)
    progress.write_text("# Progress\n", encoding="utf-8")
    repo = (ROOT / "docs" / "progress.md").read_bytes()
    environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    written = subprocess.run(
        [
            sys.executable,
            "-I",
            str(ROOT / "scripts" / "progress.py"),
            "--file",
            str(progress),
            "--phase",
            "9z",
            "--title",
            "Synthetic tooling",
            "--date",
            "2026-11-17",
            "--tests-before",
            "1",
            "--tests-after",
            "2",
            "--given",
            "1",
            "--names",
            "None",
            "--changed",
            "1",
        ],
        cwd=unrelated,
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert (written.returncode, written.stdout, written.stderr) == (
        0,
        "Progress entry for Phase 9z written.\n",
        "",
    )
    assert progress.read_text(encoding="utf-8") == ENTRY
    assert (ROOT / "docs" / "progress.md").read_bytes() == repo
    before = sorted(path.relative_to(synthetic).as_posix() for path in synthetic.rglob("*"))
    reported = subprocess.run(
        [
            sys.executable,
            "-I",
            str(ROOT / "scripts" / "check_reports.py"),
            "--root",
            str(synthetic),
        ],
        cwd=unrelated,
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
    )
    after = sorted(path.relative_to(synthetic).as_posix() for path in synthetic.rglob("*"))
    assert (reported.returncode, reported.stdout, reported.stderr) == (0, "Reports OK.\n", "")
    assert after == before


def test_accept_and_spot_wrappers_keep_fakes_and_the_src_boundary(tmp_path: Path, capsys) -> None:
    accept = load_script("accept")
    calls: list[tuple[str, Path]] = []

    def fake_command(command: str, cwd: Path) -> tuple[int, str]:
        calls.append((command, cwd))
        return 0, "synthetic ok\n"

    assert (
        accept.main(["--phase", "2n", "--log-dir", str(tmp_path / "logs")], run=fake_command) == 0
    )
    assert calls
    assert {cwd for _command, cwd in calls} == {accept.ROOT}
    assert capsys.readouterr().out.startswith("A1:")

    spot = load_script("spot_check")
    root = tmp_path / "repo"
    module = root / "src" / "docket" / "example.py"
    module.parent.mkdir(parents=True)
    module.write_text("VALUE = 1\n", encoding="utf-8")
    outside = root / "docket_tools" / "reports.py"
    outside.parent.mkdir(parents=True)
    outside.write_text("VALUE = 1\n", encoding="utf-8")
    ran: list[tuple[str, Path]] = []

    def fake_test(test: str, cwd: Path) -> tuple[int, str]:
        ran.append((test, cwd))
        return 1, "tests/unit/test_example.py:1: AssertionError: assert 1 == 2\n"

    assert (
        spot.main(
            [
                "--root",
                str(root),
                "src/docket/example.py",
                "--old",
                "VALUE = 1",
                "--new",
                "VALUE = 2",
                "--test",
                "tests/unit/test_example.py::test_one",
            ],
            run=fake_test,
        )
        == 0
    )
    assert module.read_text(encoding="utf-8") == "VALUE = 1\n"
    assert ran == [("tests/unit/test_example.py::test_one", root)]
    ran.clear()
    assert (
        spot.main(
            [
                "--root",
                str(root),
                "docket_tools/reports.py",
                "--old",
                "VALUE = 1",
                "--new",
                "VALUE = 2",
                "--test",
                "tests/unit/test_example.py::test_one",
            ],
            run=fake_test,
        )
        == 2
    )
    assert ran == []
    assert outside.read_text(encoding="utf-8") == "VALUE = 1\n"
    assert capsys.readouterr().err == "Error: the module must be under src/\n"


def test_tooling_section_and_first_keep_no_cov_while_the_full_run_measures_both(
    tmp_path: Path,
) -> None:
    section: list[list[str]] = []

    def record(command: list[str], _cwd: Path, log: Path | None = None) -> int:
        section.append(command)
        if log is not None:
            log.write_text("synthetic\n", encoding="utf-8")
        return 0

    assert check.main(["--section", "tooling", "--log-dir", str(tmp_path)], run=record) == 0
    assert "--no-cov" in section[0]
    assert "tests/unit/test_tooling_boundary.py" in section[0]
    assert "tests/unit/test_tooling_boundary_more.py" in section[0]
    core: list[list[str]] = []

    def record_core(command: list[str], _cwd: Path, _log: Path | None = None) -> int:
        core.append(command)
        return 0

    assert check.main(["--section", "core"], run=record_core) == 0
    assert "--no-cov" in core[0]
    assert "tests/unit/test_tooling_boundary_more.py" not in core[0]

    seen: list[list[str]] = []
    runner = CoverageRunner("healthy")

    def record_first(command: list[str], cwd: Path, log: Path | None = None) -> int:
        seen.append(command)
        return runner(command, cwd, log)

    assert (
        check.main(["--quiet", "--first", "tooling", "--log-dir", str(tmp_path)], run=record_first)
        == 0
    )
    first = next(command for command in seen if "--no-cov" in command)
    full = next(
        command
        for command in seen
        if "-m" in command and "pytest" in command and "--no-cov" not in command
    )
    assert "tests/unit/test_tooling_boundary.py" in first
    assert "tests/unit/test_tooling_boundary_more.py" in first
    assert "--no-cov" not in full
    options = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert "--cov=docket" in options["tool"]["pytest"]["ini_options"]["addopts"]
    assert "--cov=docket_tools" in options["tool"]["pytest"]["ini_options"]["addopts"]


def test_an_early_lint_failure_leaves_both_coverage_gates_unrun(tmp_path: Path, capsys) -> None:
    def fail_lint(command: list[str], _cwd: Path, log: Path | None = None) -> int:
        if log is not None:
            log.write_text("lint failed\n", encoding="utf-8")
        return 1 if "check" in command else 0

    assert check.main(["--quiet", "--log-dir", str(tmp_path)], run=fail_lint) == 1
    output = capsys.readouterr().out
    assert "  critical coverage: not run\n" in output
    assert "  tooling coverage: not run\n" in output
    assert "Check failed at: lint\n" in output
