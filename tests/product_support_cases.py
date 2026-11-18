"""Given preservation inventory for the shared product-test support migration."""

import ast
import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "tests/product_support_manifest.json").read_text())


def digest(node):
    return hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()


def consumer_digest(path):
    tree = ast.parse(path.read_text())
    tree.body = [
        node
        for node in tree.body
        if not isinstance(node, (ast.Import, ast.ImportFrom))
        and not (isinstance(node, ast.FunctionDef) and node.name in {"store", "path", "refused"})
        and not (
            path.name == "test_store_links.py"
            and isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "__all__"
            and isinstance(node.value, ast.List)
            and len(node.value.elts) == 1
            and isinstance(node.value.elts[0], ast.Constant)
            and node.value.elts[0].value == "base_store"
        )
    ]
    return digest(tree)


def seed_digest(path):
    tree = ast.parse(path.read_text())
    fixture = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "store"
    )
    body = fixture.body
    # The old fixture owns a Store context; the new adapter receives the shared fixture instead.
    if len(body) == 1 and isinstance(body[0], ast.With):
        expression = body[0].items[0].context_expr
        if (
            isinstance(expression, ast.Call)
            and isinstance(expression.func, ast.Name)
            and expression.func.id == "Store"
        ):
            body = body[0].body
    module = ast.Module(body=copy.deepcopy(body), type_ignores=[])
    for node in ast.walk(module):
        if isinstance(node, ast.Name) and node.id in {"opened", "base_store"}:
            node.id = "shared"
    return digest(module)


def _run_consumers(paths, *, collect):
    environment = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join((str(ROOT / "src"), str(ROOT))),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
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
            *paths,
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )


def execute_reference_cases():
    return _run_consumers(["tests/integration/test_core_references.py"], collect=False)


def collect_consumers():
    done = _run_consumers(MANIFEST["files"], collect=True)
    assert done.returncode == 0, done.stdout[-1200:] + done.stderr[-500:]
    return sorted(
        line for line in done.stdout.splitlines() if line.startswith("tests/") and "::" in line
    )
