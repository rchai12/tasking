"""Phase 5d: each closed list and each shared bound has one source, in `domain`."""

import ast
import json
import subprocess
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import get_args, get_type_hints

import pytest
from fastapi.testclient import TestClient

from docket import domain
from docket.store import Store
from tests.integration.test_web import Opened

MARK = "Phase 5d given test: remove this marker when each closed list has one source"
PACKAGE = Path(__file__).parents[2] / "src" / "docket"
KEY = "synthetic-key-5d"
# Lists another module may spell out: the planner's kind type and the notice text per kind.
ALLOWED_LISTS = [("reminder_plan.py", "Literal"), ("views.py", "_NOTICE")]
# Run in a fresh interpreter: change domain's values first, then import the modules that
# derive from them, and print what they derived.
CHILD = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
from docket import domain
domain.DUE_WINDOW_MINUTES = 45
domain.REMINDER_KINDS = ("late", "due", "due_soon", "before", "start")
domain.API_CLIENTS = ("synthetic-client",)
from docket import clients, deadlines, reminder_plan
print(json.dumps({
    "due_window": deadlines.DUE_WINDOW.total_seconds() / 60,
    "late_minutes": list(reminder_plan.LATE_MINUTES),
    "kind_order": reminder_plan._KIND_ORDER,
    "clients": list(clients.CLIENTS),
}))
"""


def sources() -> list[tuple[str, ast.Module]]:
    return [
        (str(path.relative_to(PACKAGE)), ast.parse(path.read_text()))
        for path in sorted(PACKAGE.rglob("*.py"))
    ]


def assigned(tree: ast.Module, name: str) -> ast.expr:
    for node in tree.body:
        if isinstance(node, ast.Assign) and [ast.unparse(t) for t in node.targets] == [name]:
            return node.value
    raise AssertionError(f"{name} is not assigned at module level")


def allowed_nodes(tree: ast.Module, file: str) -> set[int]:
    """The literal lists `ALLOWED_LISTS` names, which may spell out a closed list."""
    found: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and (file, ast.unparse(node.value)) in ALLOWED_LISTS:
            found.add(id(node.slice))
        if isinstance(node, ast.Assign) and any(
            (file, ast.unparse(target)) in ALLOWED_LISTS for target in node.targets
        ):
            found.add(id(node.value))
    return found


def listed_words(node: ast.AST) -> list[str] | None:
    """The strings of a literal tuple, list, set or dict's keys, if all are strings."""
    if isinstance(node, ast.Dict):
        items: list[ast.expr | None] = list(node.keys)
    elif isinstance(node, ast.Tuple | ast.List | ast.Set):
        items = list(node.elts)
    else:
        return None
    if items and all(isinstance(i, ast.Constant) and isinstance(i.value, str) for i in items):
        return [item.value for item in items]  # type: ignore[union-attr]
    return None


def is_email(node: ast.AST | None) -> bool:
    return isinstance(node, ast.Constant) and node.value == "email"


def email_client_uses(tree: ast.Module) -> list[int]:
    """Lines where `"email"` stands for the API client, never for a task's source."""
    lines = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            sides = [node.left, node.comparators[0]]
            if any(ast.unparse(s) == "client" for s in sides) and any(map(is_email, sides)):
                lines.append(node.lineno)
        elif isinstance(node, ast.Call):
            if any(k.arg == "client" and is_email(k.value) for k in node.keywords):
                lines.append(node.lineno)
            elif ast.unparse(node.func).endswith("request_key") and is_email(
                node.args[0] if node.args else None
            ):
                lines.append(node.lineno)
        elif isinstance(node, ast.Assign) and any(
            ast.unparse(t).endswith("CLIENTS") for t in node.targets
        ):
            if any(is_email(part) for part in ast.walk(node.value)):
                lines.append(node.lineno)
    return lines


@pytest.mark.parametrize(
    ("name", "spelled", "value"),
    [
        ("OPEN_STATES", "('open', 'in_progress')", ("open", "in_progress")),
        ("ENDED_STATES", "('done', 'cancelled')", ("done", "cancelled")),
        ("WORK_KINDS", "('start',)", ("start",)),
        (
            "DEADLINE_KINDS",
            "('before', 'due_soon', 'due', 'late')",
            ("before", "due_soon", "due", "late"),
        ),
        (
            "REMINDER_KINDS",
            "WORK_KINDS + DEADLINE_KINDS",
            ("start", "before", "due_soon", "due", "late"),
        ),
        ("DUE_WINDOW_MINUTES", "30", 30),
        ("EMAIL_CLIENT", "'email'", "email"),
        ("API_CLIENTS", "(EMAIL_CLIENT,)", ("email",)),
        ("CORE_CLIENTS", "(EMAIL_CLIENT, 'agent')", ("email", "agent")),
    ],
    ids=[
        "open-states",
        "ended-states",
        "work-kinds",
        "deadline-kinds",
        "reminder-kinds",
        "due-window",
        "email-client",
        "api-clients",
        "core-clients",
    ],
)
def test_domain_spells_out_each_list_once(name: str, spelled: str, value: object) -> None:
    tree = ast.parse((PACKAGE / "domain.py").read_text())
    assert (ast.unparse(assigned(tree, name)), getattr(domain, name)) == (spelled, value)


