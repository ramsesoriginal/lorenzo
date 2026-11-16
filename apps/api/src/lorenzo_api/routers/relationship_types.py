"""The types of relationship a library has (ADR 0400): an entry is a type when relationships are of
it (directly or through what it inherits from), or when it holds the library's type stats.

A type is a prototype, so nothing makes one: this read only gathers them for the screen that
edits them, with how each reads and points, as the reader may see them."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select, text

from lorenzo_api.dependencies import CurrentUser, SessionDep, get_tenant_or_404
from lorenzo_api.entry_visibility import visible_entry_clause
from lorenzo_api.models import Entity, EntityPrototype, EntityStat, Relationship, Tenant
from lorenzo_api.routers.connections import EntryStub, entry_stubs
from lorenzo_api.routers.locations import standing

router = APIRouter(
    prefix="/tenants/{tenant_id}",
    tags=["relationships"],
    dependencies=[Depends(get_tenant_or_404)],
)

#: A read lists at most this many types.
MAX_TYPES_READ = 500


class RelationshipTypeOut(EntryStub):
    """One type: what it inherits from, how it points and reads, and how many relationships the
    reader sees that are directly of it."""

    parent_ids: list[uuid.UUID]
    directed: bool | None
    reads_as: str | None
    reads_as_back: str | None
    in_use: int


class RelationshipTypesOut(BaseModel):
    items: list[RelationshipTypeOut]


@router.get("/relationship-types")
async def list_relationship_types(
    tenant_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> RelationshipTypesOut:
    vis = await standing(session, user, tenant_id)
    tenant = await session.get_one(Tenant, tenant_id)
    stat_ids = [
        s
        for s in (
            tenant.relationship_directed_stat_id,
            tenant.relationship_reads_as_stat_id,
            tenant.relationship_reads_as_back_stat_id,
        )
        if s is not None
    ]
    # The types relationships the reader sees are directly of.
    used = {
        row[0]: row[1]
        for row in (
            await session.execute(
                select(EntityPrototype.prototype_id, func.count())
                .join(Relationship, Relationship.entity_id == EntityPrototype.entity_id)
                .where(
                    EntityPrototype.tenant_id == tenant_id,
                    visible_entry_clause(vis, EntityPrototype.entity_id),
                )
                .group_by(EntityPrototype.prototype_id)
            )
        ).all()
    }
    holders = (
        set(
            await session.scalars(
                select(EntityStat.entity_id).where(
                    EntityStat.tenant_id == tenant_id, EntityStat.stat_definition_id.in_(stat_ids)
                )
            )
        )
        if stat_ids
        else set()
    )
    seeds = list(set(used) | holders)
    ids: set[uuid.UUID] = set(seeds)
    if seeds:
        # What they inherit from, all the way up: a family of types is a type too.
        ancestors = await session.execute(
            text(
                """
                WITH RECURSIVE up(id) AS (
                  SELECT unnest(CAST(:seeds AS uuid[]))
                  UNION
                  SELECT ep.prototype_id FROM entity_prototype ep JOIN up ON ep.entity_id = up.id
                  WHERE ep.tenant_id = :tenant
                )
                SELECT id FROM up
                """
            ),
            {"seeds": seeds, "tenant": tenant_id},
        )
        ids |= {row[0] for row in ancestors}
    rows = (
        (
            await session.execute(
                select(Entity.id)
                .where(
                    Entity.tenant_id == tenant_id,
                    Entity.id.in_(ids),
                    visible_entry_clause(vis, Entity.id),
                )
                .order_by(Entity.name, Entity.id)
                .limit(MAX_TYPES_READ)
            )
        )
        .scalars()
        .all()
    )
    shown = set(rows)
    stubs = await entry_stubs(session, tenant_id, shown)
    parents: dict[uuid.UUID, list[uuid.UUID]] = {}
    for child, parent in (
        await session.execute(
            select(EntityPrototype.entity_id, EntityPrototype.prototype_id).where(
                EntityPrototype.tenant_id == tenant_id, EntityPrototype.entity_id.in_(shown)
            )
        )
    ).all():
        if parent in shown:
            parents.setdefault(child, []).append(parent)
    own: dict[tuple[uuid.UUID, uuid.UUID], EntityStat] = {}
    if stat_ids and shown:
        for stat in await session.scalars(
            select(EntityStat).where(
                EntityStat.tenant_id == tenant_id,
                EntityStat.entity_id.in_(shown),
                EntityStat.stat_definition_id.in_(stat_ids),
            )
        ):
            own[(stat.entity_id, stat.stat_definition_id)] = stat

    def held(entity: uuid.UUID, stat: uuid.UUID | None) -> EntityStat | None:
        return own.get((entity, stat)) if stat else None

    out: list[RelationshipTypeOut] = []
    for identity in rows:
        directed = held(identity, tenant.relationship_directed_stat_id)
        reads = held(identity, tenant.relationship_reads_as_stat_id)
        back = held(identity, tenant.relationship_reads_as_back_stat_id)
        out.append(
            RelationshipTypeOut(
                **stubs[identity].model_dump(),
                parent_ids=sorted(parents.get(identity, []), key=str),
                directed=directed.value_bool if directed else None,
                reads_as=reads.value_text if reads else None,
                reads_as_back=back.value_text if back else None,
                in_use=used.get(identity, 0),
            )
        )
    return RelationshipTypesOut(items=out)
