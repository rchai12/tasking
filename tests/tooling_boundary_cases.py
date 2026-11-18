"""Given inventories and fake coverage, independent of the implementation's gate lists."""

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "tests/tooling_boundary_manifest.json").read_text())
IMPORTS = {
    "docket.reports": "docket_tools.reports",
    "docket.acceptance": "docket_tools.acceptance",
    "docket.spotcheck": "docket_tools.spotcheck",
}


def normalized_test(path):
    tree = ast.parse(path.read_text())
    old = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in IMPORTS:
            old.append(node.module)
            node.module = IMPORTS[node.module]
    return old, hashlib.sha256(ast.dump(tree, include_attributes=False).encode()).hexdigest()


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
                paths = [f"src/docket/{name}" for name in MANIFEST["product_critical"]]
                paths += list(MANIFEST["modules"])
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
