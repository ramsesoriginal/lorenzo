"""Relationships: entries that tie two entries (ADR 0399)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, Query, Response
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Select, Uuid, any_, exists, literal, select
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import aliased

from lorenzo_api.activity_log import record_activity
from lorenzo_api.dependencies import (
    CurrentUser,
    ParamsDep,
    SessionDep,
    get_tenant_or_404,
    set_tenant_rls_context,
)
from lorenzo_api.entity_access import (
    controlled_holder_entity_ids,
    group_ids_for_characters,
    prototype_descendants_cte,
)
from lorenzo_api.entity_kinds import create_entry
from lorenzo_api.entry_visibility import visible_entry_clause
from lorenzo_api.etag import check_if_match, etag_for
from lorenzo_api.exceptions import (
    EntityNotFoundError,
    InvalidRelationshipError,
    MapPreconditionRequiredError,
    RelationshipReadAsForbiddenError,
)
from lorenzo_api.information_visibility import InformationVisibility
from lorenzo_api.models import Entity, EntityAudience, Relationship, StoryEvent
from lorenzo_api.relationship_time import ReachLimitReachedError, classify, reach
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


AsOfState = Literal["holds", "not_yet", "ended", "unknown", "limit_reached"]


class RelationshipEntryOut(EntryStub):
    """A relationship and its two ends. `one_way` is true for a tie that goes from `end_a` to
    `end_b` only."""

    end_a: EntryStub
    end_b: EntryStub
    one_way: bool
    updated_at: datetime
    can_manage: bool
    # Only for those who may manage relationships: whether everyone in the library may see it.
    is_public: bool | None = None
    # The Events that bound it in time, when the reader may see them (ADR 0405). A limit the
    # reader cannot see is null here; it is not named in any field or error.
    starts_at: EntryStub | None = None
    ends_at: EntryStub | None = None
    # Only when the list was read `as_of` an Event: where it stands then.
    as_of: AsOfState | None = None


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
    # Optional limits in time, each an Event the writer sees (ADR 0405).
    starts_at: uuid.UUID | None = None
    ends_at: uuid.UUID | None = None


class RelationshipPut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    end_a: uuid.UUID
    end_b: uuid.UUID
    one_way: bool = False
    # Replaced with the rest: send null to leave a limit unset (ADR 0405).
    starts_at: uuid.UUID | None = None
    ends_at: uuid.UUID | None = None


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
    starts_at: uuid.UUID | None = None,
    ends_at: uuid.UUID | None = None,
    as_of: AsOfState | None = None,
) -> RelationshipEntryOut:
    """A relationship row. A limit's stub is only in `stubs` when the reader may see that Event,
    so a hidden one is null and leaves no trace."""
    return RelationshipEntryOut(
        **stubs[identity].model_dump(),
        end_a=stubs[end_a],
        end_b=stubs[end_b],
        one_way=bool(one_way),
        updated_at=updated_at,
        can_manage=manage,
        is_public=is_public if manage else None,
        starts_at=stubs.get(starts_at) if starts_at else None,
        ends_at=stubs.get(ends_at) if ends_at else None,
        as_of=as_of,
    )


async def visible_event_ids(
    session: SessionDep, vis: InformationVisibility, tenant: uuid.UUID, ids: set[uuid.UUID]
) -> set[uuid.UUID]:
    """Which of these Events the reader may see: only those get named in a relationship."""
    if not ids:
        return set()
    return set(
        await session.scalars(
            select(Entity.id)
            .join(StoryEvent, StoryEvent.entity_id == Entity.id)
            .where(
                Entity.tenant_id == tenant,
                Entity.id.in_(ids),
                visible_entry_clause(vis, Entity.id),
            )
        )
    )


async def build_rows(
    session: SessionDep,
    vis: InformationVisibility,
    tenant: uuid.UUID,
    found: Any,
    *,
    states: dict[uuid.UUID, AsOfState] | None = None,
) -> list[RelationshipEntryOut]:
    """Rows of `(id, end_a, end_b, one_way, updated_at, is_public, starts_at, ends_at)` as
    relationships, with each entry's stub read once and each limit named only if it is visible."""
    limits = {row[6] for row in found if row[6]} | {row[7] for row in found if row[7]}
    visible = await visible_event_ids(session, vis, tenant, limits)
    ids = {row[0] for row in found} | {row[1] for row in found} | {row[2] for row in found}
    stubs = await entry_stubs(session, tenant, ids | visible)
    manage = manages(vis)
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
            starts_at=row[6] if row[6] in visible else None,
            ends_at=row[7] if row[7] in visible else None,
            as_of=None if states is None else states.get(row[0]),
        )
        for row in found
    ]


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
) -> RelationshipEntryOut:
    is_public = None
    if manages(vis):
        audience = await session.get(EntityAudience, entity.id)
        is_public = True if audience is None else audience.is_public
    (row,) = await build_rows(
        session,
        vis,
        tenant,
        [
            (
                entity.id,
                marker.end_a,
                marker.end_b,
                marker.one_way,
                entity.updated_at,
                is_public,
                marker.starts_at,
                marker.ends_at,
            )
        ],
    )
    return row


async def _after_write(
    session: SessionDep, vis: InformationVisibility, tenant: uuid.UUID, identity: uuid.UUID
) -> RelationshipEntryOut:
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


