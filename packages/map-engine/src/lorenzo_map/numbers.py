"""Numbers as the format allows them: finite, at most six decimals, bounded."""

from __future__ import annotations

import math
import unicodedata
from typing import Any

from lorenzo_map.errors import MapDocumentError
from lorenzo_map.limits import MAX_DECIMALS, MAX_UNIT_LENGTH

SCALE = 1_000_000  # millionths: MAX_DECIMALS decimals


def quantise(value: Any, *, bound: float, what: str) -> int:
    """The number in millionths, or a refusal. A bool is not a number; a value with more than six
    decimals, or beyond `bound` in size, is refused rather than rounded."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise MapDocumentError(f"{what} must be a number")
    if not math.isfinite(value):
        raise MapDocumentError(f"{what} must be a finite number")
    if abs(value) > bound:
        raise MapDocumentError(f"{what} is too large")
    scaled = value * SCALE
    whole = round(scaled)
    if abs(scaled - whole) > 1e-4:
        raise MapDocumentError(f"{what} has more than {MAX_DECIMALS} decimals")
    return int(whole)


def canonical(millionths: int) -> int | float:
    """The stored form of a quantised number: an integer when it is one, else a float."""
    if millionths % SCALE == 0:
        return millionths // SCALE
    return millionths / SCALE


def clean_text(value: Any, *, what: str) -> str:
    """A name the author chose (a unit): trimmed, composed, not empty, not long, no control
    characters."""
    if not isinstance(value, str):
        raise MapDocumentError(f"{what} must be text")
    text = unicodedata.normalize("NFC", value).strip()
    if not text or len(text) > MAX_UNIT_LENGTH:
        raise MapDocumentError(f"{what} must be between 1 and {MAX_UNIT_LENGTH} characters")
    if any(unicodedata.category(ch).startswith("C") for ch in text):
        raise MapDocumentError(f"{what} must not contain control characters")
    return text
