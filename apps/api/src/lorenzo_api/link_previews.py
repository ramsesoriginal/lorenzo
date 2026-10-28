"""What a link to an entry shows when pointed at (ADR 0264): the registry of preview templates.

A template says, for one kind of entry, which stats a card shows (by the name the library gave
the stat), how many of them, and how much of the description. The kinds are the ones an entry
can be that a card has words for (ADR 0217: `item`, `item_instance`, `being`, `character`; ADR 0350:
`location`, `map`) and a fallback for any other entry. The templates are code, not data: a
library does not edit them (ADR 0264).

Pure Python, no database: `template_for` picks the template from an entry's kinds, `pick_stats`
and `excerpt_of` apply it to values the router has already read.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from lorenzo_api.lorenzoscript import Node, parse


@dataclass(frozen=True, slots=True)
class PreviewTemplate:
    """One kind's card. `stats` are stat names in the order they are shown, matched without
    regard to case; a stat the entry has no value for is skipped, and at most `max_stats` show.
    `excerpt_chars` cuts the description. `inherits` lets an entry with no description or main
    picture of its own show the nearest ancestor's (ADR 0111), as an item's page does."""

    name: str
    stats: tuple[str, ...]
    max_stats: int = 4
    excerpt_chars: int = 200
    inherits: bool = True


FALLBACK = PreviewTemplate(name="entry", stats=(), max_stats=0)

# In the order `template_for` prefers: the most specific kind of an entry wins.
TEMPLATES: dict[str, PreviewTemplate] = {
    "character": PreviewTemplate(
        name="character", stats=("hp", "armor", "height"), max_stats=3, inherits=False
    ),
    "being": PreviewTemplate(name="being", stats=("hp", "armor", "height", "rarity"), max_stats=3),
    "item_instance": PreviewTemplate(
        name="item_instance", stats=("damage", "armor", "weight", "price", "rarity", "hp")
    ),
    "item": PreviewTemplate(
        name="item", stats=("damage", "armor", "weight", "price", "rarity"), max_stats=4
    ),
    # ADR 0350: a place and a map show no numbers, only what they are and how they are described.
    "location": PreviewTemplate(name="location", stats=(), max_stats=0),
    "map": PreviewTemplate(name="map", stats=(), max_stats=0),
    # ADR 0363: a connection shows what it is called and how it is described.
    "connection": PreviewTemplate(name="connection", stats=(), max_stats=0),
}


def template_for(kinds: Sequence[str]) -> PreviewTemplate:
    """The template of the most specific kind in `kinds`, or the fallback for a bare entry."""
    for kind, template in TEMPLATES.items():
        if kind in kinds:
            return template
    return FALLBACK


def pick_stats(
    template: PreviewTemplate, values: Mapping[str, int | float | str | bool]
) -> list[tuple[str, int | float | str | bool]]:
    """The template's stats that `values` (by stat name) holds, in the template's order, as
    (name as the library spells it, value), at most `max_stats`. Tags (booleans) are left out:
    a card says what a thing is worth or weighs, not that it is flagged."""
    by_lower = {name.lower(): name for name in values}
    picked: list[tuple[str, int | float | str | bool]] = []
    for wanted in template.stats:
        name = by_lower.get(wanted.lower())
        if name is None or isinstance(values[name], bool):
            continue
        picked.append((name, values[name]))
        if len(picked) == template.max_stats:
            break
    return picked


def _inline_text(nodes: Sequence[Node]) -> str:
    """Plain text of inline nodes: links keep their words, pictures and the rest give none."""
    out: list[str] = []
    for node in nodes:
        kind = node["type"]
        if kind == "image":
            continue
        if kind in ("text", "codespan"):
            out.append(node["text"])
        elif kind == "break":
            out.append(" ")
        elif kind == "stat":
            out.append(node.get("name") or "")
        elif kind == "date":
            out.append(node["date"])
        elif "children" in node:
            out.append(_inline_text(node["children"]))
    return "".join(out)


def _block_texts(blocks: Sequence[Node]) -> list[str]:
    texts: list[str] = []
    for block in blocks:
        kind = block["type"]
        if kind in ("paragraph", "heading"):
            texts.append(_inline_text(block["children"]))
        elif kind in ("blockquote", "div"):
            texts.extend(_block_texts(block["children"]))
        elif kind == "list":
            for item in block["items"]:
                texts.extend(_block_texts(item["children"]))
    return texts


def excerpt_of(source: str, limit: int) -> str:
    """The start of a LorenzoScript text as plain words: paragraphs, headings and list items
    joined by a space, cut at a word boundary with an ellipsis when longer than `limit`."""
    flat = " ".join(" ".join(_block_texts(parse(source)["children"])).split())
    if len(flat) <= limit:
        return flat
    cut = flat[:limit]
    space = cut.rfind(" ")
    return f"{cut[: space if space > limit // 4 else limit].rstrip()}…"
