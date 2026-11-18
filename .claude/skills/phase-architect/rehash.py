"""Move frozen byte pins for given planning edits, and nothing else.

    .venv/bin/python .claude/skills/phase-architect/rehash.py --cwd CLONE PATH...

For each PATH (relative to CLONE) whose bytes differ from `git show HEAD:PATH`, replace its HEAD
sha256 with its current sha256 wherever a `tests/*_manifest.json` holds it as a value, except
under a key containing `before` (a historical pin stays). A manifest changed this way is then
treated as a changed path too, until nothing moves. Prints one line per replacement and a final
count, then each changed PATH pinned nowhere (worth a look: a pin you expected may not exist).
Never touches a file it was not told about, except manifests.

`--value MODULE:FUNCTION` (repeatable) first moves values that a project helper computes from a
file rather than its bytes: the helper (imported from CLONE, called with a Path) runs on each
changed PATH's HEAD copy and on its current file, and the old value's JSON text in a manifest
becomes the new one. A helper returning a list is diffed; exactly one changed element moves,
more is printed as ambiguous and left for you. Examples: an AST digest of a test file
(`tests.product_support_cases:consumer_digest`), the AST dumps of a module's bodies
(`tests.product_consolidation_cases:bodies`).
"""

import argparse
import hashlib
import importlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def head_bytes(root: Path, path: str) -> bytes | None:
    found = subprocess.run(
        ["git", "show", f"HEAD:{path}"], cwd=root, capture_output=True, check=False
    )
    return found.stdout if found.returncode == 0 else None


def replace(text: str, old: str, new: str, where: str, hits: list[str]) -> str:
    lines = text.splitlines(keepends=True)
    for number, line in enumerate(lines, 1):
        if f'"{old}"' not in line:
            continue
        key = line.split(":", 1)[0] if '":' in line else ""
        if "before" in key:
            continue
        lines[number - 1] = line.replace(f'"{old}"', f'"{new}"')
        hits.append(f"{where}:{number}")
    return "".join(lines)


def value_pairs(old: object, new: object, path: str) -> list[tuple[str, str]]:
    if isinstance(old, str) and isinstance(new, str):
        return [] if old == new else [(old, new)]
    if isinstance(old, list | tuple) and isinstance(new, list | tuple):
        removed = [item for item in old if item not in new]
        added = [item for item in new if item not in old]
        if len(removed) == len(added) == 1:
            return [(removed[0], added[0])]
        if removed or added:
            print(f"ambiguous: {path} has {len(removed)} removed, {len(added)} added values")
    return []


def move_values(root: Path, paths: list[str], specs: list[str], manifests: list[str]) -> int:
    sys.path.insert(0, str(root))
    moved = 0
    for spec in specs:
        module, name = spec.split(":")
        helper = getattr(importlib.import_module(module), name)
        for path in paths:
            before = head_bytes(root, path)
            if not path.endswith(".py") or before is None:
                continue
            with tempfile.TemporaryDirectory() as folder:
                copy = Path(folder) / Path(path).name
                copy.write_bytes(before)
                pairs = value_pairs(helper(copy), helper(root / path), path)
            for old, new in pairs:
                for manifest in manifests:
                    file = root / manifest
                    text = file.read_text()
                    for ascii_only in (False, True):
                        needle = json.dumps(old, ensure_ascii=ascii_only)
                        if needle in text:
                            count = text.count(needle)
                            replacement = json.dumps(new, ensure_ascii=ascii_only)
                            file.write_text(text.replace(needle, replacement))
                            print(f"{path}: {name} value moved x{count} at {manifest}")
                            moved += count
                            break
    return moved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cwd", type=Path, required=True)
    parser.add_argument("--value", action="append", default=[])
    parser.add_argument("paths", nargs="+")
    args = parser.parse_args(argv)
    root = args.cwd.resolve()
    manifests = sorted(str(p.relative_to(root)) for p in root.glob("tests/*_manifest.json"))
    total = move_values(root, args.paths, args.value, manifests)
    pending = list(dict.fromkeys([*args.paths, *manifests]))
    known: dict[str, str] = {}
    unpinned = []
    while pending:
        path = pending.pop(0)
        if path not in known:
            before = head_bytes(root, path)
            if before is None:
                continue
            known[path] = digest(before)
        old, new = known[path], digest((root / path).read_bytes())
        if old == new:
            continue
        known[path] = new
        moved = 0
        for manifest in manifests:
            file = root / manifest
            text = file.read_text()
            if old not in text:
                continue
            hits: list[str] = []
            changed = replace(text, old, new, manifest, hits)
            if hits:
                file.write_text(changed)
                for hit in hits:
                    print(f"{path}: {old[:12]} -> {new[:12]} at {hit}")
                moved += len(hits)
                if manifest not in pending:
                    pending.append(manifest)
        total += moved
        if moved == 0 and path not in manifests and path not in unpinned:
            unpinned.append(path)
    print(f"moved {total}")
    for path in unpinned:
        print(f"not pinned anywhere: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
