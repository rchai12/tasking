"""Immutable byte-move, selector and preservation checks for Phase 2q."""

import hashlib
import json
from pathlib import Path

from tests.product_consolidation_cases import collected, run_pytest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "tests/product_organization_manifest.json").read_text())
MOVES = MANIFEST["moves"]


def check_move(old: str) -> None:
    row = MOVES[old]
    retired = ROOT / old
    assert not retired.exists() and not retired.is_symlink(), "retired path remains: " + old
    target = ROOT / row["destination"]
    assert target.is_file() and not target.is_symlink(), (
        "missing regular destination: " + row["destination"]
    )
    assert hashlib.sha256(target.read_bytes()).hexdigest() == row["sha256"], row["destination"]


def check_collection(old: str) -> None:
    row = MOVES[old]
    assert collected([row["destination"]]) == sorted(row["mapping"].values()), row["destination"]


def check_runtime(old: str) -> None:
    row = MOVES[old]
    done = run_pytest([row["destination"]], collect=False)
    assert done.returncode == 0, done.stdout[-1600:] + done.stderr[-500:]
    summary = next(line for line in done.stdout.splitlines() if " passed" in line)
    assert summary.startswith(str(len(row["mapping"])) + " passed"), summary
    assert all(word not in summary for word in ("failed", "error", "skipped", "xfailed")), summary


def check_document(path: str) -> None:
    expected = MANIFEST["documents"][path]["after_sha256"]
    assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected, path


def check_manifest() -> None:
    row = MANIFEST["manifest"]
    assert hashlib.sha256((ROOT / row["path"]).read_bytes()).hexdigest() == row["after_sha256"], (
        row["path"]
    )


def check_frozen() -> None:
    for path, expected in MANIFEST["frozen"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected, path


def check_oracle() -> None:
    assert [len(row["mapping"]) for row in MOVES.values()] == [7, 9, 4, 5, 2]
    before = [old for row in MOVES.values() for old in row["mapping"]]
    after = [new for row in MOVES.values() for new in row["mapping"].values()]
    assert len(before) == len(set(before)) == len(after) == len(set(after)) == 27
    assert len(MANIFEST["documents"]) == 10
    assert len(MANIFEST["frozen"]) == 145
    for old, row in MOVES.items():
        assert old.rsplit("/", 1)[0] == row["destination"].rsplit("/", 1)[0]
        for source, target in row["mapping"].items():
            assert source.split("::", 1)[1] == target.split("::", 1)[1]