async def _check_limits(
    session: SessionDep,
    user: CurrentUser,
    tenant: uuid.UUID,
    starts_at: uuid.UUID | None,
    ends_at: uuid.UUID | None,
) -> None:
    """The Events that bound a relationship in time are Events the writer sees, and differ."""
    if starts_at is not None and starts_at == ends_at:
        raise InvalidRelationshipError(detail="A relationship does not start and end at one Event.")
    for limit in (starts_at, ends_at):
        if limit is None:
            continue
        await _visible_entry(session, user, tenant, limit)
        if await session.get(StoryEvent, limit) is None:
            raise InvalidRelationshipError(detail="A relationship starts and ends at Events.")


async def _being_view(
    session: SessionDep, tenant: uuid.UUID, being: uuid.UUID
) -> InformationVisibility:
    """What one being may read through its own grants and its groups (ADR 0405): not what it
    believes, which waits for RFC 0029."""
    groups = await group_ids_for_characters(
        session, character_ids=frozenset({being}), tenant_id=tenant
    )
    return InformationVisibility(
        is_orga=False,
        is_admin=False,
        player_ids=frozenset(),
        knower_entity_ids=frozenset({being}) | groups,
        gm_reachable_entity_ids=frozenset(),
    )


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
    as_of: Annotated[
        uuid.UUID | None,
        Query(
            description="An Event: each row says whether it holds, is not yet, has ended or is "
            "unknown as of that Event, from what the reader's own graph records (ADR 0405)."
        ),
    ] = None,
    state: Annotated[
        list[Literal["holds", "not_yet", "ended", "unknown"]] | None,
        Query(description="With `as_of`, only the rows in these states, before paging."),
    ] = None,
    as_seen_by: Annotated[
        uuid.UUID | None,
        Query(
            description="A being: only what it may read through its own grants and groups. For "
            "staff, and for a player when the being is one they control."
        ),
    ] = None,
) -> Page[RelationshipEntryOut]:
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
            Relationship.starts_at,
            Relationship.ends_at,
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
    if as_seen_by is not None:
        await _visible_entry(session, user, tenant_id, as_seen_by)
        if not manages(vis) and as_seen_by not in await controlled_holder_entity_ids(
            session, user_id=user.id, tenant_id=tenant_id
        ):
            raise RelationshipReadAsForbiddenError()
        # What the being may read, and never more than the reader may.
        stmt = stmt.where(
            visible_entry_clause(await _being_view(session, tenant_id, as_seen_by), Entity.id)
        )
    states: dict[uuid.UUID, AsOfState] | None = None
    if as_of is not None:
        states = await _states_as_of(session, vis, tenant_id, stmt, as_of)
        if state and not any(s == "limit_reached" for s in states.values()):
            wanted = [identity for identity, found in states.items() if found in state]
            stmt = stmt.where(Entity.id == any_(literal(wanted, type_=ARRAY(Uuid))))

    async def rows(found: Any) -> list[RelationshipEntryOut]:
        return await build_rows(session, vis, tenant_id, found, states=states)

    page: Page[RelationshipEntryOut] = await apaginate(session, stmt, params, transformer=rows)
    return page


async def _states_as_of(
    session: SessionDep,
    vis: InformationVisibility,
    tenant: uuid.UUID,
    stmt: Select[Any],
    event: uuid.UUID,
) -> dict[uuid.UUID, AsOfState]:
    """Each candidate relationship's state as of `event`, from the reader's own graph only (ADR
    0405). Past the bound on the Events reached, every row says `limit_reached`."""
    from lorenzo_api.routers.event_order import graph

    candidates = (
        await session.execute(
            stmt.with_only_columns(
                Entity.id, Relationship.starts_at, Relationship.ends_at, maintain_column_froms=True
            ).order_by(None)
        )
    ).all()
    order, names = await graph(session, tenant, vis)
    if event not in names:
        raise EntityNotFoundError(detail="No such Event in this library")
    try:
        before, after = reach(order, event)
    except ReachLimitReachedError:
        return {identity: "limit_reached" for identity, _, _ in candidates}
    return {
        identity: classify(starts_at, ends_at, event, before, after)
        for identity, starts_at, ends_at in candidates
    }


@router.post("/relationships", status_code=201)
async def create_relationship(
    tenant_id: uuid.UUID,
    body: RelationshipCreate,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> RelationshipEntryOut:
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
    await _check_limits(session, user, tenant_id, body.starts_at, body.ends_at)
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
            starts_at=body.starts_at,
            ends_at=body.ends_at,
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
) -> RelationshipEntryOut:
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
) -> RelationshipEntryOut:
    """Replaces the ends and the direction under `If-Match`."""
    vis = await require_manager(session, user, tenant_id)
    entity, marker = await _read(session, vis, tenant_id, relationship_id)
    if if_match is None:
        raise MapPreconditionRequiredError(detail="Send the relationship's ETag as If-Match.")
    check_if_match(if_match, updated_at=entity.updated_at)
    await _check_ends(session, user, tenant_id, body.end_a, body.end_b)
    await _check_limits(session, user, tenant_id, body.starts_at, body.ends_at)
    marker.end_a = body.end_a
    marker.end_b = body.end_b
    marker.one_way = True if body.one_way else None
    marker.starts_at = body.starts_at
    marker.ends_at = body.ends_at
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
