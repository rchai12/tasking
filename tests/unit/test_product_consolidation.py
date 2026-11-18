import tomllib

import pytest

from tests.product_consolidation_cases import (
    FAMILIES,
    MANIFEST,
    ROOT,
    check_collection,
    check_document,
    check_execution,
    check_family,
    check_frozen,
    check_oracle,
    check_selection,
)


@pytest.mark.parametrize("main", list(FAMILIES))
def test_canonical_modules_keep_exact_bodies_and_remove_continuations(main: str) -> None:
    check_family(main)


@pytest.mark.parametrize("main", list(FAMILIES))
def test_all_existing_cases_keep_their_mapping_and_core_section(main: str) -> None:
    check_collection(main)
    registry = tomllib.loads((ROOT / "tests/sections.toml").read_text())
    from fnmatch import fnmatch

    for path in (main, FAMILIES[main]["retired"]):
        owner = next(
            section["name"]
            for section in registry["section"]
            if any(fnmatch(path.removeprefix("tests/"), p) for p in section["patterns"])
        )
        assert owner == "core"


@pytest.mark.parametrize("main", list(FAMILIES))
def test_moved_cases_execute_with_the_canonical_fixtures(main: str) -> None:
    check_execution(main)


@pytest.mark.parametrize("path", list(MANIFEST["documents"]))
def test_historical_documents_apply_only_the_recorded_selector_migration(path: str) -> None:
    check_document(path)


@pytest.mark.parametrize(
    "index", range(4), ids=["tasks-start", "tasks-given", "serve-start", "serve-given"]
)
def test_historical_commands_select_the_original_case_sets(index: int) -> None:
    check_selection(index)


def test_other_tests_product_tooling_and_global_guards_are_unchanged() -> None:
    check_frozen()


def test_the_mapping_covers_the_literal_baseline_without_loss_or_duplication() -> None:
    check_oracle()
