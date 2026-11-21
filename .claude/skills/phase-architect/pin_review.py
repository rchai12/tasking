"""Pin passed phases' verifier reviews in tests/review_pins.json; never move an existing pin.

    .venv/bin/python .claude/skills/phase-architect/pin_review.py docs/reviews/phase-NNx-slug.md...

Run it when recording a PASS, in the next spec's commit (owner's decision, 2026-11-21). A review
already pinned with the same bytes is reported and left alone; one pinned with other bytes stops
the run, because a pinned review never changes.
"""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PINS = ROOT / "tests" / "review_pins.json"


def pin(paths: list[str], pins_file: Path = PINS, root: Path = ROOT) -> int:
    data = json.loads(pins_file.read_text(encoding="utf-8"))
    reviews: dict[str, str] = data["reviews"]
    for name in paths:
        if not name.startswith("docs/reviews/phase-") or not (root / name).is_file():
            print(f"not a review: {name}")
            return 1
        value = hashlib.sha256((root / name).read_bytes()).hexdigest()
        if reviews.get(name) not in (None, value):
            print(f"already pinned with other bytes: {name}")
            return 1
        print(f"{'already pinned' if name in reviews else 'pinned'}: {name}")
        reviews[name] = value
    data["reviews"] = dict(sorted(reviews.items()))
    pins_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="+")
    return pin(parser.parse_args().paths)


if __name__ == "__main__":
    raise SystemExit(main())
