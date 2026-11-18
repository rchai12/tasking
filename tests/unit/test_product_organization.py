import tomllib
from fnmatch import fnmatch

import pytest

from tests.product_organization_cases import (
    MANIFEST,
    MOVES,
    ROOT,
    check_collection,
    check_document,
    check_frozen,
    check_manifest,
    check_move,
    check_oracle,
    check_runtime,
)


@pytest.mark.parametrize("old", list(MOVES))
def test_product_files_move_byte_identically_without_shims(old: str) -> None:
    check_move(old)


@pytest.mark.parametrize("old", list(MOVES))
def test_mapped_cases_preserve_parameters_and_core_ownership(old: str) -> None:
    check_collection(old)
    registry = tomllib.loads((ROOT / "tests/sections.toml").read_text())
    for path in (old, MOVES[old]["destination"]):
        owner = next(
            section["name"]
            for section in registry["section"]
            if any(fnmatch(path.removeprefix("tests/"), pattern) for pattern in section["patterns"])
        )
        assert owner == "core"


@pytest.mark.parametrize("old", list(MOVES))
def test_moved_consumers_execute_with_existing_fixtures(old: str) -> None:
    check_runtime(old)


@pytest.mark.parametrize("path", list(MANIFEST["documents"]))
def test_historical_paths_follow_only_the_literal_document_plan(path: str) -> None:
    check_document(path)


def test_phase_2p_inventory_migrates_only_the_five_frozen_keys() -> None:
    check_manifest()


def test_other_tests_product_tooling_and_global_guards_stay_unchanged() -> None:
    check_frozen()


def test_literal_inventory_has_27_bijective_cases_in_the_same_directories() -> None:
    check_oracle()
