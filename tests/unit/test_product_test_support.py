import ast
import importlib
import inspect
import sqlite3
from pathlib import Path

import pytest

from docket.core import CoreError
from docket.store import Store
from tests import support
from tests.preservation_cases import assert_preserved
from tests.product_support_cases import (
    MANIFEST,
    ROOT,
    collect_consumers,
    consumer_digest,
    digest,
    execute_reference_cases,
    seed_digest,
)


@pytest.mark.parametrize("path", list(MANIFEST["files"]))
def test_consumers_bind_the_shared_store_and_path(path: str) -> None:
    module = importlib.import_module(path[:-3].replace("/", "."))
    assert module.path is support.path
    if path.endswith("test_store_links.py"):
        assert module.base_store is support.store
        assert list(inspect.signature(module.store.__wrapped__).parameters) == ["base_store"]
    else:
        assert module.store is support.store
    if path.endswith(("test_core.py", "test_core_keyed.py")):
        assert module.refused is support.refused


@pytest.mark.parametrize("path", list(MANIFEST["files"]))
def test_existing_cases_assertions_and_helpers_remain_unchanged(path: str) -> None:
    assert consumer_digest(ROOT / path) == MANIFEST["files"][path]


def test_seeded_link_fixture_keeps_exact_setup_and_values() -> None:
    assert seed_digest(ROOT / "tests/integration/test_store_links.py") == MANIFEST["seed"]
    module = importlib.import_module("tests.integration.test_store_links")
    assert module.__all__ == ["base_store"]
    node = next(
        node
        for node in ast.parse((ROOT / "tests/integration/test_store_links.py").read_text()).body
        if isinstance(node, ast.FunctionDef) and node.name == "store"
    )
    assert len(node.decorator_list) == 1
    assert ast.unparse(node.decorator_list[0]) == "pytest.fixture"


@pytest.mark.parametrize("name", list(MANIFEST["support"]))
def test_existing_support_helpers_keep_their_bodies(name: str) -> None:
    tree = ast.parse((ROOT / "tests/support.py").read_text())
    node = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name
    )
    assert digest(node) == MANIFEST["support"][name]
    if name == "run":
        runner = next(
            node
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "runner" for target in node.targets
            )
        )
        assert digest(runner) == MANIFEST["runner"]


def test_product_tooling_and_global_guards_are_untouched() -> None:
    for path, expected in MANIFEST["frozen"].items():
        assert_preserved(ROOT / path, expected)


class OtherError(Exception):
    code = "synthetic"

    def __str__(self):
        return "synthetic"


class WrongText(CoreError):
    def __str__(self):
        return "wrong text"


@pytest.mark.parametrize("case", ["correct", "wrong-code", "wrong-text", "no-error", "other-error"])
def test_shared_refusal_checks_code_text_and_exception_type(case: str) -> None:
    helper = support.refused
    error = CoreError("synthetic")
    if case == "wrong-code":
        error = CoreError("different")
    elif case == "wrong-text":
        error = WrongText("synthetic")
    elif case == "other-error":
        error = OtherError()

    def call():
        if case != "no-error":
            raise error

    if case == "correct":
        assert helper("synthetic", call) is None
    elif case == "other-error":
        with pytest.raises(OtherError) as raised:
            helper("synthetic", call)
        assert raised.value is error
    elif case == "no-error":
        with pytest.raises(pytest.fail.Exception):
            helper("synthetic", call)
    else:
        with pytest.raises(AssertionError):
            helper("synthetic", call)


def test_shared_path_is_a_function_scoped_explicit_fixture(tmp_path: Path) -> None:
    fixture = support.path
    marker = fixture._fixture_function_marker
    assert (marker.name, marker.scope, marker.autouse, marker.params) == (
        None,
        "function",
        False,
        None,
    )
    assert fixture.__wrapped__(tmp_path) == tmp_path / "docket.sqlite3"


class BodyFailure(Exception):
    pass


@pytest.mark.parametrize("failure", [False, True], ids=["normal", "body-exception"])
def test_shared_store_is_empty_and_closes_once_on_every_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: bool
) -> None:
    fixture = support.store
    assert list(inspect.signature(fixture.__wrapped__).parameters) == ["tmp_path"]
    marker = fixture._fixture_function_marker
    assert (marker.name, marker.scope, marker.autouse) == (None, "function", False)
    calls = []
    original = Store.close

    def close(self):
        calls.append("closed")
        return original(self)

    monkeypatch.setattr(Store, "close", close)
    generator = fixture.__wrapped__(tmp_path)
    opened = next(generator)
    try:
        assert opened.tasks() == []
        assert calls == []
        if failure:
            error = BodyFailure("synthetic")
            with pytest.raises(BodyFailure) as raised:
                generator.throw(error)
            assert raised.value is error
        else:
            with pytest.raises(StopIteration):
                next(generator)
        assert calls == ["closed"]
        with pytest.raises(sqlite3.ProgrammingError):
            opened.tasks()
    finally:
        generator.close()


def test_all_304_existing_consumer_cases_keep_their_nodeids_and_sections() -> None:
    assert collect_consumers() == MANIFEST["cases"]
    assert len(MANIFEST["cases"]) == 304
    from tests.support import load_script

    check = load_script("check")
    sections = check.read_sections((ROOT / "tests/sections.toml").read_text())
    assert all(
        check.section_of(path.removeprefix("tests/"), sections) == "core"
        for path in MANIFEST["files"]
    )


def test_parametrized_path_cases_execute_with_the_shared_store() -> None:
    done = execute_reference_cases()
    summary = done.stdout.strip().splitlines()[-1] if done.stdout.strip() else "no output"
    assert done.returncode == 0, (
        f"expected 28 reference cases passed; actual {summary}; {done.stderr[-500:]}"
    )
    assert "28 passed" in done.stdout
