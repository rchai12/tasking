"""Preserve old bytes, or named AST contracts outside an explicitly migrated feature boundary."""

import ast
import copy
import hashlib
from pathlib import Path


def ast_nodes(path: Path) -> dict[str, ast.AST]:
    result = {}
    for index, node in enumerate(ast.parse(path.read_text()).body):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(node, ast.ClassDef):
            header = copy.deepcopy(node)
            header.body = []
            result[node.name] = header
            for child_index, child in enumerate(node.body):
                name = getattr(child, "name", str(child_index))
                result[node.name + "." + name] = child
        else:
            name = getattr(node, "name", None)
            if name is None and isinstance(node, ast.Assign):
                name = ast.unparse(node.targets[0])
            if name is None and isinstance(node, ast.AnnAssign):
                name = ast.unparse(node.target)
            result[name or "node:" + str(index)] = node
    return result


def ast_hash(node: ast.AST, *, signature: bool = False) -> str:
    value = copy.deepcopy(node)
    if signature:
        value.body = []
    return hashlib.sha256(ast.dump(value, include_attributes=False).encode()).hexdigest()


def import_atoms(path: Path) -> set[tuple]:
    atoms = set()
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.Import):
            atoms.update(("import", alias.name, alias.asname) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            atoms.update(("from", node.module, alias.name, alias.asname) for alias in node.names)
    return atoms


def assert_preserved(path: Path, expected: str | dict) -> None:
    if isinstance(expected, str):
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, str(path)
        return
    assert set(expected) == {"stable_nodes", "mutable_signatures", "imports"}
    assert set(map(tuple, expected["imports"])) <= import_atoms(path), str(path) + ":imports"
    nodes = ast_nodes(path)
    for name, digest in expected["stable_nodes"].items():
        assert name in nodes and ast_hash(nodes[name]) == digest, str(path) + ":" + name
    for name, digest in expected["mutable_signatures"].items():
        assert name in nodes and ast_hash(nodes[name], signature=True) == digest, (
            str(path) + ":" + name
        )
