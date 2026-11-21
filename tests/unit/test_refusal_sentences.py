"""Phase 6c: every refusal code core can raise has a sentence in views."""

import ast
from pathlib import Path

import pytest

from docket import core
from docket.views import refusal_text

CORE = Path(core.__file__)
NEW = [
    ("invalid_client", "That client is not allowed."),
    ("invalid_key", "A request key is 1 to 200 characters."),
    ("key_reused", "That request key was already used for a different request."),
    ("invalid_deadline", "That is not a valid deadline."),
    ("invalid_work", "That is not a valid work time."),
]
KNOWN = {
    "unknown_task",
    "invalid_title",
    "invalid_source",
    "invalid_reference",
    "invalid_actor",
    "invalid_action",
    "task_ended",
    "work_after_deadline",
    "invalid_client",
    "invalid_key",
    "key_reused",
    "invalid_reminder_plan",
    "invalid_deadline",
    "invalid_work",
}


def codes() -> dict[str, str]:
    """Every public string constant of docket.core, by name: the refusal codes."""
    return {
        name: value
        for name, value in vars(core).items()
        if name.isupper() and not name.startswith("_") and isinstance(value, str)
    }


@pytest.mark.xfail(
    strict=True, reason="Phase 6c given test: remove this marker when every code has a sentence"
)
@pytest.mark.parametrize(("code", "expected"), NEW, ids=[code for code, _ in NEW])
def test_the_new_sentences(code: str, expected: str) -> None:
    assert refusal_text(code) == expected
    assert refusal_text(code, "t4") == expected


@pytest.mark.xfail(
    strict=True, reason="Phase 6c given test: remove this marker when every code has a sentence"
)
def test_every_core_code_has_a_sentence() -> None:
    found = codes()
    assert KNOWN <= set(found.values())
    missing = []
    for value in sorted(found.values()):
        try:
            sentence = refusal_text(value)
        except KeyError:
            missing.append(value)
        else:
            assert sentence[:1].isupper() and sentence.endswith("."), value
    assert missing == []


def test_every_core_refusal_names_a_code_constant() -> None:
    names = set(codes())
    raised = []
    for node in ast.walk(ast.parse(CORE.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "CoreError":
            arguments = [*node.args, *(keyword.value for keyword in node.keywords)]
            assert len(arguments) == 1, f"line {node.lineno}"
            assert isinstance(arguments[0], ast.Name), f"line {node.lineno}"
            assert arguments[0].id in names, f"line {node.lineno}"
            raised.append(arguments[0].id)
    assert len(raised) >= 20


def test_an_unknown_code_still_raises() -> None:
    with pytest.raises(KeyError):
        refusal_text("no_such_code")
