"""Bounds and character rules for an email message id or link."""

import unicodedata

MESSAGE_ID_MAX = 512
LINK_MAX = 2048

_BAD_CATEGORIES = {"Cc", "Cf", "Zl", "Zp"}


def valid_reference(value: object, maximum: int) -> bool:
    return (
        isinstance(value, str)
        and 1 <= len(value) <= maximum
        and all(unicodedata.category(character) not in _BAD_CATEGORIES for character in value)
    )
