"""Finding each line's item (ADR 0193, RFC 0035 section 3). In this order, the first hit wins, and
everything is compared without case and without surrounding spaces:

1. `ref` as an instance id of the owner's own item (moves it, with `--add`)
2. `ref` (or `item`) as an item id
3. `ref` (or `item`) as a slug
4. the name as an exact title
5. the name written another way (the preprocessing tables)
6. nothing found: a placeholder

What may be matched is what the caller may see: the catalog `lorenzo item list` shows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

from lorenzo_cli.client.models import ItemOut
from lorenzo_cli.client.transport import LorenzoClient
from lorenzo_cli.importer import tenant_view
from lorenzo_cli.inventory.format import Line
from lorenzo_cli.inventory.preprocess import Table
from lorenzo_cli.self_service import catalog

PLACEHOLDER_SLUG = "unsorted"

Via = Literal["instance", "id", "slug", "title", "spelling", "placeholder"]


@dataclass(frozen=True)
class Match:
    via: Via
    item: ItemOut | None = None  # what to make, None for a placeholder
    instance_id: UUID | None = None  # an item of the owner's own that the file names
    note: str | None = None  # why a line became a placeholder when that is worth saying


@dataclass
class Library:
    """What a line can be matched against, read once."""

    items: dict[UUID, ItemOut] = field(default_factory=dict)
    titles: dict[str, list[ItemOut]] = field(default_factory=dict)
    slugs: dict[str, UUID] = field(default_factory=dict)
    placeholder_id: UUID | None = None
    instances: set[UUID] = field(default_factory=set)  # the owner's own items already there

    def lookup(self, name: str) -> list[ItemOut]:
        return self.titles.get(name.strip().lower(), [])


def _uuid(text: str | None) -> UUID | None:
    if text is None:
        return None
    try:
        return UUID(text.strip())
    except ValueError:
        return None


def references(lines: list[Line]) -> list[str]:
    """The slugs the file mentions, to resolve in one go."""
    found = {r.strip() for line in lines for r in (line.ref, line.item) if r and _uuid(r) is None}
    found.add(PLACEHOLDER_SLUG)
    return sorted(found)


def read_library(
    client: LorenzoClient, tenant_id: UUID, lines: list[Line], instances: set[UUID]
) -> Library:
    library = Library(instances=instances)
    for item in catalog(client, tenant_id):
        library.items[item.entity_id] = item
        library.titles.setdefault(item.title.strip().lower(), []).append(item)
    for slug, hit in tenant_view.resolve_slugs(client, tenant_id, references(lines)).items():
        if "item" in hit.kinds:
            library.slugs[slug.lower()] = hit.entity_id
    library.placeholder_id = library.slugs.get(PLACEHOLDER_SLUG)
    return library


def match(line: Line, library: Library, table: Table) -> Match:
    for reference in (line.ref, line.item):
        if reference is None:
            continue
        found = _uuid(reference)
        if found is not None and found in library.instances:
            return Match("instance", instance_id=found)
    for reference in (line.ref, line.item):
        if reference is None:
            continue
        found = _uuid(reference)
        if found is not None and found in library.items:
            return Match("id", library.items[found])
        slug = library.slugs.get(reference.strip().lower())
        if slug is not None and slug in library.items:
            return Match("slug", library.items[slug])

    named = library.lookup(line.name)
    if len(named) == 1:
        return Match("title", named[0])
    if len(named) > 1:
        return Match(
            "placeholder",
            note=f"“{line.name}” is the title of {len(named)} items, so none was picked",
        )
    for other in table.alternatives(line.name):
        found_items = library.lookup(other)
        if len(found_items) == 1:
            return Match("spelling", found_items[0], note=f"read as “{other}”")
    return Match("placeholder")
