"""Relationships: entries that tie two entries (ADR 0399)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Query, Response
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Select, exists, select
from sqlalchemy.orm import aliased

from lorenzo_api.activity_log import record_activity
from lorenzo_api.dependencies import (
    CurrentUser,
    ParamsDep,
    SessionDep,
    get_tenant_or_404,
    set_tenant_rls_context,
)
from lorenzo_api.entity_access import prototype_descendants_cte
from lorenzo_api.entity_kinds import create_entry
from lorenzo_api.entry_visibility import visible_entry_clause
from lorenzo_api.etag import check_if_match, etag_for
from lorenzo_api.exceptions import (
    EntityNotFoundError,
    InvalidRelationshipError,
    MapPreconditionRequiredError,
)
from lorenzo_api.information_visibility import InformationVisibility
from lorenzo_api.models import Entity, EntityAudience, Relationship
from lorenzo_api.relationships import (
    MAX_END_IDS,
    require_relationship_room,
    touch_relationship,
)
from lorenzo_api.routers.connections import EntryStub, _visible_entry, entry_stubs
from lorenzo_api.routers.locations import manages, require_manager, standing
from lorenzo_api.schemas.common import Slug

router = APIRouter(
    prefix="/tenants/{tenant_id}",
    tags=["relationships"],
    dependencies=[Depends(get_tenant_or_404)],
)

_NOT_FOUND = "No such relationship in this library"


class RelationshipOut(EntryStub):
    """A relationship and its two ends. `one_way` is true for a tie that goes from `end_a` to
    `end_b` only."""

    end_a: EntryStub
    end_b: EntryStub
    one_way: bool
    updated_at: datetime
    can_manage: bool
    # Only for those who may manage relationships: whether everyone in the library may see it.
    is_public: bool | None = None


class RelationshipCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    slug: Slug | None = None
    end_a: uuid.UUID
    end_b: uuid.UUID
    one_way: bool = False
    # The type of relationship it is, as entries: parent of, ally of (ADR 0399).
    prototypes: list[uuid.UUID] = Field(default_factory=list, max_length=20)
    is_public: bool = False


class RelationshipPut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    end_a: uuid.UUID
    end_b: uuid.UUID
    one_way: bool = False


async def _commit(session: SessionDep, tenant: uuid.UUID) -> None:
    await session.commit()
    await set_tenant_rls_context(session, tenant)


def _out(
    stubs: dict[uuid.UUID, EntryStub],
    *,
    identity: uuid.UUID,
    end_a: uuid.UUID,
    end_b: uuid.UUID,
    one_way: bool | None,
    updated_at: datetime,
    manage: bool,
    is_public: bool | None,
) -> RelationshipOut:
    return RelationshipOut(
        **stubs[identity].model_dump(),
        end_a=stubs[end_a],
        end_b=stubs[end_b],
        one_way=bool(one_way),
        updated_at=updated_at,
        can_manage=manage,
        is_public=is_public if manage else None,
    )


async def _read(
    session: SessionDep, vis: InformationVisibility, tenant: uuid.UUID, identity: uuid.UUID
) -> tuple[Entity, Relationship]:
    """A relationship the reader may see with both ends: `visible_entry_clause` holds the rule, so
    a hidden one and a missing one are the same 404."""
    found = (
        await session.execute(
            select(Entity, Relationship)
            .join(Relationship, Relationship.entity_id == Entity.id)
            .where(
                Entity.tenant_id == tenant,
                Entity.id == identity,
                visible_entry_clause(vis, Entity.id),
            )
        )
    ).first()
    if found is None:
        raise EntityNotFoundError(detail=_NOT_FOUND)
    return found[0], found[1]


async def _built(
    session: SessionDep,
    vis: InformationVisibility,
    tenant: uuid.UUID,
    entity: Entity,
    marker: Relationship,
) -> RelationshipOut:
    stubs = await entry_stubs(session, tenant, {entity.id, marker.end_a, marker.end_b})
    manage = manages(vis)
    is_public = None
    if manage:
        audience = await session.get(EntityAudience, entity.id)
        is_public = True if audience is None else audience.is_public
    return _out(
        stubs,
        identity=entity.id,
        end_a=marker.end_a,
        end_b=marker.end_b,
        one_way=marker.one_way,
        updated_at=entity.updated_at,
        manage=manage,
        is_public=is_public,
    )


async def _after_write(
    session: SessionDep, vis: InformationVisibility, tenant: uuid.UUID, identity: uuid.UUID
) -> RelationshipOut:
    """What a write answers: the relationship as it now is. The writer's own sight was resolved
    before the entry existed, so it is read without that filter; the writer made it."""
    entity = await session.get(Entity, identity)
    marker = await session.get(Relationship, identity)
    assert entity is not None and marker is not None
    await session.refresh(entity)
    return await _built(session, vis, tenant, entity, marker)


async def _check_ends(
    session: SessionDep, user: CurrentUser, tenant: uuid.UUID, end_a: uuid.UUID, end_b: uuid.UUID
) -> None:
    if end_a == end_b:
        raise InvalidRelationshipError(detail="A relationship ties two different entries.")
    for end in (end_a, end_b):
        await _visible_entry(session, user, tenant, end)
        if await session.scalar(select(exists().where(Relationship.entity_id == end))):
            raise InvalidRelationshipError(detail="An end of a relationship is not itself one.")


async def _prototypes(
    session: SessionDep, user: CurrentUser, tenant: uuid.UUID, ids: list[uuid.UUID]
) -> list[uuid.UUID]:
    unique = list(dict.fromkeys(ids))
    for identity in unique:
        await _visible_entry(session, user, tenant, identity)
    return unique


@router.get("/relationships")
async def list_relationships(
    tenant_id: uuid.UUID,
    params: ParamsDep,
    session: SessionDep,
    user: CurrentUser,
    end: Annotated[
        uuid.UUID | None,
        Query(description="Only the relationships that have this entry as an end."),
    ] = None,
    end_a_in: Annotated[
        list[uuid.UUID] | None,
        Query(max_length=MAX_END_IDS, description="Only those whose first end is one of these."),
    ] = None,
    end_b_in: Annotated[
        list[uuid.UUID] | None,
        Query(max_length=MAX_END_IDS, description="Only those whose second end is one of these."),
    ] = None,
    type_id: Annotated[
        uuid.UUID | None,
        Query(
            alias="type",
            description="Only the relationships that name this type, or one that inherits from it.",
        ),
    ] = None,
    q: Annotated[
        str | None,
        Query(description="Case-insensitive substring match against the relationship's name."),
    ] = None,
) -> Page[RelationshipOut]:
    """The relationships the reader may see with both their ends, by name then id (ADR 0399). A
    hidden relationship or end is absent from every row, count and page."""
    vis = await standing(session, user, tenant_id)
    # The audience is joined under its own name: the visibility predicate has its own.
    own = aliased(EntityAudience)
    stmt: Select[Any] = (
        select(
            Entity.id,
            Relationship.end_a,
            Relationship.end_b,
            Relationship.one_way,
            Entity.updated_at,
            own.is_public,
        )
        .join(Relationship, Relationship.entity_id == Entity.id)
        .outerjoin(own, own.entity_id == Entity.id)
        .where(Entity.tenant_id == tenant_id, visible_entry_clause(vis, Entity.id))
        .order_by(Entity.name, Entity.id)
    )
    if end is not None:
        stmt = stmt.where((Relationship.end_a == end) | (Relationship.end_b == end))
    if end_a_in:
        stmt = stmt.where(Relationship.end_a.in_(end_a_in))
    if end_b_in:
        stmt = stmt.where(Relationship.end_b.in_(end_b_in))
    if type_id is not None:
        await _visible_entry(session, user, tenant_id, type_id)
        descendants = prototype_descendants_cte(type_id, tenant_id)
        stmt = stmt.where(Entity.id.in_(select(descendants.c.descendant_id)))
    if q is not None:
        stmt = stmt.where(Entity.name.icontains(q, autoescape=True))
    manage = manages(vis)

    async def rows(found: Any) -> list[RelationshipOut]:
        ids = {row[0] for row in found} | {row[1] for row in found} | {row[2] for row in found}
        stubs = await entry_stubs(session, tenant_id, ids)
        return [
            _out(
                stubs,
                identity=row[0],
                end_a=row[1],
                end_b=row[2],
                one_way=row[3],
                updated_at=row[4],
                manage=manage,
                is_public=True if row[5] is None else row[5],
            )
            for row in found
        ]

    page: Page[RelationshipOut] = await apaginate(session, stmt, params, transformer=rows)
    return page


@router.post("/relationships", status_code=201)
async def create_relationship(
    tenant_id: uuid.UUID,
    body: RelationshipCreate,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> RelationshipOut:
    """A relationship between two entries the writer sees, restricted unless `is_public`."""
    vis = await require_manager(session, user, tenant_id)
    await require_relationship_room(session, tenant_id=tenant_id)
    entity = await add_relationship(session, user, tenant_id, body)
    await _commit(session, tenant_id)
    out = await _after_write(session, vis, tenant_id, entity.id)
    response.headers["ETag"] = etag_for(out.updated_at)
    return out


async def add_relationship(
    session: SessionDep, user: CurrentUser, tenant_id: uuid.UUID, body: RelationshipCreate
) -> Entity:
    """Adds one relationship to the transaction without committing it: the single create and the
    bulk write (ADR 0400) both make theirs here. The caller has checked the writer's standing and
    the library's room."""
    await _check_ends(session, user, tenant_id, body.end_a, body.end_b)
    prototypes = await _prototypes(session, user, tenant_id, body.prototypes)
    entity = await create_entry(
        session,
        tenant_id=tenant_id,
        user_id=user.id,
        name=body.name,
        slug=body.slug,
        kinds=[],
        parents=prototypes,
        in_public_catalog=False,
        entity_id=body.id,
    )
    session.add(
        Relationship(
            entity_id=entity.id,
            tenant_id=tenant_id,
            end_a=body.end_a,
            end_b=body.end_b,
            one_way=True if body.one_way else None,
        )
    )
    # A new relationship is restricted until its audience is opened (ADR 0404).
    session.add(EntityAudience(entity_id=entity.id, tenant_id=tenant_id, is_public=body.is_public))
    await session.flush()
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="relationship.created",
        target_type="entity",
        target_id=entity.id,
    )
    return entity


