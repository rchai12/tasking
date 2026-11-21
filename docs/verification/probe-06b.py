"""Synthetic freeze-retirement properties: only the retired tests go, edits pass, reviews stay."""

import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
SPEC = "docs/phases/phase-06b-retire-freeze-manifests.md"
GIVEN = "tests/unit/test_review_pins.py"
RETIRED_FILES = (
    "tests/unit/test_feature_preservation.py",
    "tests/unit/test_product_consolidation.py",
    "tests/unit/test_product_organization.py",
    "tests/unit/test_product_selector_runtime.py",
)
RETIRED_FUNCTIONS = (
    "tests/unit/test_product_test_support.py::test_consumers_bind_the_shared_store_and_path",
    "tests/unit/test_product_test_support.py::"
    "test_existing_cases_assertions_and_helpers_remain_unchanged",
    "tests/unit/test_product_test_support.py::test_seeded_link_fixture_keeps_exact_setup_and_values",
    "tests/unit/test_product_test_support.py::test_existing_support_helpers_keep_their_bodies",
    "tests/unit/test_product_test_support.py::test_product_tooling_and_global_guards_are_untouched",
    "tests/unit/test_product_test_support.py::"
    "test_all_304_existing_consumer_cases_keep_their_nodeids_and_sections",
    "tests/unit/test_product_test_support.py::"
    "test_parametrized_path_cases_execute_with_the_shared_store",
    "tests/unit/test_tooling_boundary.py::"
    "test_moved_modules_are_byte_identical_and_old_sources_are_removed",
    "tests/unit/test_tooling_boundary.py::"
    "test_prior_test_cases_and_assertions_only_change_import_namespace",
)
RETIRED_COUNT = 101
EDIT = "\n# Synthetic probe edit: a formerly pinned file may now change.\n"
HELPER = "\n\ndef _synthetic_probe_helper() -> None:\n    return None\n"


def retired(nodeid: str) -> bool:
    """The oracle: whether a base test id is one Phase 6b removes."""
    path, _, name = nodeid.partition("::")
    if path in RETIRED_FILES:
        return True
    function = f"{path}::{name.split('[', 1)[0]}"
    return function in RETIRED_FUNCTIONS


def oracle() -> None:
    assert retired("tests/unit/test_feature_preservation.py::test_byte_freezes_still_refuse_any")
    assert retired(
        "tests/unit/test_tooling_boundary.py::"
        "test_moved_modules_are_byte_identical_and_old_sources_are_removed[docket_tools/reports.py]"
    )
    assert not retired(
        "tests/unit/test_tooling_boundary.py::test_command_wrappers_bind_repository_tooling[a]"
    )
    assert not retired(
        "tests/unit/test_product_test_support.py::test_shared_path_is_a_function_scoped_explicit_fixture"
    )
    assert not retired("tests/unit/test_review_pins.py::test_the_retired_freeze_files_are_gone")
    assert not retired("tests/integration/test_store_table_boundaries.py::test_x")


def git(*args: str) -> bytes:
    done = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, timeout=60)
    assert done.returncode == 0, f"git {args[0]} failed"
    return done.stdout


def base_commit() -> str:
    found = git("log", "--diff-filter=A", "--format=%H", "-1", "--", SPEC).decode().strip()
    assert found, f"{SPEC} is not committed, so there is no base to compare with"
    return found


def base_tree(into: Path) -> None:
    data = git("archive", "--format=tar", base_commit())
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        archive.extractall(into, filter="data")


def working_tree(into: Path) -> None:
    listed = git("ls-files", "-z", "--cached", "--others", "--exclude-standard").split(b"\0")
    for raw in listed:
        name = raw.decode()
        if name and (ROOT / name).is_file():
            (into / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, into / name)


def pytest(tree: Path, *args: str) -> subprocess.CompletedProcess[str]:
    environment = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join((str(tree / "src"), str(tree))),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    return subprocess.run(
        [sys.executable, "-m", "pytest", "--no-cov", "-q", "-p", "no:cacheprovider", *args],
        cwd=tree,
        env=environment,
        capture_output=True,
        text=True,
        timeout=600,
    )


