"""Terminal output as plain words.

Typer draws its own help and usage errors with colour and boxes (always, under GitHub Actions),
and a terminal wraps long lines, so a test reads what was said through this.
"""

from __future__ import annotations

import re

_COLOUR = re.compile(r"\x1b\[[0-9;]*m")
_BOXES = re.compile(r"[│╭╮╰╯─]")


def plain(text: str) -> str:
    return " ".join(_BOXES.sub(" ", _COLOUR.sub("", text)).split())
