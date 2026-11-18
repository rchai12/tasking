import math

import pytest

from docket.serialization import canonical_json


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ({}, "{}"),
        ({"z": None, "a": "Café 雪"}, '{"a":"Café 雪","z":null}'),
        (
            {"z": [{"b": False, "a": True}, None], "a": {"y": 2, "x": 1}},
            '{"a":{"x":1,"y":2},"z":[{"a":true,"b":false},null]}',
        ),
        ({"text": 'a\n"b\\c'}, '{"text":"a\\n\\"b\\\\c"}'),
        ({"n": 1.0, "zero": -0.0}, '{"n":1.0,"zero":-0.0}'),
        ({"n": math.nan, "p": math.inf}, '{"n":NaN,"p":Infinity}'),
    ],
    ids=["empty", "unicode-null-order", "nested", "escapes", "numbers", "defaults"],
)
def test_canonical_json_keeps_the_existing_representation(value, expected) -> None:
    assert canonical_json(value) == expected


@pytest.mark.parametrize("kind", ["unsupported", "cycle"])
def test_encoding_errors_are_not_rewritten(kind: str) -> None:
    value: dict[str, object] = {"value": object()}
    error = TypeError
    if kind == "cycle":
        value["value"] = value
        error = ValueError
    with pytest.raises(error):
        canonical_json(value)


def test_encoding_does_not_mutate_the_input() -> None:
    value = {"z": [None, {"b": "雪", "a": 1}], "a": False}
    canonical_json(value)
    assert value == {"z": [None, {"b": "雪", "a": 1}], "a": False}
    assert list(value) == ["z", "a"]
