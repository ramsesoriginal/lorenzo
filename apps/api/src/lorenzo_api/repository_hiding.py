"""Hiding the entries of a repository built on another - ADR 0437, RFC 0051 (H4).

A repository B built on A may carry A *hidden* (`inclusion = hide`, `repository_inclusion`): a
library that copies B holds A's entries and cannot see them, while the entries that are B's own
inherit from them, evaluate their formulas through them and take their updates. This module is
everything about that except the read filter itself (`entry_visibility`, where every read of an
entry already asks the gate of ADR 0305) and the choice (`repository_inclusion`):

- What a record brings: `carries_of` reads a release's `sources` into the record the library keeps
  (`repository_copy.carries`), so what is hidden is derived from the library's own records and
  never from another repository.
- The derivation: `hidden_sources` and `refresh_hidden` set the flag on the copy link of each
  entry (`repository_copy_link_entity.hidden`): *show wins*, a repository's entries are hidden only
  while every repository the library holds that brings it hides it, and nothing the library copied
  for itself is ever hidden.
- What an update says of hidden rows: `HiddenChanges` and the label for it.
- What a hidden row is no longer needed for, and so goes with the update that drops it:
  `unused_hidden_entries`.

Only a library hides: a repository's copy of A is the rows its own release is built from, and its
Owner authors on top of it, so it is never hidden from its members (the choice it makes for its own
release is its Owner's, within A's terms).
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import exists, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.models import (
    Containment,
    EntityLocation,
    EntityPrototype,
    GroupMember,
    LocationPart,
    MapPlacement,
    Ownership,
    Relationship,
    RepositoryCopy,
    RepositoryCopyLinkEntity,
    Tenant,
    TenantKind,
)
from lorenzo_api.repository_content import Content

__all__ = [
    "HIDDEN_ENTRY",
    "HiddenChanges",
    "carries_of",
    "hidden_label",
    "hidden_sources",
    "refresh_hidden",
    "scrub_rows",
    "unused_hidden_entries",
]

# How a hidden entry is called wherever a name would give it away: a provenance line, a conflict,
# the words of an update (RFC 0051, "Words").
HIDDEN_ENTRY = "a hidden entry"


def carries_of(content: Content, repository_id: uuid.UUID, *, for_itself: bool) -> dict[str, str]:
    """What a repository brings separate, as its release says (`Content.sources`): each source it
    shows or hides, by id, and not the ones it includes (those are its own rows). `for_itself` is
    true where the library copied the repository itself, rather than as a step of another: what it
    brings of itself is then shown, whatever another repository says of it."""
    carried = {
        str(source_id): source["inclusion"]
        for source_id, source in content.sources.items()
        if source["inclusion"] in ("show", "hide")
    }
    if for_itself:
        carried[str(repository_id)] = "show"
    return carried


def hidden_sources(records: list[dict[str, str]]) -> set[uuid.UUID]:
    """The repositories whose entries a library hides, from what each of its copy records carries
    (`carries_of`): at least one hides it and none shows it. A repository nothing brings, or that
    the library copied for itself, is shown."""
    modes: dict[str, set[str]] = defaultdict(set)
    for carried in records:
        for source, mode in carried.items():
            modes[source].add(mode)
    return {uuid.UUID(source) for source, mode in modes.items() if mode == {"hide"}}


async def refresh_hidden(session: AsyncSession, tenant_id: uuid.UUID) -> bool:
    """Derives which entries the tenant hides from its copy records and writes the flag on each
    copy link, then `tenant.hides_entries`. Runs after every copy, every update and every removal
    of a copy, so the flag is always what the records say. Returns whether anything is hidden now.

    Only a library hides: a repository's rows are the ones its own release is built from."""
    tenant = await session.get(Tenant, tenant_id)
    if tenant is None:
        return False
    hidden: set[uuid.UUID] = set()
    if tenant.kind is not TenantKind.REPOSITORY:
        hidden = hidden_sources(
            list(
                await session.scalars(
                    select(RepositoryCopy.carries).where(RepositoryCopy.tenant_id == tenant_id)
                )
            )
        )
    link = RepositoryCopyLinkEntity
    unhide = update(link).where(link.tenant_id == tenant_id, link.hidden.is_(True))
    if hidden:
        unhide = unhide.where(link.source_tenant_id.not_in(hidden))
    await session.execute(unhide.values(hidden=False))
    if hidden:
        await session.execute(
            update(link)
            .where(
                link.tenant_id == tenant_id,
                link.hidden.is_(False),
                link.entity_id.is_not(None),
                link.source_tenant_id.in_(hidden),
            )
            .values(hidden=True)
        )
    now = bool(
        await session.scalar(
            select(
                exists().where(
                    link.tenant_id == tenant_id,
                    link.hidden.is_(True),
                )
            )
        )
    )
    if tenant.hides_entries != now:
        tenant.hides_entries = now
        await session.flush()
    return now


