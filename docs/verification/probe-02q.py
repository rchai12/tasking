"""Command-level inventory and consumer execution for Phase 2q."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main() -> None:
    from tests.product_organization_cases import (
        MANIFEST,
        MOVES,
        check_collection,
        check_document,
        check_frozen,
        check_manifest,
        check_move,
        check_oracle,
        check_runtime,
    )

    check_oracle()
    print("27-case mapping oracle ok")
    if "--oracle-only" in sys.argv:
        print("FAILURES 0")
        return
    checks = [("frozen boundaries", check_frozen, ()), ("Phase 2p manifest", check_manifest, ())]
    for old in MOVES:
        checks.extend(
            [
                ("byte move " + old, check_move, (old,)),
                ("mapped cases " + old, check_collection, (old,)),
                ("runtime " + old, check_runtime, (old,)),
            ]
        )
    checks.extend(
        ("historical path " + path, check_document, (path,)) for path in MANIFEST["documents"]
    )
    failures = 0
    for label, call, args in checks:
        try:
            call(*args)
        except Exception as error:
            print(f"FAIL {label}: expected pinned move/selection; {type(error).__name__}")
            failures += 1
        else:
            print(label + " ok")
    print(f"FAILURES {failures}")


if __name__ == "__main__":
    main()