@router.get("/relationships/{relationship_id}")
async def get_relationship(
    tenant_id: uuid.UUID,
    relationship_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> RelationshipOut:
    vis = await standing(session, user, tenant_id)
    found, marker = await _read(session, vis, tenant_id, relationship_id)
    out = await _built(session, vis, tenant_id, found, marker)
    response.headers["ETag"] = etag_for(out.updated_at)
    return out


@router.put("/relationships/{relationship_id}")
async def put_relationship(
    tenant_id: uuid.UUID,
    relationship_id: uuid.UUID,
    body: RelationshipPut,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> RelationshipOut:
    """Replaces the ends and the direction under `If-Match`."""
    vis = await require_manager(session, user, tenant_id)
    entity, marker = await _read(session, vis, tenant_id, relationship_id)
    if if_match is None:
        raise MapPreconditionRequiredError(detail="Send the relationship's ETag as If-Match.")
    check_if_match(if_match, updated_at=entity.updated_at)
    await _check_ends(session, user, tenant_id, body.end_a, body.end_b)
    marker.end_a = body.end_a
    marker.end_b = body.end_b
    marker.one_way = True if body.one_way else None
    await session.flush()
    entity = await touch_relationship(
        session, tenant_id=tenant_id, relationship_id=relationship_id, user_id=user.id
    )
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="relationship.updated",
        target_type="entity",
        target_id=relationship_id,
    )
    await _commit(session, tenant_id)
    found, current = await _read(session, vis, tenant_id, relationship_id)
    out = await _built(session, vis, tenant_id, found, current)
    response.headers["ETag"] = etag_for(out.updated_at)
    return out
