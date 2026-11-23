"""The one JSON writer used to save and compare request and audit records."""

import json


def canonical_json(value: dict[str, object] | list[str]) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
