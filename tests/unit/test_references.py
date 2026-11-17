import pytest

from docket.references import LINK_MAX, MESSAGE_ID_MAX, valid_reference


def test_reference_limits() -> None:
    assert MESSAGE_ID_MAX == 512
    assert LINK_MAX == 2048


@pytest.mark.parametrize(
    ("value", "maximum", "expected"),
    [
        (None, 512, False),
        (["x"], 512, False),
        ("", 512, False),
        ("x", 512, True),
        ("é" * 512, 512, True),
        ("x" * 513, 512, False),
        ("x" * 2048, 2048, True),
        ("x" * 2049, 2048, False),
        (" x ", 512, True),
        ("https://mail.example/a?b=c#d", 2048, True),
    ],
    ids=[
        "null",
        "list",
        "empty",
        "one",
        "unicode-at-cap",
        "id-over-cap",
        "link-at-cap",
        "link-over-cap",
        "spaces-preserved",
        "url-text",
    ],
)
def test_reference_boundaries(value: object, maximum: int, expected: bool) -> None:
    assert valid_reference(value, maximum) is expected


@pytest.mark.parametrize(
    "character",
    ["\x00", "\x1b", "\n", "\u0085", "\u200d", "\u2028", "\u2029"],
    ids=["nul", "escape", "newline", "c1", "format", "line", "paragraph"],
)
def test_reference_character_categories(character: str) -> None:
    assert valid_reference("safe" + character + "tail", 512) is False
