import ast
import inspect
import re
import sqlite3
from collections.abc import Mapping
from pathlib import Path

import pytest

from docket import cli, config, core, deadlines, domain, intake, references, views, web
from docket.store import Store


@pytest.mark.parametrize(
    ("table", "column", "name"),
    [
        ("tasks", "state", "STATES"),
        ("tasks", "source", "SOURCES"),
        ("tasks", "provider", "PROVIDERS"),
        ("links", "provider", "PROVIDERS"),
        ("request_keys", "client", "CORE_CLIENTS"),
        ("audit_log", "actor", "ACTORS"),
        ("audit_log", "action", "AUDIT_ACTIONS"),
    ],
    ids=[
        "states",
        "sources",
        "task-providers",
        "link-providers",
        "clients",
        "actors",
        "audit-actions",
    ],
)
def test_current_sql_enumerations_match_domain(
    tmp_path: Path, table: str, column: str, name: str
) -> None:
    path = tmp_path / "docket.sqlite3"
    with Store(path):
        with sqlite3.connect(path) as connection:
            sql = connection.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()[0]
    match = re.search(rf"\b{column}\s+IN\s*\(([^)]+)\)", sql)
    assert match is not None
    assert set(ast.literal_eval("(" + match[1] + ")")) == set(getattr(domain, name))


@pytest.mark.parametrize(
    ("table", "expression", "minimum", "maximum", "module", "name"),
    [
        ("tasks", "length(title)", 1, 100, "domain", "TITLE_MAX"),
        ("tasks", "work_minutes", 5, 720, "domain", "WORK_MINUTES_MAX"),
        ("request_keys", "length(key)", 1, 200, "domain", "REQUEST_KEY_MAX"),
        ("tasks", "length(message_id)", 1, 512, "references", "MESSAGE_ID_MAX"),
        ("tasks", "length(link)", 1, 2048, "references", "LINK_MAX"),
        ("links", "length(message_id)", 1, 512, "references", "MESSAGE_ID_MAX"),
        ("links", "length(link)", 1, 2048, "references", "LINK_MAX"),
    ],
    ids=["titles", "work", "keys", "task-message", "task-link", "link-message", "link-link"],
)
def test_current_sql_bounds_match_shared_limits(
    tmp_path: Path, table: str, expression: str, minimum: int, maximum: int, module: str, name: str
) -> None:
    path = tmp_path / "docket.sqlite3"
    with Store(path):
        with sqlite3.connect(path) as connection:
            sql = connection.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()[0]
    match = re.search(re.escape(expression) + r"\s+BETWEEN\s+(\d+)\s+AND\s+(\d+)", sql)
    assert match is not None
    assert (int(match[1]), int(match[2])) == (minimum, maximum)
    assert getattr(domain if module == "domain" else references, name) == maximum
    if expression == "work_minutes":
        assert domain.WORK_MINUTES_MIN == minimum


LIMITS = {5, 100, 200, 720}
BOUND_KEYWORDS = {"ge", "gt", "le", "lt", "min_length", "max_length"}


def copied_limits(tree: ast.Module) -> list[int]:
    """Lines where a domain limit is a bound: compared against, or a bound keyword (ge=5).

    Another use of the same number, such as the HTTP status 200, is not a copied limit.
    """
    parts: list[ast.expr] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            parts += [node.left, *node.comparators]
        elif isinstance(node, ast.keyword) and node.arg in BOUND_KEYWORDS:
            parts.append(node.value)
    return [
        part.lineno
        for part in parts
        if isinstance(part, ast.Constant) and type(part.value) is int and part.value in LIMITS
    ]


def test_consumers_do_not_keep_copied_parsers_domains_or_limits() -> None:
    for module in (cli, intake):
        tree = ast.parse(inspect.getsource(module))
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"compile", "fromisoformat"}
            for node in ast.walk(tree)
        ), f"{module.__name__} still owns a parser"
    groups = [
        {"open", "in_progress", "done", "cancelled"},
        {"email", "agent", "proposal", "owner"},
        {"email", "agent"},
        {"owner", "agent", "email"},
        {"start", "done", "cancel", "reopen"},
        {"gmail", "outlook", "yahoo"},
        {"open", "in_progress"},
        {"done", "cancelled"},
        {"Cc", "Cf", "Zl", "Zp"},
    ]
    for module in (core, cli, intake, views, references, config, deadlines, web):
        tree = ast.parse(inspect.getsource(module))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Set, ast.Tuple, ast.List, ast.Dict)):
                try:
                    value = ast.literal_eval(node)
                    copied = groups
                    if isinstance(node, ast.Dict):
                        # Verb captions are presentation text; these two mappings are shared policy.
                        copied = [
                            {"open", "in_progress", "done", "cancelled"},
                            {"email", "agent", "proposal", "owner"},
                        ]
                    assert set(value) not in copied, f"{module.__name__} duplicates a domain"
                except (ValueError, TypeError):
                    pass
        if module in (core, intake, config, deadlines, web):
            assert copied_limits(tree) == [], f"{module.__name__} duplicates a limit"
    for module in (config, deadlines):
        assert "available_timezones" not in inspect.getsource(module)


def test_presentations_and_actor_mappings_share_the_domain_objects() -> None:
    assert isinstance(domain.STATE_LABELS, Mapping)
    assert isinstance(domain.SOURCE_ACTORS, Mapping)
    assert any(value is domain.STATE_LABELS for value in vars(views).values()) or (
        getattr(views, "domain", None) is domain
    )
    assert any(value is domain.SOURCE_ACTORS for value in vars(core).values()) or (
        getattr(core, "domain", None) is domain
    )


def test_token_issuance_stays_email_only() -> None:
    from docket.clients import CLIENTS

    assert CLIENTS == ("email",)
    assert domain.CORE_CLIENTS == ("email", "agent")
