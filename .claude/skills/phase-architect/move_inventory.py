"""Record byte-identical test moves and literal document/manifest migrations; never apply them."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def inventory(root: Path, args: argparse.Namespace) -> dict:
    moves = dict(pair.split("=", 1) for pair in args.move)
    assert len(moves) == len(args.move) == len(set(moves.values()))
    assert all((root / old).is_file() and not (root / new).exists() for old, new in moves.items())
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "--no-cov", "-q", *moves],
        cwd=root,
        env={**os.environ, "PYTHONPATH": os.pathsep.join((str(root / "src"), str(root)))},
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    cases = [
        line for line in done.stdout.splitlines() if line.startswith("tests/") and "::" in line
    ]
    result = {"baseline": args.baseline, "moves": {}, "documents": {}, "frozen": {}}
    for old, new in moves.items():
        mapping = {
            case: new + "::" + case.split("::", 1)[1]
            for case in cases
            if case.startswith(old + "::")
        }
        assert mapping
        result["moves"][old] = {
            "destination": new,
            "sha256": sha((root / old).read_bytes()),
            "mapping": mapping,
        }
    suffix = (
        f"\n## Test path migration (Phase {args.phase})\n\n"
        "The product continuation paths above now use behaviour names. This is a byte-identical "
        "file move; function names, parameter IDs, counts and original implementation history "
        "are unchanged. The phase's immutable move inventory records every old/new selector.\n"
    )
    for path in args.document:
        original = (root / path).read_text()
        replacements = [[old, new] for old, new in moves.items() if old in original]
        assert replacements, path
        updated = original
        for old, new in replacements:
            updated = updated.replace(old, new)
        updated += suffix
        result["documents"][path] = {
            "before_sha256": sha(original.encode()),
            "after_sha256": sha(updated.encode()),
            "replacements": replacements,
            "append": suffix,
        }
    path = args.migrate_manifest
    original = (root / path).read_bytes()
    data = json.loads(original)
    frozen = data["frozen"]
    for old, new in moves.items():
        assert old in frozen and new not in frozen
        assert frozen[old] == result["moves"][old]["sha256"]
    # Preserve insertion order and values, replacing only the explicitly moved keys.
    data["frozen"] = {moves.get(key, key): value for key, value in frozen.items()}
    result["manifest"] = {
        "path": path,
        "before_sha256": sha(original),
        "after_sha256": sha((json.dumps(data, indent=2) + "\n").encode()),
    }
    tracked = subprocess.check_output(["git", "ls-files"], cwd=root, text=True).splitlines()
    for path in tracked:
        if path in moves or path == args.migrate_manifest:
            continue
        if path.startswith(
            ("src/", "tests/", "scripts/", "docket_tools/", "docs/reviews/")
        ) or path in (
            "pyproject.toml",
            "AGENTS.md",
        ):
            result["frozen"][path] = sha((root / path).read_bytes())
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--move", action="append", required=True, metavar="OLD=NEW")
    parser.add_argument("--document", action="append", required=True)
    parser.add_argument("--migrate-manifest", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = inventory(args.root.resolve(), args)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(
        f"{len(result['moves'])} moves; "
        f"{sum(len(row['mapping']) for row in result['moves'].values())} cases; "
        f"{len(result['documents'])} documents; {len(result['frozen'])} frozen paths"
    )


if __name__ == "__main__":
    main()
