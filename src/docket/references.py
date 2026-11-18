"""Bounds and character rules for an email message id or link."""

import unicodedata

from docket import domain

MESSAGE_ID_MAX = 512
LINK_MAX = 2048


def valid_reference(value: object, maximum: int) -> bool:
    return (
        isinstance(value, str)
        and 1 <= len(value) <= maximum
        and all(
            unicodedata.category(character) not in domain.FORBIDDEN_TEXT_CATEGORIES
            for character in value
        )
    )
