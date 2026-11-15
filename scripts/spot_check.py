"""Change one source line, run the deciding test, and restore the file.

Run it as: .venv/bin/python scripts/spot_check.py MODULE --old TEXT --new TEXT --test ID
"""

import argparse
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from docket.spotcheck import SpotError, spot_check

ROOT = Path(__file__).resolve().parent.parent


def run_pytest(test: str, cwd: Path) -> tuple[int, str]:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    command = [
        sys.executable,
        "-m",
        "pytest",
        test,
        "-q",
        "--tb=line",
        "--no-cov",
        "-p",
        "no:cacheprovider",
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        return 124, "timed out"
    return completed.returncode, completed.stdout


def main(
    argv: list[str] | None = None,
    run: Callable[[str, Path], tuple[int, str]] = run_pytest,
) -> int:
    parser = argparse.ArgumentParser(description="Run one spot check and restore the file.")
    parser.add_argument("module", help="Module path relative to --root.")
    parser.add_argument("--old", required=True, help="Text that must match exactly once.")
    parser.add_argument("--new", required=True, help="Replacement text.")
    parser.add_argument("--test", required=True, help="Pytest id to run.")
    parser.add_argument("--row", help="Spot-check row label, printed before the verdict.")
    parser.add_argument("--root", type=Path, default=ROOT, help="Repository root.")
    options = parser.parse_args(argv)
    module = (options.root / options.module).resolve()
    source = (options.root / "src").resolve()
    if not module.is_relative_to(source):
        print("Error: the module must be under src/", file=sys.stderr)
        return 2

    def _run() -> tuple[int, str]:
        return run(options.test, options.root)

    try:
        found = spot_check(module, options.old, options.new, _run)
    except SpotError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    if options.row:
        print(f"{options.row} {found}")
    else:
        print(found)
    return 0 if found.startswith("fails") else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
