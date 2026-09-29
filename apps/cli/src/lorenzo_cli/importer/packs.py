"""What is in a pack (RFC 0025 R7, ADR 0145).

A pack lists its items by display name (`["Rations, days of", 5, 2]`), and an entry ending in
`, with:` is a container that the entries after it go inside. The contents are stored in the
tenant, in the pack item's public description, as a list a person can read and a program can parse:

    This pack contains:

    - 1 x [Backpack](basic-gear-backpack)
      - 5 x [Rations, days of](basic-gear-rations-days-of)
      - 1 x [Tinderbox](basic-gear-tinderbox)
    - 1 x Alms box

A line with a link is an item of the catalog. A line without one is plain text, for something the
sheet itself has no gear entry for. The parser reads only lines of that shape and ignores the rest,
so a person who adds a sentence to the description can't break handing the pack out.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from lorenzo_cli.importer.mapping import Mapping

_WITH = re.compile(r",\s*with:\s*$", re.IGNORECASE)
INTRO = "This pack contains:"
# Nesting is two spaces per level; a pack has a container and what is in it, and no deeper.
MAX_DEPTH = 3

_LINKED = re.compile(
    r"^(?P<indent>(?:  )*)- (?P<quantity>\d+) x "
    r"\[(?P<label>[^\]\n]+)\]\((?P<slug>[A-Za-z0-9][A-Za-z0-9_-]{0,99})\)\s*$"
)
_PLAIN = re.compile(r"^(?P<indent>(?:  )*)- (?P<quantity>\d+) x (?P<label>[^\s\[\]()][^\n]*?)\s*$")


@dataclass(frozen=True)
class PackEntry:
    """One entry of a pack's `items`."""

    name: str
    quantity: int
    container: bool


@dataclass(frozen=True)
class PackLine:
    """One line of the contents list. `slug` is None for plain text."""

    depth: int
    quantity: int
    label: str
    slug: str | None = None


@dataclass(frozen=True)
class Unresolved:
    """A pack entry no catalog item could be found for."""

    name: str
    reason: str
    suggestion: str


@dataclass
class PackContents:
    lines: list[PackLine] = field(default_factory=list)
    unresolved: list[Unresolved] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def parse_entries(items: Iterable[Any]) -> list[PackEntry]:
    """The pack's `items` as entries; a quantity that isn't a whole number of one or more is one."""
    entries: list[PackEntry] = []
    for item in items:
        if not (isinstance(item, list) and item and isinstance(item[0], str) and item[0].strip()):
            continue
        name = " ".join(item[0].split())
        container = bool(_WITH.search(name))
        amount = item[1] if len(item) > 1 else ""
        quantity = amount if isinstance(amount, int) and not isinstance(amount, bool) else 1
        entries.append(PackEntry(_WITH.sub("", name).strip(), max(quantity, 1), container))
    return entries


@dataclass(frozen=True)
class Target:
    """An item of the run a pack entry can be linked to."""

    slug: str
    # The item's own name: a line is labelled with it, since its quantity counts these.
    display: str
    # How many units of the pack's name one of these is (a coil of 50 feet of rope), or 1.
    bundle: int = 1


class NameIndex:
    """The names the items of a run go by, to find what a pack's display name refers to."""

    def __init__(self) -> None:
        self._by_name: dict[str, set[tuple[str, str]]] = defaultdict(set)
        self._targets: dict[tuple[str, str], Target] = {}

    def add(
        self,
        list_name: str,
        key: str,
        target: Target,
        names: Iterable[str | None],
    ) -> None:
        self._targets[(list_name, key)] = target
        for name in names:
            if name and name.strip():
                self._by_name[" ".join(name.split()).lower()].add((list_name, key))

    def target(self, list_name: str, key: str) -> Target | None:
        return self._targets.get((list_name, key))

    def find(self, name: str) -> set[tuple[str, str]]:
        return self._by_name.get(name.lower(), set())


def _row_suggestion(name: str, hint: str) -> str:
    return f'[pack_items]\n"{name.lower()}" = "{hint}"   # or "text" if it is not a catalog item'


def _quantity_of(entry: PackEntry, target: Target, contents: PackContents) -> int:
    """A pack counts in the units of its name (50 feet); the item may be a bundle of them (a coil
    of 50 feet). Rounded up, and said so, when it doesn't divide."""
    if target.bundle <= 1:
        return entry.quantity
    whole, rest = divmod(entry.quantity, target.bundle)
    if rest == 0:
        return max(whole, 1)
    contents.notes.append(
        f"{entry.quantity} of {entry.name!r} is not a whole number of {target.display!r} "
        f"({target.bundle} each); rounded up to {whole + 1}"
    )
    return whole + 1


def resolve(entries: list[PackEntry], index: NameIndex, mapping: Mapping) -> PackContents:
    """Link each entry to an item of the run, by the map's row or by an exact name; what neither
    finds stays plain text and is reported."""
    contents = PackContents()
    depth = 0
    for entry in entries:
        line_depth = 0 if entry.container else depth
        if entry.container:
            depth = 1
        target: Target | None = None
        row = mapping.pack_items.get(entry.name.lower())
        if row == "text":
            pass
        elif row is not None:
            list_name, _, key = row.partition(":")
            target = index.target(list_name, key)
            if target is None:
                contents.unresolved.append(
                    Unresolved(
                        entry.name,
                        f"the map points {entry.name!r} at {row!r}, which isn't in this run",
                        _row_suggestion(entry.name, "gear:key"),
                    )
                )
        else:
            hits = index.find(entry.name)
            if len(hits) == 1:
                target = index.target(*next(iter(hits)))
            elif hits:
                choices = sorted(hits)
                names = ", ".join(f"{lst}:{key}" for lst, key in choices)
                contents.unresolved.append(
                    Unresolved(
                        entry.name,
                        f"{entry.name!r} could be any of {names}",
                        _row_suggestion(entry.name, f"{choices[0][0]}:{choices[0][1]}"),
                    )
                )
            else:
                contents.unresolved.append(
                    Unresolved(
                        entry.name,
                        f"no item in this run is called {entry.name!r}",
                        _row_suggestion(entry.name, "gear:key"),
                    )
                )
        if target is None:
            contents.lines.append(PackLine(line_depth, entry.quantity, entry.name))
        else:
            quantity = _quantity_of(entry, target, contents)
            contents.lines.append(PackLine(line_depth, quantity, target.display, target.slug))
    return contents


def render(lines: list[PackLine]) -> str:
    """The description text: an introduction, then the list."""
    body = []
    for line in lines:
        target = f"[{line.label}]({line.slug})" if line.slug else line.label
        body.append(f"{'  ' * line.depth}- {line.quantity} x {target}")
    return INTRO + "\n\n" + "\n".join(body)


def parse_description(text: str) -> list[PackLine]:
    """The contents list of a description; every line that isn't one is ignored."""
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