def test_the_states_split_into_open_and_ended() -> None:
    assert tuple(domain.STATE_LABELS) == domain.OPEN_STATES + domain.ENDED_STATES


@pytest.mark.parametrize(
    ("key", "valid"),
    [
        (None, False),
        (7, False),
        (b"k", False),
        ("", False),
        ("k", True),
        ("k" * 200, True),
        ("k" * 201, False),
    ],
    ids=["none", "number", "bytes", "empty", "one", "two-hundred", "two-hundred-one"],
)
def test_valid_request_key(key: object, valid: bool) -> None:
    assert domain.valid_request_key(key) is valid


def refuse_core(path: Path) -> object:
    from docket import core

    with Store(path) as store, pytest.raises(core.CoreError) as raised:
        core.change_state_once(store, "t1", "start", client="agent", key=KEY, request={})
    return raised.value.code


def refuse_intake(path: Path) -> object:
    from docket import intake

    with Store(path) as store:
        return intake.accept_task(store, client="email", key=KEY, body={}).body


def refuse_web(path: Path) -> object:
    from docket import web

    app = web.create_app(open_store=Opened(path), tokens={"synthetic-token-5d": "email"}, port=8767)
    headers = {"Authorization": "Bearer synthetic-token-5d", "Idempotency-Key": KEY}
    with TestClient(app, base_url="http://127.0.0.1:8767") as client:
        response = client.post("/tasks", content=b"{", headers=headers)
    return response.status_code, response.json()


def refuse_store(path: Path) -> object:
    from docket.store import StoreError

    with Store(path) as store, store.transaction(), pytest.raises(StoreError) as raised:
        store.queue_digest(
            date(2026, 11, 2), ("t1",), key=KEY, at=datetime(2026, 11, 2, 13, tzinfo=UTC)
        )
    return str(raised.value)


@pytest.mark.parametrize(
    ("refuse", "answer"),
    [
        (refuse_core, "invalid_key"),
        (refuse_intake, {"error": "missing_key"}),
        (refuse_web, (400, {"error": "missing_key"})),
        (refuse_store, "invalid digest key"),
    ],
    ids=["core", "intake", "web", "store"],
)
def test_each_key_check_asks_domain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, refuse, answer: object
) -> None:
    asked: list[object] = []

    def refused(key: object) -> bool:
        asked.append(key)
        return False

    monkeypatch.setattr(domain, "valid_request_key", refused, raising=False)
    assert (refuse(tmp_path / "docket.sqlite3"), asked) == (answer, [KEY])


def test_derived_values_follow_domain() -> None:
    finished = subprocess.run(
        [sys.executable, "-I", "-c", CHILD, str(PACKAGE.parent)],
        capture_output=True,
        text=True,
    )
    assert finished.returncode == 0, (finished.stderr.strip().splitlines() or [""])[-1]
    assert json.loads(finished.stdout) == {
        "due_window": 45.0,
        "late_minutes": [45, 60, 120, 180, 240, 480, 720],
        "kind_order": {"late": 0, "due": 1, "due_soon": 2, "before": 3, "start": 4},
        "clients": ["synthetic-client"],
    }


def test_no_module_but_domain_lists_states_or_kinds() -> None:
    lists = {"states": set(domain.STATES), "kinds": set(domain.REMINDER_KINDS)}
    found = []
    for file, tree in sources():
        if file == "domain.py":
            continue
        allowed = allowed_nodes(tree, file)
        for node in ast.walk(tree):
            words = listed_words(node)
            if words is None or id(node) in allowed:
                continue
            for list_name, members in lists.items():
                if set(words) <= members:
                    found.append((file, node.lineno, list_name))
    assert found == []


def test_the_allowed_lists_match_domain() -> None:
    from docket import reminder_plan, views

    hints = get_type_hints(reminder_plan.PlannedReminder)
    assert get_args(hints["kind"]) == domain.REMINDER_KINDS
    assert tuple(views._NOTICE) == domain.REMINDER_KINDS


def test_the_email_client_is_named_only_in_domain() -> None:
    found = [
        (file, line)
        for file, tree in sources()
        if file != "domain.py"
        for line in email_client_uses(tree)
    ]
    assert found == []


def test_a_replay_answers_a_plain_200() -> None:
    tree = ast.parse((PACKAGE / "intake.py").read_text())
    assert ast.unparse(assigned(tree, "_REPLAY")) == "200"


def test_intake_reads_only_the_deadline_zone_through_text() -> None:
    tree = ast.parse((PACKAGE / "intake.py").read_text())
    calls = [
        ast.unparse(node.args[0])
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and ast.unparse(node.func) == "_text"
    ]
    assert calls == ["value['time_zone']"]
