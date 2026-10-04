"""A pack's contents list - RFC 0032, ADR 0145 and 0149.

A pack is a catalog item whose public description holds a strict list of
what's in it:

    This pack contains:

    - 1 x [Backpack](basic-gear-backpack)
      - 5 x [Rations, days of](basic-gear-rations-days-of)
      - 2 x [Torch](basic-gear-torch)

This module only reads and measures that list. It knows nothing of the
database, so `tests/data/pack_lists.json` can hold its examples, and the
CLI's own parser (`apps/cli/.../importer/packs.py`, which writes the list) is
held to the same ones: the two read one grammar.

The parser reads only lines of that shape and ignores everything else, so a
sentence added to the description can't change what a pack hands out.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Nesting is two spaces a level, and a list is at most three deep.
MAX_DEPTH = 3
# What one call may hand out (ADR 0149): a quantity on a line, a top-level
# stack for a group (which has no container to hold a count, so each unit is
# its own instance), and instances in all.
MAX_QUANTITY = 1000
MAX_LOOSE = 50
MAX_INSTANCES = 200

_LINKED = re.compile(
    r"^(?P<indent>(?:  )*)- (?P<quantity>\d+) x "
    r"\[(?P<label>[^\]\n]+)\]\((?P<slug>[A-Za-z0-9][A-Za-z0-9_-]{0,99})\)\s*$"
)
_PLAIN = re.compile(r"^(?P<indent>(?:  )*)- (?P<quantity>\d+) x (?P<label>[^\s\[\]()][^\n]*?)\s*$")


@dataclass(frozen=True, slots=True)
class PackLine:
    """One line of the list. `slug` is None for a line with no link."""

    depth: int
    quantity: int
    label: str
    slug: str | None = None


@dataclass(slots=True)
class PackNode:
    """A line and the lines inside it."""

    line: PackLine
    children: list[PackNode] = field(default_factory=list)


def parse_pack_list(text: str) -> list[PackLine]:
    """The list in `text`; every line that isn't one is ignored."""
    lines: list[PackLine] = []
    for raw in text.splitlines():
        match = _LINKED.match(raw)
        slug: str | None = None
        if match:
            slug = match.group("slug")
        else:
            match = _PLAIN.match(raw)
        if match is None:
            continue
        depth = len(match.group("indent")) // 2
        quantity = int(match.group("quantity"))
        if depth >= MAX_DEPTH or quantity < 1:
            continue
        lines.append(PackLine(depth, quantity, match.group("label").strip(), slug))
    return lines


def nest(lines: list[PackLine]) -> list[PackNode]:
    """The lines as a forest: each goes inside the nearest line above it that
    is one level up. A line with no such parent (indented with nothing above
    it, or two levels in at once) is mis-indented and ignored, with whatever
    is indented under it."""
    roots: list[PackNode] = []
    open_nodes: list[PackNode] = []  # the line last read at each depth so far
    for line in lines:
        if line.depth > len(open_nodes):
            continue
        node = PackNode(line)
        del open_nodes[line.depth :]
        if line.depth == 0:
            roots.append(node)
        else:
            open_nodes[line.depth - 1].children.append(node)
        open_nodes.append(node)
    return roots


def count_instances(nodes: list[PackNode], *, group: bool) -> int:
    """How many instances handing `nodes` out creates. A line with lines
    inside is a container made once per unit, each holding its own copy of
    what's inside; any other line is one stack, except a top-level one for a
    group, which has no container to hold a count and so is a single
    instance per unit."""
    return sum(_count(node, top=True, group=group) for node in nodes)


def _count(node: PackNode, *, top: bool, group: bool) -> int:
    if node.children:
        inside = sum(_count(child, top=False, group=group) for child in node.children)
        return node.line.quantity * (1 + inside)
    return node.line.quantity if top and group else 1


def list_problems(nodes: list[PackNode], *, group: bool) -> list[str]:
    """What stops the list being handed out, whatever the tenant holds: a
    line without a link, a quantity or a top-level stack over its limit, and
    too many instances. One entry each, worded for the caller."""
    problems: list[str] = []

    def walk(node: PackNode, *, top: bool) -> None:
        line = node.line
        if line.slug is None:
            problems.append(f"“{line.label}” has no link to an item")
        if line.quantity > MAX_QUANTITY:
            problems.append(f"“{line.label}”: {line.quantity} is more than {MAX_QUANTITY}")
        elif group and top and not node.children and line.quantity > MAX_LOOSE:
            problems.append(
                f"“{line.label}”: a group holds {line.quantity} loose as that many single "
                f"items, and {MAX_LOOSE} is the most"
            )
        for child in node.children:
            walk(child, top=False)

    for node in nodes:
        walk(node, top=True)
    if not problems:
        total = count_instances(nodes, group=group)
        if total > MAX_INSTANCES:
            problems.append(
                f"the list would create {total} instances, and {MAX_INSTANCES} is the most "
                "one call hands out"
            )
    return problems
