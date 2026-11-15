"""Run a phase spec's acceptance commands, or a guide's gates, and print a digest.

Run it as: .venv/bin/python scripts/accept.py --phase ID [--guide]
"""

import argparse
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from docket.acceptance import accept, read_rows
from docket.reports import PHASE_MESSAGE

ROOT = Path(__file__).resolve().parent.parent
_PHASE = re.compile(r"^(?:0|[1-9][0-9]*)[a-z]?$")


def run_shell(command: str, cwd: Path) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            ["/bin/zsh", "-c", command],
            cwd=cwd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=1800,
        )
    except subprocess.TimeoutExpired:
        return 124, "timed out"
    return completed.returncode, completed.stdout


def main(
    argv: list[str] | None = None,
    run: Callable[[str, Path], tuple[int, str]] = run_shell,
) -> int:
    parser = argparse.ArgumentParser(description="Run a phase's acceptance commands.")
    parser.add_argument("--phase", required=True, help="Phase id, such as 2e.")
    parser.add_argument(
        "--guide",
        action="store_true",
        help="Read the verification guide instead of the spec.",
    )
    parser.add_argument("--root", type=Path, default=ROOT, help="Repository root.")
    parser.add_argument(
        "--log-dir",
        type=Path,
        help="Log folder (default: docket-accept-<id> in the temporary directory).",
    )
    options = parser.parse_args(argv)
    if _PHASE.fullmatch(options.phase) is None:
        print(f"Error: {PHASE_MESSAGE}", file=sys.stderr)
        return 2
    path = _phase_file(options.root, options.phase, options.guide)
    if path is None:
        kind = "guide" if options.guide else "spec"
        print(f"Error: no {kind} for phase {options.phase}", file=sys.stderr)
        return 2
    text = path.read_text(encoding="utf-8")
    if options.guide:
        rows = read_rows(text, "2. Gates") + read_rows(text, "5. Searches")
    else:
        rows = read_rows(text, "Acceptance")
    log_dir = options.log_dir
    if log_dir is None:
        log_dir = Path(tempfile.gettempdir()) / f"docket-accept-{options.phase}"

    def _run(command: str) -> tuple[int, str]:
        return run(command, options.root)

    for line in accept(rows, _run, log_dir):
        print(line)
    return 0


def _phase_file(root: Path, phase: str, guide: bool) -> Path | None:
    letter = phase[-1] if phase[-1].isalpha() else ""
    number = phase[:-1] if letter else phase
    padded = f"{int(number):02d}{letter}"
    folder = root / "docs" / ("verification" if guide else "phases")
    matches = sorted(folder.glob(f"phase-{padded}-*.md"))
    if len(matches) == 1:
        return matches[0]
    return None


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
