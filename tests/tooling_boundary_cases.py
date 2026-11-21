"""Fake coverage built from the gate lists in scripts/."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _listed(name: str) -> list[str]:
    lines = (ROOT / "scripts" / name).read_text().splitlines()
    return [line.split("#", 1)[0].strip() for line in lines if line.split("#", 1)[0].strip()]


class CoverageRunner:
    def __init__(self, gap="healthy"):
        self.gap = gap

    def __call__(self, command, cwd, log=None):
        if log is not None:
            log.write_text("synthetic command ok\n")
        for arg in command:
            if arg.startswith("--junitxml="):
                Path(arg.split("=", 1)[1]).write_text(
                    '<testsuite><testcase classname="tests.unit.test_tooling_boundary" '
                    'name="synthetic"/></testsuite>'
                )
            if arg.startswith("--cov-report=json:"):
                paths = [f"src/docket/{name}" for name in _listed("critical_modules.txt")]
                paths += _listed("tooling_modules.txt")
                # Legacy entries keep baseline product coverage healthy to isolate the new gate.
                paths += [
                    "src/docket/reports.py",
                    "src/docket/acceptance.py",
                    "src/docket/spotcheck.py",
                ]
                files = {
                    path: {"summary": {"missing_lines": 0, "missing_branches": 0}} for path in paths
                }
                if self.gap != "healthy":
                    group, kind = self.gap.split("-")
                    target = (
                        "docket_tools/reports.py" if group == "tool" else "src/docket/config.py"
                    )
                    if kind == "missing":
                        del files[target]
                    else:
                        files[target]["summary"][
                            "missing_lines" if kind == "line" else "missing_branches"
                        ] = 1
                Path(arg.split(":", 1)[1]).write_text(json.dumps({"files": files}))
        return 0
