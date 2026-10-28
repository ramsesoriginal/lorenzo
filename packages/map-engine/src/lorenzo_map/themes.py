"""The names of the themes a Map may ask for (ADR 0352).

A theme is code in the renderer; the API only keeps its name. The renderer's own list is held to
this one by `golden/themes.json`, which both packages' tests read.
"""

from __future__ import annotations

from typing import Any

from lorenzo_map.errors import MapDocumentError
from lorenzo_map.limits import MAX_THEME_NAME

THEME_NAMES = ("default", "plain")


def validate_theme_hint(name: Any) -> str | None:
    """The theme name to store, or a refusal: nothing, or one of `THEME_NAMES`."""
    if name is None:
        return None
    if not isinstance(name, str) or name not in THEME_NAMES:
        raise MapDocumentError("that is not a theme this version has")
    return name


def read_theme_hint(name: Any) -> str | None:
    """A stored name as a reader treats it: one this version knows, else none (the default).
    The stored value is never rewritten, so a Map made by a newer version round-trips."""
    return name if isinstance(name, str) and name in THEME_NAMES else None


def keep_theme_hint(name: Any) -> str | None:
    """A name carried by a copy: unchanged when it is text of a sane length, so a newer version's
    theme survives, and nothing otherwise."""
    return name if isinstance(name, str) and 0 < len(name) <= MAX_THEME_NAME else None
