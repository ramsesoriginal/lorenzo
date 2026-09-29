"""Reading the tagged JSON the worker returns (ADR 0138).

A value the worker couldn't express as plain JSON comes back as a one-key object. These helpers
are the only place that knows the tags, so the importer never string-matches them.
"""

from __future__ import annotations

from typing import Any


def regex_of(value: Any) -> tuple[str, str] | None:
    """`(source, flags)` if `value` is a JavaScript RegExp."""
    if isinstance(value, dict) and set(value) == {"$re"}:
        source, flags = value["$re"]
        return str(source), str(flags)
    return None


def function_text_of(value: Any) -> str | None:
    """The source text if `value` is a JavaScript function (it was never called)."""
    if isinstance(value, dict) and set(value) == {"$fn"}:
        return str(value["$fn"])
    return None


def stub_name_of(value: Any) -> str | None:
    """The sheet call's name if `value` came out of one this host stubbed."""
    if isinstance(value, dict) and set(value) == {"$stub"}:
        return str(value["$stub"])
    return None


def is_plain(value: Any) -> bool:
    """True if `value` holds no tagged value anywhere inside it."""
    if isinstance(value, dict):
        if len(value) == 1 and next(iter(value)).startswith("$"):
            return False
        return all(is_plain(item) for item in value.values())
    if isinstance(value, list):
        return all(is_plain(item) for item in value)
    return True
