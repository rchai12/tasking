"""Phase 6b: verifier reviews stay pinned, and the retired freezes stay gone."""

import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PINS = ROOT / "tests" / "review_pins.json"
RETIRED_FILES = (
    "tests/preservation_cases.py",
    "tests/product_consolidation_cases.py",
    "tests/product_consolidation_manifest.json",
    "tests/product_organization_cases.py",
    "tests/product_organization_manifest.json",
    "tests/product_support_cases.py",
    "tests/product_support_manifest.json",
    "tests/tooling_boundary_manifest.json",
    "tests/unit/test_feature_preservation.py",
    "tests/unit/test_product_consolidation.py",
    "tests/unit/test_product_organization.py",
    "tests/unit/test_product_selector_runtime.py",
)
RETIRED_NAMES = (
    "preservation_cases",
    "product_consolidation_cases",
    "product_organization_cases",
    "product_support_cases",
    "_manifest.json",
    "assert_preserved",
    "normalized_test",
)


def pinned() -> dict[str, str]:
    return json.loads(PINS.read_text())["reviews"]


def changed(path: Path, expected: str) -> str | None:
    """None when the file still has the pinned bytes, else a one-line refusal."""
    if hashlib.sha256(path.read_bytes()).hexdigest() == expected:
        return None
    return f"pinned review changed: {path.name}"


@pytest.mark.parametrize("path", sorted(pinned()))
def test_every_pinned_review_keeps_its_bytes(path: str) -> None:
    assert changed(ROOT / path, pinned()[path]) is None


def test_the_pins_name_only_existing_reviews() -> None:
    reviews = {f"docs/reviews/{file.name}" for file in (ROOT / "docs/reviews").glob("phase-*.md")}
    assert sorted(set(pinned()) - reviews) == []
    assert len(pinned()) >= 31


def test_a_changed_byte_is_refused(tmp_path: Path) -> None:
    review = tmp_path / "phase-99-synthetic.md"
    review.write_bytes(b"# Review: Phase 99\n\n- Verdict: PASS\n")
    expected = hashlib.sha256(review.read_bytes()).hexdigest()
    assert changed(review, expected) is None
    review.write_bytes(b"# Review: Phase 99\n\n- Verdict: FAIL\n")
    assert changed(review, expected) == "pinned review changed: phase-99-synthetic.md"


def test_the_retired_freeze_files_are_gone() -> None:
    assert [path for path in RETIRED_FILES if (ROOT / path).exists()] == []
    assert sorted(path.name for path in (ROOT / "tests").glob("*_manifest.json")) == []


def test_no_test_or_script_reads_a_retired_freeze() -> None:
    sources = [
        *(ROOT / "tests").rglob("*.py"),
        *(ROOT / "scripts").glob("*.py"),
        *(ROOT / "docket_tools").glob("*.py"),
    ]
    found = sorted(
        f"{path.relative_to(ROOT)}: {name}"
        for path in sources
        if path != Path(__file__).resolve()
        for name in RETIRED_NAMES
        if name in path.read_text()
    )
    assert found == []
