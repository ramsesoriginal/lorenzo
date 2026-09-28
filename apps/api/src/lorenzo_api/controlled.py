"""What a being's or a group's board shows (RFC 0031, ADR 0130): which item
instances it controls, and which column each one is in. Plain Python over
what routers/item_instances.py's controlled-by walk loaded, with no queries
of its own, so the rules can be read and tested on their own.

The five words, for a holder:

- Personal: owned by the holder itself.
- Owned: owned by the holder, or by a group it's a member of.
- Equipped: contained directly by the holder, if it's a being.
- Carried: contained under the holder at any depth, if it's a being. A group
  carries nothing (ADR 0124).
- Controlled: what the board shows - see controlled_ids.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Set
from dataclasses import dataclass, field
from functools import cache, cached_property
from typing import Literal

ColumnKind = Literal["equipped", "not_carried", "container", "read_only"]


@dataclass(frozen=True)
class Holdings:
    """What the walk from a holder found. `parents` is every containment row
    under the walk, child to parent, for item instances and any other entity
    alike, and every row into whatever directly holds something the walk
    found - so a column knows everything its container holds. `owners` is
    every item instance the walk found, the holder and its groups aside,
    with its owner (None if nobody owns it).
    """

    holder_id: uuid.UUID
    holder_is_being: bool
    group_ids: frozenset[uuid.UUID]
    parents: Mapping[uuid.UUID, uuid.UUID]
    owners: Mapping[uuid.UUID, uuid.UUID | None]

    @cached_property
    def children(self) -> dict[uuid.UUID, list[uuid.UUID]]:
        children: dict[uuid.UUID, list[uuid.UUID]] = {}
        for child, parent in self.parents.items():
            children.setdefault(parent, []).append(child)
        return children

    def below(self, root: uuid.UUID) -> set[uuid.UUID]:
        """Everything contained under root, at any depth, root itself aside.
        Each entity is visited once, so a containment cycle (ADR 0016) can't
        loop."""
        seen: set[uuid.UUID] = set()
        stack = list(self.children.get(root, ()))
        while stack:
            node = stack.pop()
            if node in seen or node == root:
                continue
            seen.add(node)
            stack.extend(self.children.get(node, ()))
        return seen


def controlled_ids(holdings: Holdings) -> frozenset[uuid.UUID]:
    """RFC 0031 §2. Controlled is:

    - everything Carried, except the direct contents of an item instance
      that isn't Owned and holds, at any depth, nothing Personal;
    - everything Owned;
    - the direct contents of every Owned item instance, except those of one
      that isn't Personal and holds, at any depth, nothing Owned.

    Carrying something, you look straight inside it; set down, only your own
    things and what's with them matter. Putting something of yours into a
    container shows you the rest of it.
    """
    owning = {holdings.holder_id, *holdings.group_ids}
    items = holdings.owners.keys()

    def personal(entity_id: uuid.UUID) -> bool:
        return holdings.owners.get(entity_id) == holdings.holder_id

    def owned(entity_id: uuid.UUID) -> bool:
        return holdings.owners.get(entity_id) in owning

    @cache
    def holds_personal(container: uuid.UUID) -> bool:
        return any(personal(inside) for inside in holdings.below(container))

    @cache
    def holds_owned(container: uuid.UUID) -> bool:
        return any(owned(inside) for inside in holdings.below(container))

    def seen_when_carried(in_item: uuid.UUID | None) -> bool:
        # Unless it's in something not Owned that holds nothing Personal.
        return in_item is None or owned(in_item) or holds_personal(in_item)

    def with_owned(in_item: uuid.UUID | None) -> bool:
        # In something Owned, unless that isn't Personal and holds nothing Owned.
        return (
            in_item is not None and owned(in_item) and (personal(in_item) or holds_owned(in_item))
        )

    carried = holdings.below(holdings.holder_id) if holdings.holder_is_being else set()
    controlled: set[uuid.UUID] = set()
    for entity_id in items:
        # The item instance it's directly in, if it's in one.
        container = holdings.parents.get(entity_id)
        in_item = container if container is not None and container in items else None
        if (
            owned(entity_id)
            or (entity_id in carried and seen_when_carried(in_item))
            or with_owned(in_item)
        ):
            controlled.add(entity_id)
    return frozenset(controlled)


@dataclass
class Column:
    """One column of a board, before it's named and ordered."""

    kind: ColumnKind
    container_id: uuid.UUID | None
    item_ids: list[uuid.UUID] = field(default_factory=list)
    contents_hidden: bool = False


def columns(
    holdings: Holdings, controlled: Set[uuid.UUID], containers: Set[uuid.UUID]
) -> list[Column]:
    """ADR 0130's columns, every Controlled item in the one for where it is:

    - equipped: what a being contains directly, always there for a being;
    - not_carried: what's in no container, always there;
    - container: one for every Controlled item instance that's a container
      (`containers`, those marked is_container) or has anything in it;
    - read_only: one for anything else that directly holds something
      Controlled - another being, an item instance that isn't Controlled,
      a place.

    Items come in id order. Equipped and not_carried come first; the rest
    are left for the caller to order, since that takes their names.
    """
    by_container: dict[uuid.UUID, Column] = {}
    if holdings.holder_is_being:
        by_container[holdings.holder_id] = Column("equipped", holdings.holder_id)
    not_carried = Column("not_carried", None)
    for entity_id in sorted(controlled):
        if entity_id in containers or entity_id in holdings.children:
            by_container[entity_id] = Column("container", entity_id)

    for entity_id in sorted(controlled):
        container = holdings.parents.get(entity_id)
        if container is None:
            not_carried.item_ids.append(entity_id)
            continue
        if container not in by_container:
            by_container[container] = Column("read_only", container)
        by_container[container].item_ids.append(entity_id)

    for container_id, column in by_container.items():
        listed = set(column.item_ids)
        column.contents_hidden = any(
            inside not in listed for inside in holdings.children.get(container_id, ())
        )

    equipped = [by_container.pop(holdings.holder_id)] if holdings.holder_is_being else []
    return [*equipped, not_carried, *by_container.values()]
