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


def collect_consumers():
    environment = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join((str(ROOT / "src"), str(ROOT))),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "--no-cov",
            "-q",
            "-p",
            "no:cacheprovider",
            *MANIFEST["files"],
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert done.returncode == 0, done.stdout[-1200:] + done.stderr[-500:]
    return sorted(
        line for line in done.stdout.splitlines() if line.startswith("tests/") and "::" in line
    )
