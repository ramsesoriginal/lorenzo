"""What the MPMB importer writes into (ADR 0490): the stats and categories of the `neutral` and
`dnd5e` starters, each with its part. A stat is the system half's when its group belongs to the
document's system, a category when it is the system's document's entry; the rest is neutral. The
seed's layers decided this before; the starters' systems decide it now."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import cache

from lorenzo_cli import starters
from lorenzo_cli.importer.mapping import Part

# The documents the importer reads: the neutral one, and D&D 5e's on top of it.
DOCUMENTS = ("neutral", "dnd5e")


@dataclass(frozen=True)
class Definition:
    name: str
    group: str
    value_type: str
    part: Part


@dataclass(frozen=True)
class Node:
    slug: str
    name: str
    parents: tuple[str, ...]
    part: Part


@dataclass(frozen=True)
class Vocabulary:
    # Which starters it was read from, by a digest of their text: a review queue records it.
    version: str
    definitions: tuple[Definition, ...]
    nodes: tuple[Node, ...]

    def node(self, slug: str) -> Node:
        return next(n for n in self.nodes if n.slug == slug)


@cache
def load() -> Vocabulary:
    definitions: list[Definition] = []
    nodes: list[Node] = []
    digest = hashlib.sha256()
    for name in DOCUMENTS:
        digest.update(starters.text(name).encode())
        doc = starters.load(name)
        system_groups = {g.name for g in doc.group if g.system}
        for stat in doc.stat:
            part: Part = "system" if stat.group in system_groups else "neutral"
            definitions.append(Definition(stat.name, stat.group, stat.type, part))
        for entry in doc.entry:
            nodes.append(
                Node(
                    entry.slug,
                    entry.name,
                    tuple(entry.parents),
                    "system" if doc.system is not None else "neutral",
                )
            )
    return Vocabulary(digest.hexdigest()[:12], tuple(definitions), tuple(nodes))
