"""Independent command-level checks over the immutable Phase 2p inventory."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.product_consolidation_cases import (  # noqa: E402
    FAMILIES,
    MANIFEST,
    check_collection,
    check_document,
    check_execution,
    check_family,
    check_frozen,
    check_oracle,
    check_selection,
)


def main() -> None:
    check_oracle()
    print("mapping oracle ok")
    if "--oracle-only" in sys.argv:
        print("FAILURES 0")
        return
    failures = 0
    checks = [("frozen boundaries", check_frozen, ())]
    for path in FAMILIES:
        checks.extend(
            [
                ("module " + path, check_family, (path,)),
                ("collection " + path, check_collection, (path,)),
                ("runtime " + path, check_execution, (path,)),
            ]
        )
    checks.extend(("document " + path, check_document, (path,)) for path in MANIFEST["documents"])
    checks.extend((f"selector {index}", check_selection, (index,)) for index in range(4))
    for label, call, args in checks:
        try:
            call(*args)
        except Exception as error:
            failures += 1
            print(f"FAIL {label}: expected preserved mapping; {type(error).__name__}")
        else:
            print(label + " ok")
    print(f"FAILURES {failures}")


if __name__ == "__main__":
    main()
