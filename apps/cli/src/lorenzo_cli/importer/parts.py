"""Whose each thing an item is made of is (RFC 0033 section 6, ADR 0182): the neutral half, true
anywhere, or the system's, D&D's.

The starters decide it where they can (ADR 0504): a stat of a group of D&D 5e's system is the
system's, a category of the dnd5e starter is the system's, the rest is neutral. A row says it only
for what they do not decide (text, a stat or a parent they don't know), so a map can't say what the
starters contradict.
"""

from __future__ import annotations

from lorenzo_cli.importer.mapping import SYSTEM_AXES, Part, Rule
from lorenzo_cli.importer.transforms import Issue
from lorenzo_cli.importer.vocabulary import Vocabulary


def part_of_axis(axis: str) -> Part:
    """A category a row mints: `proficiency`, `tier` and `property` are the system's."""
    return "system" if axis in SYSTEM_AXES else "neutral"


class Parts:
    """The part of the starters' stats and categories."""

    def __init__(self, vocabulary: Vocabulary) -> None:
        self._stats = {d.name: d.part for d in vocabulary.definitions}
        self._nodes = {n.slug: n.part for n in vocabulary.nodes}

    def stat(self, name: str) -> Part | None:
        """The part of one of the starters' stats, or None where they don't have it."""
        return self._stats.get(name)

    def node(self, slug: str) -> Part | None:
        """The part of one of the starters' categories, or None where they don't have it."""
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