def collected(tree: Path) -> set[str]:
    done = pytest(tree, "--collect-only")
    assert done.returncode == 0, f"collection failed in {tree.name}: {done.stdout[-300:]}"
    return {line for line in done.stdout.splitlines() if line.startswith("tests/") and "::" in line}


def failures(done: subprocess.CompletedProcess[str]) -> list[str]:
    return sorted(
        line.split()[1] for line in done.stdout.splitlines() if line.startswith(("FAILED", "ERROR"))
    )


def only_the_retired_tests_go(root: Path) -> None:
    before, after = root / "base", root / "now"
    before.mkdir()
    after.mkdir()
    base_tree(before)
    working_tree(after)
    old, new = collected(before), collected(after)
    gone, added = old - new, new - old
    wrongly_gone = sorted(nodeid for nodeid in gone if not retired(nodeid))[:3]
    kept = sorted(nodeid for nodeid in old & new if retired(nodeid))[:3]
    assert not wrongly_gone, f"removed tests Phase 6b keeps: {wrongly_gone}"
    assert not kept, f"retired tests still collected: {kept}"
    assert len(gone) == RETIRED_COUNT, f"removed {len(gone)} tests, expected {RETIRED_COUNT}"
    assert added == set(), f"tests added beyond the given file: {sorted(added)[:3]}"
    given = {nodeid for nodeid in new if nodeid.startswith(GIVEN + "::")}
    assert len(given) == 35, f"the given file collects {len(given)} tests, expected 35"


def pinned_paths(base: Path) -> list[str]:
    """Every non-review file a base manifest pinned by bytes or structure."""
    names: set[str] = set()
    for manifest in base.glob("tests/*_manifest.json"):
        data = json.loads(manifest.read_text())
        names.update(data.get("frozen", {}))
        names.update(data.get("modules", {}))
    names.update(("src/docket/core.py", "src/docket/store.py"))
    return sorted(name for name in names if not name.startswith(("docs/reviews/", "tests/")))


def edits_to_formerly_pinned_files_pass(root: Path) -> None:
    before, after = root / "base", root / "now"
    before.mkdir()
    after.mkdir()
    base_tree(before)
    working_tree(after)
    edited = []
    for name in pinned_paths(before):
        target = after / name
        # An empty package marker stays empty: a behaviour test keeps docket_tools a bare package.
        if not target.is_file() or target.stat().st_size == 0:
            continue
        text = target.read_text()
        target.write_text(text + (HELPER if name.endswith(("core.py", "store.py")) else EDIT))
        edited.append(name)
    assert len(edited) >= 30, f"edited {len(edited)} formerly pinned files, expected 30 or more"
    done = pytest(after)
    failed = failures(done)
    assert done.returncode == 0, (
        f"after a comment or helper in {len(edited)} formerly pinned files "
        f"(AGENTS.md, pyproject.toml, store.py ...), {len(failed)} tests failed: {failed[:3]}"
    )


def a_changed_review_still_fails(root: Path) -> None:
    after = root / "now"
    after.mkdir()
    working_tree(after)
    review = after / "docs/reviews/phase-00-skeleton.md"
    review.write_bytes(review.read_bytes() + b" ")
    done = pytest(after, GIVEN)
    expected = [
        GIVEN + "::test_every_pinned_review_keeps_its_bytes[docs/reviews/phase-00-skeleton.md]"
    ]
    assert failures(done) == expected, f"a changed review gave {failures(done)[:3] or 'no failure'}"


def main() -> None:
    oracle()
    print("retirement oracle ok")
    if "--oracle-only" in sys.argv:
        print("FAILURES 0")
        return
    failures_seen = 0
    for name, check in (
        ("only the retired tests go", only_the_retired_tests_go),
        ("edits to formerly pinned files pass", edits_to_formerly_pinned_files_pass),
        ("a changed review still fails", a_changed_review_still_fails),
    ):
        with TemporaryDirectory() as directory:
            try:
                check(Path(directory))
            except Exception as raised:
                detail = str(raised) if isinstance(raised, AssertionError) else ""
                print(f"FAIL {name}: {detail or type(raised).__name__}")
                failures_seen += 1
            else:
                print(name + " ok")
    print(f"FAILURES {failures_seen}")


if __name__ == "__main__":
    main()