def scrub_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The rows a release called breaking or warned of, with the entries a library hides not named:
    an entry (or a parent attached to one) is "a hidden entry" and its detail says so (ADR 0437).
    The release is a repository's account of itself and names what it changed; the library that
    holds it hidden is not told which."""
    return [
        {
            **row,
            "name": HIDDEN_ENTRY,
            "detail": f"{HIDDEN_ENTRY.capitalize()} changed in a way that breaks libraries that "
            "copied it.",
        }
        if row.get("kind") in ("entity", "attachment")
        else row
        for row in rows
    ]


def hidden_label(count: int) -> str:
    """The words for what an update does to hidden entries, which are never named: "1 change to a
    hidden entry", "3 changes to hidden entries" (RFC 0051, "Words")."""
    return (
        f"{count} change to a hidden entry" if count == 1 else f"{count} changes to hidden entries"
    )


@dataclass
class HiddenChanges:
    """What an update of one repository does to the entries the library hides: counts and no names.
    `breaking` is how many of them a release since the library last updated called breaking, which
    the library acknowledges as one line (`acknowledge_hidden_breaking`). The rows themselves are
    kept for the engine that applies them with the rest, and are never read out: a hidden row is
    not named."""

    changed_rows: list[Any] = field(default_factory=list)
    added_rows: list[Any] = field(default_factory=list)
    removed_rows: list[Any] = field(default_factory=list)

    @property
    def changed(self) -> int:
        return len(self.changed_rows)

    @property
    def added(self) -> int:
        return len(self.added_rows)

    @property
    def removed(self) -> int:
        return len(self.removed_rows)

    @property
    def total(self) -> int:
        return self.changed + self.added + self.removed

    @property
    def breaking(self) -> int:
        return sum(
            1 for row in (*self.changed_rows, *self.added_rows, *self.removed_rows) if row.breaking
        )

    @property
    def label(self) -> str | None:
        return hidden_label(self.total) if self.total else None


async def unused_hidden_entries(
    session: AsyncSession, tenant_id: uuid.UUID, candidates: set[uuid.UUID]
) -> set[uuid.UUID]:
    """Of the entries in `candidates` (local ids of hidden entries whose repository no longer
    brings them), those nothing visible uses: no entry that is not itself hidden has it as a
    parent, a container, an owner, a group, a place or an end of a relationship, and no map
    places it. Those go with the update that drops them (RFC 0051, default 4); the others stay,
    hidden, until what uses them lets go."""
    if not candidates:
        return set()
    link = RepositoryCopyLinkEntity
    hidden_ids = select(link.entity_id).where(
        link.tenant_id == tenant_id, link.hidden.is_(True), link.entity_id.is_not(None)
    )
    used: set[uuid.UUID] = set()

    async def used_by(column: Any, owner: Any) -> None:
        used.update(
            await session.scalars(
                select(column).where(
                    column.in_(candidates), owner.not_in(hidden_ids), owner.is_not(None)
                )
            )
        )

    await used_by(EntityPrototype.prototype_id, EntityPrototype.entity_id)
    await used_by(Containment.parent_entity_id, Containment.child_entity_id)
    await used_by(Ownership.owner_character_id, Ownership.owned_entity_id)
    await used_by(LocationPart.parent_entity_id, LocationPart.child_entity_id)
    await used_by(EntityLocation.location_entity_id, EntityLocation.entity_id)
    await used_by(GroupMember.group_entity_id, GroupMember.character_entity_id)
    await used_by(MapPlacement.map_entity_id, MapPlacement.entry_entity_id)
    for end, other in (
        (Relationship.end_a, Relationship.end_b),
        (Relationship.end_b, Relationship.end_a),
    ):
        used.update(
            await session.scalars(
                select(end).where(
                    end.in_(candidates),
                    Relationship.tenant_id == tenant_id,
                    other.not_in(hidden_ids),
                )
            )
        )
    return candidates - used
