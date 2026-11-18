"""Given inventory checks for the four Phase 2p product-test families."""

import ast
import hashlib
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

from tests.preservation_cases import assert_preserved

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "tests/product_consolidation_manifest.json").read_text())
FAMILIES = MANIFEST["families"]


def imports(path: Path) -> list[list[str | None]]:
    values = set()
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.Import):
            values.update(("import", alias.name, alias.asname) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            values.update(
                ("from", "." * node.level + (node.module or ""), alias.name, alias.asname)
                for alias in node.names
            )
    return [list(value) for value in sorted(values, key=repr)]


def bodies(path: Path) -> list[str]:
    return sorted(
        ast.dump(node, include_attributes=False)
        for node in ast.parse(path.read_text()).body
        if not isinstance(node, (ast.Import, ast.ImportFrom))
    )


def run_pytest(arguments: list[str], *, collect: bool) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            *(["--collect-only"] if collect else []),
            "--no-cov",
            "-q",
            "-p",
            "no:cacheprovider",
            *(argument for argument in arguments if argument != "-q"),
        ],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": os.pathsep.join((str(ROOT / "src"), str(ROOT)))},
        capture_output=True,
        text=True,
        timeout=30,
    )


def collected(arguments: list[str]) -> list[str]:
    done = run_pytest(arguments, collect=True)
    assert done.returncode == 0, done.stdout[-1600:] + done.stderr[-500:]
    return sorted(
        line for line in done.stdout.splitlines() if line.startswith("tests/") and "::" in line
    )


def check_family(main: str) -> None:
    family = FAMILIES[main]
    assert not (ROOT / family["retired"]).exists(), family["retired"]
    assert bodies(ROOT / main) == family["bodies"], main
    assert imports(ROOT / main) == family["imports"], main


def check_collection(main: str) -> None:
    assert collected([main]) == sorted(FAMILIES[main]["mapping"].values()), main


def check_execution(main: str) -> None:
    family = FAMILIES[main]
    selectors = [main + "::" + name for name in family["moved_functions"]]
    done = run_pytest(selectors, collect=False)
    assert done.returncode == 0, done.stdout[-1600:] + done.stderr[-500:]
    count = sum(old.startswith(family["retired"] + "::") for old in family["mapping"])
    assert f"{count} passed" in done.stdout, done.stdout[-1600:]


def check_document(path: str) -> None:
    expected = MANIFEST["documents"][path]["after_sha256"]
    assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected, path


def check_selection(index: int) -> None:
    selection = MANIFEST["selections"][index]
    # Parse the actual migrated command, so leaving a stale command cannot pass this check.
    assert any(
        "`" + selection["after"] + "`" in (ROOT / path).read_text()
        for path in MANIFEST["documents"]
    ), selection["before"]
    cases = collected(shlex.split(selection["after"])[3:])
    family_cases = [case for case in cases if case.split("::")[0] in FAMILIES]
    assert family_cases == selection["expected_family_cases"], selection["before"]


def check_frozen() -> None:
    for path, expected in MANIFEST["frozen"].items():
        assert_preserved(ROOT / path, expected)


def check_oracle() -> None:
    mapping = {old: new for family in FAMILIES.values() for old, new in family["mapping"].items()}
    assert len(mapping) == 78
    assert len(set(mapping.values())) == 78
    assert sum(old != new for old, new in mapping.items()) == 8
    assert [len(family["mapping"]) for family in FAMILIES.values()] == [13, 7, 9, 49]
    assert [len(row["expected_family_cases"]) for row in MANIFEST["selections"]] == [32, 46, 54, 24]
