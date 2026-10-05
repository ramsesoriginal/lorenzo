"""Whose each thing an item is made of is (RFC 0033 section 6, ADR 0182): the neutral half, true
anywhere, or the system's, D&D's.

The seed decides it where it can: a stat has the part of its definition's layer, a category the
part of its node's. A row says it only for what no layer decides (text, a stat or a parent the
seed doesn't know), so a map can't say what the seed contradicts.
"""

from __future__ import annotations

from lorenzo_cli.importer.mapping import SYSTEM_AXES, Part, Rule
from lorenzo_cli.importer.transforms import Issue
from lorenzo_cli.seed import SeedSpec
from lorenzo_cli.seed.spec import Layer, is_system_layer


def part_of_layer(layer: Layer) -> Part:
    return "system" if is_system_layer(layer) else "neutral"


def part_of_axis(axis: str) -> Part:
    """A category a row mints: `proficiency`, `tier` and `property` are the system's."""
    return "system" if axis in SYSTEM_AXES else "neutral"


class Parts:
    """The part of the seed's stats and categories."""

    def __init__(self, seed: SeedSpec) -> None:
        self._stats = {d.name: part_of_layer(d.layer) for d in seed.definitions}
        self._nodes = {n.slug: part_of_layer(n.layer) for n in seed.nodes}

    def stat(self, name: str) -> Part | None:
        """The part of one of the seed's stats, or None where the seed doesn't have it."""
        return self._stats.get(name)

    def node(self, slug: str) -> Part | None:
        """The part of one of the seed's categories, or None where the seed doesn't have it."""
        return self._nodes.get(slug)


# What a plain transform writes, for the part an issue it raises is held in. A transform with a
# `stat` takes the stat's; the text ones take the rule's.
_PLAIN_PART: dict[str, Part | None] = {
    "own_weight": "neutral",
    "sourcebook": "neutral",
    "damage": "system",
    "armor": "system",
    "pack_contents": "neutral",
    # Reach (neutral) and distances (system) come from one value: it holds both passes.
    "range": None,
}


def issue_part(rule: Rule, issue: Issue, parts: Parts) -> Part | None:
    """The pass an issue holds an item back in; None is both. An item is held where what it
    couldn't read is needed (ADR 0182): an unreadable price holds the system pass and not the
    neutral one, which imports the item without it."""
    if issue.kind == "name":
        return None  # the name is the item's identity in both passes
    if issue.kind == "price":
        return "system"
    stat = rule.params.get("stat")
    if isinstance(stat, str):
        return parts.stat(stat) or rule.part or "neutral"
    if rule.transform in {"description", "information", "aliases"}:
        return rule.part or "neutral"
    return _PLAIN_PART.get(rule.transform)
