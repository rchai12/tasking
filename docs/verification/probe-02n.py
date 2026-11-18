"""Offline namespace, source preservation and independent coverage-gate checks."""

import argparse
import hashlib
import importlib
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.support import load_script  # noqa: E402
from tests.tooling_boundary_cases import MANIFEST, ROOT, CoverageRunner  # noqa: E402


def oracle() -> None:
    assert list(MANIFEST["modules"]) == [
        "docket_tools/reports.py",
        "docket_tools/acceptance.py",
        "docket_tools/spotcheck.py",
    ]
    assert len(MANIFEST["tests"]) == 11
    with TemporaryDirectory() as folder:
        path = Path(folder) / "coverage.json"
        for group, target in (
            ("tool", "docket_tools/reports.py"),
            ("product", "src/docket/config.py"),
        ):
            for kind in ("missing", "line", "branch"):
                CoverageRunner(f"{group}-{kind}")([f"--cov-report=json:{path}"], Path(folder))
                files = json.loads(path.read_text())["files"]
                if kind == "missing":
                    assert target not in files
                else:
                    field = "missing_lines" if kind == "line" else "missing_branches"
                    assert files[target]["summary"][field] == 1


def relocation() -> None:
    for path, expected in MANIFEST["modules"].items():
        actual = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        assert actual == expected, f"{path}: source digest changed"
        assert not (ROOT / "src/docket" / Path(path).name).exists(), (
            f"legacy source remains: {path}"
        )
        assert importlib.import_module(path[:-3].replace("/", ".")).__file__ == str(ROOT / path)


def wrappers() -> None:
    for script, function, expected in (
        ("accept", "accept", "docket_tools.acceptance"),
        ("check_reports", "check_reports", "docket_tools.reports"),
        ("progress", "put_entry", "docket_tools.reports"),
        ("spot_check", "spot_check", "docket_tools.spotcheck"),
    ):
        actual = getattr(load_script(script), function).__module__
        assert actual == expected, f"{script}: expected {expected}; actual {actual}"


def gates() -> None:
    check = load_script("check")
    for gap in (
        "healthy",
        "tool-missing",
        "tool-line",
        "tool-branch",
        "product-missing",
        "product-line",
        "product-branch",
    ):
        with TemporaryDirectory() as folder, redirect_stdout(io.StringIO()) as output:
            result = check.main(["--quiet", "--log-dir", folder], run=CoverageRunner(gap))
        expected = 0 if gap == "healthy" else 1
        assert result == expected, f"{gap}: expected exit {expected}; actual {result}"
        text = output.getvalue()
        if gap.startswith("product"):
            assert "tooling coverage: not run" in text, (
                f"{gap}: tooling did not stop after product failure"
            )
        elif gap.startswith("tool"):
            assert "Check failed at: tooling coverage" in text, f"{gap}: separate gate missing"
        else:
            assert "tooling coverage: passed" in text, "healthy: separate tooling gate missing"


def imports() -> None:
    from tests.tooling_boundary_cases import normalized_test

    for path, expected in MANIFEST["tests"].items():
        old, actual = normalized_test(ROOT / path)
        assert not old, f"{path}: legacy imports {old}"
        assert actual == expected, f"{path}: cases or assertions changed"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--oracle-only", action="store_true")
    args = parser.parse_args()
    oracle()
    print("tooling coverage oracle ok")
    failures = 0
    if not args.oracle_only:
        for name, check in (
            ("unchanged relocation", relocation),
            ("script bindings", wrappers),
            ("independent gates", gates),
            ("preserved tests", imports),
        ):
            try:
                check()
                print(f"{name} ok")
            except Exception as error:
                print(f"{name} FAIL: {type(error).__name__}: {error}")
                failures += 1
    print(f"FAILURES {failures}")
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
