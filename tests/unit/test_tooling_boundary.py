import ast
import hashlib
import importlib
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from tests.support import load_script
from tests.tooling_boundary_cases import MANIFEST, ROOT, CoverageRunner, normalized_test


@pytest.mark.parametrize("path", list(MANIFEST["modules"]))
def test_moved_modules_are_byte_identical_and_old_sources_are_removed(path: str) -> None:
    assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == MANIFEST["modules"][path]
    assert not (ROOT / "src/docket" / Path(path).name).exists()
    assert importlib.import_module(path[:-3].replace("/", ".")).__file__ == str(ROOT / path)


@pytest.mark.parametrize("path", list(MANIFEST["tests"]))
def test_prior_test_cases_and_assertions_only_change_import_namespace(path: str) -> None:
    old, digest = normalized_test(ROOT / path)
    assert old == [], f"old tooling import still present in {path}"
    assert digest == MANIFEST["tests"][path]


def test_product_and_tooling_gate_lists_are_separate_and_complete() -> None:
    check = load_script("check")
    assert check.read_critical(check.CRITICAL_FILE.read_text()) == MANIFEST["product_critical"]
    assert check.TOOLING_FILE == ROOT / "scripts/tooling_modules.txt"
    assert check.read_critical(check.TOOLING_FILE.read_text()) == [
        "docket_tools/reports.py",
        "docket_tools/acceptance.py",
        "docket_tools/spotcheck.py",
    ]
    assert check.TOOLING_COVERAGE_STEP == "tooling coverage"


@pytest.mark.parametrize(
    "gap",
    [
        "healthy",
        "tool-missing",
        "tool-line",
        "tool-branch",
        "product-missing",
        "product-line",
        "product-branch",
    ],
)
def test_each_coverage_gate_refuses_missing_lines_and_branches_independently(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], gap: str
) -> None:
    check = load_script("check")
    result = check.main(["--quiet", "--log-dir", str(tmp_path)], run=CoverageRunner(gap))
    output = capsys.readouterr().out
    assert result == (0 if gap == "healthy" else 1)
    if gap.startswith("product"):
        assert "  critical coverage: FAILED\n" in output
        assert "  tooling coverage: not run\n" in output
        assert "Check failed at: critical coverage\n" in output
    else:
        assert "  critical coverage: passed\n" in output
        assert f"  tooling coverage: {'passed' if gap == 'healthy' else 'FAILED'}\n" in output
        assert (
            "All checks passed.\n" if gap == "healthy" else "Check failed at: tooling coverage\n"
        ) in output


@pytest.mark.parametrize(
    ("script", "name", "module"),
    [
        ("accept", "accept", "docket_tools.acceptance"),
        ("check_reports", "check_reports", "docket_tools.reports"),
        ("progress", "put_entry", "docket_tools.reports"),
        ("spot_check", "spot_check", "docket_tools.spotcheck"),
    ],
)
def test_command_wrappers_bind_repository_tooling(script: str, name: str, module: str) -> None:
    assert getattr(load_script(script), name).__module__ == module


@pytest.mark.parametrize("script", ["accept", "check_reports", "progress", "spot_check"])
def test_direct_commands_bootstrap_from_an_unrelated_directory(tmp_path: Path, script: str) -> None:
    environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    done = subprocess.run(
        [sys.executable, "-I", str(ROOT / "scripts" / f"{script}.py"), "--help"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert (done.returncode, done.stderr) == (0, "")
    assert done.stdout.startswith("usage:")


def test_packaging_coverage_and_section_configuration_keeps_the_boundary() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert config["tool"]["setuptools"]["packages"]["find"]["where"] == ["src"]
    options = config["tool"]["pytest"]["ini_options"]["addopts"].split()
    assert {value for value in options if value.startswith("--cov=")} == {
        "--cov=docket",
        "--cov=docket_tools",
    }
    assert "--cov-branch" in options
    assert config["tool"]["coverage"]["report"]["fail_under"] == 90
    check = load_script("check")
    sections = check.read_sections((ROOT / "tests/sections.toml").read_text())
    assert check.section_of("unit/test_tooling_boundary.py", sections) == "tooling"


def test_product_source_has_no_tooling_imports_or_legacy_shims() -> None:
    for path in (ROOT / "src/docket").rglob("*.py"):
        assert path.name not in {"reports.py", "acceptance.py", "spotcheck.py"}
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith("docket_tools")
            elif isinstance(node, ast.Import):
                assert all(not name.name.startswith("docket_tools") for name in node.names)
    assert (ROOT / "docket_tools/__init__.py").read_bytes() == b""


def test_src_only_product_runs_without_repository_tooling(tmp_path: Path) -> None:
    source = tmp_path / "src"
    shutil.copytree(
        ROOT / "src/docket", source / "docket", ignore=shutil.ignore_patterns("__pycache__")
    )
    program = """
import importlib.util, socket, sys
from pathlib import Path
def blocked(*args, **kwargs):
    raise AssertionError("unexpected network")
socket.socket.connect = blocked
socket.getaddrinfo = blocked
import keyring.core
from keyring.backends import fail
keyring.core._keyring_backend = fail.Keyring()
sys.path.insert(0, sys.argv[1])
import docket
assert Path(docket.__file__).resolve().parent == Path(sys.argv[1]) / "docket"
assert importlib.util.find_spec("docket_tools") is None
from docket.cli import app
from typer.testing import CliRunner
result = CliRunner().invoke(app, ["version"])
assert (result.exit_code, result.stdout) == (0, "docket 0.1.0\\n")
for name in ("docket.reports", "docket.acceptance", "docket.spotcheck"):
    assert importlib.util.find_spec(name) is None
print("src-only product ok")
"""
    done = subprocess.run(
        [sys.executable, "-I", "-c", program, str(source)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert (done.returncode, done.stdout, done.stderr) == (0, "src-only product ok\n", "")
