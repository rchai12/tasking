"""Offline shared-fixture/refusal contracts and unchanged-case preservation."""

import argparse
import importlib
import inspect
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from docket.core import CoreError  # noqa: E402
from tests import support  # noqa: E402
from tests.product_support_cases import (  # noqa: E402
    MANIFEST,
    ROOT,
    collect_consumers,
    consumer_digest,
    execute_reference_cases,
    seed_digest,
)


def oracle() -> None:
    assert len(MANIFEST["files"]) == 8
    assert len(MANIFEST["cases"]) == len(set(MANIFEST["cases"])) == 304
    assert set(MANIFEST["support"]) == {"run", "fixed_times", "fixed_ids", "load_script"}


def bindings() -> None:
    for path in MANIFEST["files"]:
        module = importlib.import_module(path[:-3].replace("/", "."))
        assert module.path is support.path, f"{path}: path fixture not shared"
        name = "base_store" if path.endswith("test_store_links.py") else "store"
        assert getattr(module, name) is support.store, f"{path}: store fixture not shared"
        if path.endswith("test_store_links.py"):
            assert getattr(module, "__all__", None) == ["base_store"], (
                "missing explicit fixture re-export"
            )
    for name in ("tests.integration.test_core", "tests.integration.test_core_keyed"):
        assert importlib.import_module(name).refused is support.refused, (
            f"{name}: refusal helper copied"
        )


def refusal() -> None:
    def bad():
        raise CoreError("synthetic")

    assert support.refused("synthetic", bad) is None
    try:
        support.refused("different", bad)
    except AssertionError:
        pass
    else:
        raise AssertionError("wrong code was accepted by the shared helper")


def lifetime() -> None:
    assert list(inspect.signature(support.store.__wrapped__).parameters) == ["tmp_path"], (
        "store fixture must depend directly on tmp_path, not the parametrized path label"
    )
    with TemporaryDirectory() as folder:
        path = support.path.__wrapped__(Path(folder))
        assert path == Path(folder) / "docket.sqlite3"
        generator = support.store.__wrapped__(Path(folder))
        store = next(generator)
        try:
            assert store.tasks() == [], "shared store was unexpectedly seeded"
        finally:
            generator.close()
        import sqlite3

        try:
            store.tasks()
        except sqlite3.ProgrammingError:
            pass
        else:
            raise AssertionError("fixture exit left its SQLite connection open")


def preservation() -> None:
    for path, expected in MANIFEST["files"].items():
        assert consumer_digest(ROOT / path) == expected, f"{path}: test body changed"
    assert seed_digest(ROOT / "tests/integration/test_store_links.py") == MANIFEST["seed"]
    assert collect_consumers() == MANIFEST["cases"], "existing test node IDs/counts changed"
    done = execute_reference_cases()
    summary = done.stdout.strip().splitlines()[-1] if done.stdout.strip() else "no output"
    assert done.returncode == 0, (
        "runtime fixture collision: expected 28 reference cases passed; " + summary
    )
    assert "28 passed" in done.stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--oracle-only", action="store_true")
    args = parser.parse_args()
    oracle()
    print("product-test inventory oracle ok")
    failures = 0
    if not args.oracle_only:
        for name, check in (
            ("shared bindings", bindings),
            ("strict refusal", refusal),
            ("store lifetime", lifetime),
            ("304 preserved cases", preservation),
        ):
            try:
                check()
                print(f"{name} ok")
            except Exception as error:
                print(f"{name} FAIL: {type(error).__name__}: {error}")
                failures += 1
    print(f"FAILURES {failures}")
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
