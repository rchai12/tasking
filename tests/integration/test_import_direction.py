"""Phase 5c: the pure planner stands alone and no import is hidden to dodge a cycle."""

import ast
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from docket.deadlines import Deadline

MARK = "Phase 5c given test: remove this marker when the import direction is one way"
PACKAGE = Path(__file__).parents[2] / "src" / "docket"
# The one import kept inside a function: the MCP SDK loads only for `docket mcp serve`.
ALLOWED_INNER = [("cli.py", "docket.mcp_server.server")]


def modules() -> list[str]:
    names = []
    for path in sorted(PACKAGE.rglob("*.py")):
        parts = path.relative_to(PACKAGE.parent).with_suffix("").parts
        names.append(".".join(parts[:-1] if parts[-1] == "__init__" else parts))
    return names


def module_path(name: str) -> Path:
    path = PACKAGE.parent.joinpath(*name.split("."))
    return path / "__init__.py" if path.is_dir() else path.with_suffix(".py")


def docket_imports(name: str) -> list[tuple[str, bool]]:
    """Each docket module the source imports, and whether the import is at module level."""
    tree = ast.parse(module_path(name).read_text())
    top = set(map(id, tree.body))
    known = set(modules())
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            targets = [
                f"{node.module}.{alias.name}"
                if f"{node.module}.{alias.name}" in known
                else node.module
                for alias in node.names
            ]
        else:
            continue
        for target in targets:
            if target.split(".")[0] == "docket" and target != "docket":
                found.append((target, id(node) in top))
    return found


def node(name: str) -> str:
    """The store's private parts are one node with the store."""
    return "docket.store" if name.startswith("docket._store_") else name


def test_every_module_imports_alone_in_a_fresh_interpreter() -> None:
    source = str(PACKAGE.parent)
    started = {
        name: subprocess.Popen(
            [
                sys.executable,
                "-I",
                "-c",
                f"import sys; sys.path.insert(0, {source!r}); import {name}",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        for name in modules()
    }
    failed = {}
    for name, process in started.items():
        _, error = process.communicate(timeout=60)
        if process.returncode:
            failed[name] = (error.strip().splitlines() or ["no output"])[-1]
    assert failed == {}


@pytest.mark.xfail(strict=True, reason=MARK)
def test_no_docket_import_is_hidden_in_a_function_or_a_type_check() -> None:
    inner = [
        (str(module_path(name).relative_to(PACKAGE)), target)
        for name in modules()
        for target, at_top in docket_imports(name)
        if not at_top
    ]
    assert inner == ALLOWED_INNER


@pytest.mark.xfail(strict=True, reason=MARK)
def test_the_import_graph_has_no_cycle() -> None:
    edges: dict[str, set[str]] = {}
    for name in modules():
        for target, _ in docket_imports(name):
            if (str(module_path(name).relative_to(PACKAGE)), target) in ALLOWED_INNER:
                continue
            if node(name) != node(target):
                edges.setdefault(node(name), set()).add(node(target))
    done: set[str] = set()

    def visit(name: str, path: tuple[str, ...]) -> None:
        if name in path:
            raise AssertionError(" -> ".join(path[path.index(name) :] + (name,)))
        if name in done:
            return
        for target in sorted(edges.get(name, ())):
            visit(target, path + (name,))
        done.add(name)

    for name in sorted(edges):
        visit(name, ())


@pytest.mark.xfail(strict=True, reason=MARK)
def test_the_planner_imports_only_deadlines_and_domain() -> None:
    assert sorted({target for target, _ in docket_imports("docket.reminder_plan")}) == [
        "docket.deadlines",
        "docket.domain",
    ]


@pytest.mark.xfail(strict=True, reason=MARK)
def test_the_planner_needs_no_stored_task() -> None:
    from docket import reminder_plan

    task = SimpleNamespace(
        state="open",
        deadline=Deadline(datetime(2026, 11, 1, 22, tzinfo=UTC), "America/New_York", True),
        work=None,
    )
    planned = reminder_plan.plan_reminders(task, datetime(2026, 11, 1, 12, tzinfo=UTC))
    assert [(row.kind, row.fire_at.isoformat()) for row in planned] == [
        ("before", "2026-11-01T21:00:00+00:00"),
        ("due", "2026-11-01T22:00:00+00:00"),
        ("late", "2026-11-01T22:30:00+00:00"),
        ("late", "2026-11-01T23:00:00+00:00"),
        ("late", "2026-11-02T00:00:00+00:00"),
        ("late", "2026-11-02T01:00:00+00:00"),
        ("late", "2026-11-02T02:00:00+00:00"),
        ("late", "2026-11-02T06:00:00+00:00"),
        ("late", "2026-11-02T10:00:00+00:00"),
    ]


@pytest.mark.xfail(strict=True, reason=MARK)
@pytest.mark.parametrize(
    ("name", "home"),
    [
        ("plan_reminders", "reminder_plan"),
        ("PlannedReminder", "reminder_plan"),
        ("LATE_MINUTES", "reminder_plan"),
        ("notice_text", "views"),
        ("digest_heading", "views"),
    ],
)
def test_moved_names_stay_reachable_from_reminders(name: str, home: str) -> None:
    import importlib

    from docket import reminders

    assert getattr(reminders, name) is getattr(importlib.import_module(f"docket.{home}"), name)


@pytest.mark.xfail(strict=True, reason=MARK)
def test_core_and_the_store_plan_through_the_planner_module() -> None:
    for name in ("docket.core", "docket.store", "docket._store_migrate"):
        targets = {target for target, _ in docket_imports(name)}
        assert "docket.reminders" not in targets, name
        assert "docket.reminder_plan" in targets, name
