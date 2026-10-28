"""What changing a Map's system does to the places drawn on it (ADR 0354): refuse what would move
every one of them, and say what else may no longer line up. Pure: the router asks, then decides."""

from __future__ import annotations

from typing import Any


def _hex_orientation(system: dict[str, Any]) -> str | None:
    return system.get("orientation") if system.get("kind") == "hex" else None


def refusal(old: dict[str, Any], new: dict[str, Any]) -> str | None:
    """A sentence when the change would turn a hex or a sphere Map into another kind or another into
    one of them, or turn a hex Map's hexes, and none otherwise (ADR 0354, 0357). Only asked when the
    Map has placements."""
    if (old.get("kind") == "hex") != (new.get("kind") == "hex"):
        return "A Map with places cannot become a hex Map, or stop being one."
    if (old.get("kind") == "sphere") != (new.get("kind") == "sphere"):
        return "A Map with places cannot become a sphere, or stop being one."
    if _hex_orientation(old) != _hex_orientation(new):
        return "A hex Map with places cannot turn its hexes between flat and pointy."
    return None


def warnings(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    """What may no longer line up after the change, for a Map with placements."""
    found: list[str] = []
    if old.get("kind") != new.get("kind"):
        found.append("The kind of sheet changed; places stay where they were drawn.")
    if old.get("cell") != new.get("cell") or old.get("sub") != new.get("sub"):
        found.append(
            "The cell changed; places stay where they were drawn and may no longer fall on "
            "cell centres or edges."
        )
    if old.get("extent") != new.get("extent"):
        found.append("The sheet changed size; places outside it are kept.")
    return found
