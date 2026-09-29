"""What is in a pack (RFC 0025 R7, ADR 0145 and 0146).

A pack lists its contents by display name (`["Rations, days of", 5, 2]`), and an entry ending in
`, with:` is a container that the entries after it go inside. The contents are stored in the
tenant, in the pack item's public description, as a list a person can read and a program can parse:

    This pack contains:

    - 1 x [Backpack](basic-gear-backpack)
      - 5 x [Rations, days of](basic-gear-rations-days-of)
      - 1 x [Alms box](basic-gear-alms-box)

Every line links to an item of the catalog. An entry the sheet has no gear entry for (an alms box)
becomes a simple plain item of its own, so the pack can be handed out complete; the importer makes
it, and says so when nothing in the map told it to. A line without a link is still read (as plain
text) so that a person can write one by hand. The parser reads only lines of that shape and ignores
the rest, so a sentence added to the description can't break handing the pack out.

Resolving a pack takes two steps, because the slugs of the plain items don't exist until every
item of the run has one: first decide what each entry refers to, then build the lines.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from collections.abc import Mapping as MappingType
from dataclasses import dataclass, field
from typing import Any, Literal

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
    # The weight of one, if the source gives it: a plain item made for the entry keeps it.
    weight: float | None = None


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
        each = item[2] if len(item) > 2 else ""
        weight = (
            float(each) if isinstance(each, int | float) and not isinstance(each, bool) else None
        )
        entries.append(
            PackEntry(
                _WITH.sub("", name).strip(),
                max(quantity, 1),
                container,
                weight if weight and weight > 0 else None,
            )
        )
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

    def add(self, list_name: str, key: str, target: Target, names: Iterable[str | None]) -> None:
        self._targets[(list_name, key)] = target
        for name in names:
            if name and name.strip():
                self._by_name[" ".join(name.split()).lower()].add((list_name, key))

    def set_slugs(self, slugs: MappingType[tuple[str, str], str]) -> None:
        """Slugs are only final after every item has one; the targets are filled in then."""
        for (list_name, key), target in list(self._targets.items()):
            self._targets[(list_name, key)] = Target(
                slugs.get((list_name, key), target.slug), target.display, target.bundle
            )

    def target(self, list_name: str, key: str) -> Target | None:
        return self._targets.get((list_name, key))

    def find(self, name: str) -> set[tuple[str, str]]:
        return self._by_name.get(name.lower(), set())


@dataclass(frozen=True)
class Ref:
    """What an entry refers to: an item of the run (`link`), a plain item to be made for it
    (`item`, with its key in the `gear` list), or nothing (`text`)."""

    kind: Literal["link", "item", "text"]
    list_name: str = ""
    key: str = ""


@dataclass(frozen=True)
class Placed:
    entry: PackEntry
    depth: int
    ref: Ref


@dataclass
class Resolution:
    placed: list[Placed] = field(default_factory=list)
    unresolved: list[Unresolved] = field(default_factory=list)


def plain_key(name: str) -> str:
    """The key of the plain item made for an entry: its name, lower-cased. One item per name,
    however many packs mention it."""
    return " ".join(name.lower().split())


def _row_suggestion(name: str, hint: str) -> str:
    return (
        f'[pack_items]\n"{name.lower()}" = "{hint}"'
        '   # or "item" if it is a plain item of its own, "text" if it is no item'
    )


def resolve_refs(entries: list[PackEntry], index: NameIndex, mapping: Mapping) -> Resolution:
    """Decide what each entry refers to, by the map's row or by an exact name, never by guessing.
    What neither finds becomes a plain item and is reported, so it can be linked instead."""
    resolution = Resolution()
    depth = 0
    for entry in entries:
        line_depth = 0 if entry.container else depth
        if entry.container:
            depth = 1
        ref = _ref_for(entry, index, mapping, resolution)
        resolution.placed.append(Placed(entry, line_depth, ref))
    return resolution


def _ref_for(entry: PackEntry, index: NameIndex, mapping: Mapping, out: Resolution) -> Ref:
    key = plain_key(entry.name)
    # A gear entry already under that key (its name just isn't the pack's) is that item.
    plain = Ref("link", "gear", key) if index.target("gear", key) else Ref("item", "gear", key)
    instead = (
        "the gear entry of that name is used" if plain.kind == "link" else "a plain item is made"
    )
    row = mapping.pack_items.get(entry.name.lower())
    if row == "text":
        return Ref("text")
    if row == "item":
        return plain
    if row is not None:
        list_name, _, key = row.partition(":")
        if index.target(list_name, key) is not None:
            return Ref("link", list_name, key)
        out.unresolved.append(
            Unresolved(
                entry.name,
                f"the map points {entry.name!r} at {row!r}, which isn't in this run; "
                f"{instead} instead",
                _row_suggestion(entry.name, "gear:key"),
            )
        )
        return plain
    hits = index.find(entry.name)
    if len(hits) == 1:
        list_name, key = next(iter(hits))
        return Ref("link", list_name, key)
    if hits:
        choices = sorted(hits)
        names = ", ".join(f"{lst}:{key}" for lst, key in choices)
        reason = f"{entry.name!r} could be any of {names}; {instead} instead"
        hint = f"{choices[0][0]}:{choices[0][1]}"
    else:
        reason = f"no item in this run is called {entry.name!r}; {instead} for it"
        hint = "gear:key"
    out.unresolved.append(Unresolved(entry.name, reason, _row_suggestion(entry.name, hint)))
    return plain


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


def build_contents(
    resolution: Resolution,
    index: NameIndex,
    plain_slugs: MappingType[str, str] | None = None,
) -> PackContents:
    """The lines, once every slug is known. `plain_slugs` maps a plain item's key to its slug."""
    contents = PackContents(unresolved=list(resolution.unresolved))
    for placed in resolution.placed:
        entry, ref = placed.entry, placed.ref
        if ref.kind == "link":
            target = index.target(ref.list_name, ref.key)
            assert target is not None
            quantity = _quantity_of(entry, target, contents)
            contents.lines.append(PackLine(placed.depth, quantity, target.display, target.slug))
        elif ref.kind == "item":
            slug = (plain_slugs or {}).get(ref.key)
            contents.lines.append(PackLine(placed.depth, entry.quantity, entry.name, slug))
        else:
            contents.lines.append(PackLine(placed.depth, entry.quantity, entry.name))
    return contents


def resolve(entries: list[PackEntry], index: NameIndex, mapping: Mapping) -> PackContents:
    """Both steps, for a caller with no plain items to make (their lines have no link)."""
    return build_contents(resolve_refs(entries, index, mapping), index)


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
