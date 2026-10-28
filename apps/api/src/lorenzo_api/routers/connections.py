"""Connections and the links they give a Map (ADR 0363, 0364)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, Query, Response
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Select, case, select, union_all
from sqlalchemy.orm import aliased

from lorenzo_api.activity_log import record_activity
from lorenzo_api.connections import (
    MAX_HUB_SPOKES,
    MAX_LINK_ROWS,
    require_connection_room,
    touch_connection,
)
from lorenzo_api.dependencies import (
    CurrentUser,
    ParamsDep,
    SessionDep,
    get_tenant_or_404,
    set_tenant_rls_context,
)
from lorenzo_api.entity_kinds import create_entry
from lorenzo_api.entry_visibility import require_visible_entry, visible_entry_clause
from lorenzo_api.etag import check_if_match, etag_for
from lorenzo_api.exceptions import (
    EntityNotFoundError,
    InvalidConnectionError,
    MapPreconditionRequiredError,
)
from lorenzo_api.information_visibility import InformationVisibility
from lorenzo_api.models import (
    Connection,
    Entity,
    EntityAudience,
    EntitySlug,
    Map,
    MapPlacement,
)
from lorenzo_api.routers.entities import kinds_of
from lorenzo_api.routers.locations import manages, require_manager, standing
from lorenzo_api.schemas.common import Slug
from lorenzo_api.schemas.entities import EntityKind

router = APIRouter(
    prefix="/tenants/{tenant_id}", tags=["connections"], dependencies=[Depends(get_tenant_or_404)]
)

_NOT_FOUND = "No such connection in this library"
_NO_ENTRY = "No such entry in this library"
_NO_MAP = "No such Map in this library"


class EntryStub(BaseModel):
    id: uuid.UUID
    name: str
    slug: str | None = None
    kinds: list[EntityKind]


class ConnectionOut(EntryStub):
    """A connection and its two ends. `one_way` is true for a way that goes from `end_a` to
    `end_b` only."""

    end_a: EntryStub
    end_b: EntryStub
    one_way: bool
    updated_at: datetime
    can_manage: bool
    # Only for those who may manage connections: whether everyone in the library may see it.
    is_public: bool | None = None


class ConnectionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    slug: Slug | None = None
    end_a: uuid.UUID
    end_b: uuid.UUID
    one_way: bool = False
    # The kinds of connection it is, as entries: a road, a portal (ADR 0363).
    prototypes: list[uuid.UUID] = Field(default_factory=list, max_length=20)
    is_public: bool = False


class ConnectionPut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    end_a: uuid.UUID
    end_b: uuid.UUID
    one_way: bool = False


class Spoke(BaseModel):
    model_config = ConfigDict(extra="forbid")
    end: uuid.UUID
    # `to_hub` goes from the spoke to the hub only, `from_hub` the other way.
    direction: Literal["both", "to_hub", "from_hub"] = "both"
    name: str | None = Field(default=None, min_length=1, max_length=200)


class HubCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hub: uuid.UUID
    spokes: list[Spoke] = Field(min_length=1, max_length=MAX_HUB_SPOKES)
    prototypes: list[uuid.UUID] = Field(default_factory=list, max_length=20)
    is_public: bool = False


class LinkOut(BaseModel):
    """A connection seen from the end that is placed on a Map (ADR 0364)."""

    connection: EntryStub
    here: EntryStub
    other: EntryStub
    # `out` leaves `here` only, `in` arrives at it only.
    direction: Literal["both", "out", "in"]
    other_maps: list[EntryStub]


class LinksOut(BaseModel):
    items: list[LinkOut]
    truncated: bool = False


async def _commit(session: SessionDep, tenant: uuid.UUID) -> None:
    await session.commit()
    await set_tenant_rls_context(session, tenant)


async def _visible_entry(
    session: SessionDep, user: CurrentUser, tenant: uuid.UUID, identity: uuid.UUID
) -> Entity:
    try:
        await require_visible_entry(session, tenant_id=tenant, entity_id=identity, user_id=user.id)
    except EntityNotFoundError:
        raise EntityNotFoundError(detail=_NO_ENTRY) from None
    entity = await session.scalar(
        select(Entity).where(Entity.tenant_id == tenant, Entity.id == identity)
    )
    if entity is None:
        raise EntityNotFoundError(detail=_NO_ENTRY)
    return entity


def _readable(vis: InformationVisibility) -> Any:
    """A connection is read by someone who sees it and both its ends (ADR 0363)."""
    return (
        visible_entry_clause(vis, Entity.id)
        & visible_entry_clause(vis, Connection.end_a)
        & visible_entry_clause(vis, Connection.end_b)
    )


async def _stubs(
    session: SessionDep, tenant: uuid.UUID, ids: set[uuid.UUID]
) -> dict[uuid.UUID, EntryStub]:
    if not ids:
        return {}
    rows = (
        await session.execute(
            select(Entity.id, Entity.name, EntitySlug.slug)
            .outerjoin(EntitySlug, EntitySlug.entity_id == Entity.id)
            .where(Entity.tenant_id == tenant, Entity.id.in_(ids))
        )
    ).all()
    kinds = await kinds_of(session, [row[0] for row in rows])
    return {
        row[0]: EntryStub(id=row[0], name=row[1], slug=row[2], kinds=kinds[row[0]]) for row in rows
    }


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
) -> ConnectionOut:
    me = stubs[identity]
    return ConnectionOut(
        **me.model_dump(),
        end_a=stubs[end_a],
        end_b=stubs[end_b],
        one_way=bool(one_way),
        updated_at=updated_at,
        can_manage=manage,
        is_public=is_public if manage else None,
    )


async def _read(
    session: SessionDep, vis: InformationVisibility, tenant: uuid.UUID, identity: uuid.UUID
) -> tuple[Entity, Connection]:
    """A connection the reader may see with both ends; a hidden one and a missing one are the same
    404."""
    found = (
        await session.execute(
            select(Entity, Connection)
            .join(Connection, Connection.entity_id == Entity.id)
            .where(Entity.tenant_id == tenant, Entity.id == identity, _readable(vis))
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
    marker: Connection,
) -> ConnectionOut:
    stubs = await _stubs(session, tenant, {entity.id, marker.end_a, marker.end_b})
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
) -> ConnectionOut:
    """What a write answers: the connection as it now is. The writer's own sight was resolved before
    the entry existed, so it is read without that filter; the writer made it."""
    entity = await session.get(Entity, identity)
    marker = await session.get(Connection, identity)
    assert entity is not None and marker is not None
    await session.refresh(entity)
    return await _built(session, vis, tenant, entity, marker)


async def _check_ends(
    session: SessionDep, user: CurrentUser, tenant: uuid.UUID, end_a: uuid.UUID, end_b: uuid.UUID
) -> None:
    if end_a == end_b:
        raise InvalidConnectionError(detail="A connection joins two different entries.")
    for end in (end_a, end_b):
        await _visible_entry(session, user, tenant, end)


async def _prototypes(
    session: SessionDep, user: CurrentUser, tenant: uuid.UUID, ids: list[uuid.UUID]
) -> list[uuid.UUID]:
    unique = list(dict.fromkeys(ids))
    for identity in unique:
        await _visible_entry(session, user, tenant, identity)
    return unique


async def _make(
    session: SessionDep,
    *,
    tenant: uuid.UUID,
    user: CurrentUser,
    name: str,
    slug: str | None,
    end_a: uuid.UUID,
    end_b: uuid.UUID,
    one_way: bool,
    prototypes: list[uuid.UUID],
    is_public: bool,
    identity: uuid.UUID | None = None,
) -> Entity:
    entity = await create_entry(
        session,
        tenant_id=tenant,
        user_id=user.id,
        name=name,
        slug=slug,
        kinds=[],
        parents=prototypes,
        in_public_catalog=False,
        entity_id=identity,
    )
    session.add(
        Connection(
            entity_id=entity.id,
            tenant_id=tenant,
            end_a=end_a,
            end_b=end_b,
            one_way=True if one_way else None,
        )
    )
    # A new connection is restricted until its audience is opened, like a Location.
    session.add(EntityAudience(entity_id=entity.id, tenant_id=tenant, is_public=is_public))
    await session.flush()
    await record_activity(
        session,
        tenant_id=tenant,
        actor_id=user.id,
        action="connection.created",
        target_type="entity",
        target_id=entity.id,
    )
    return entity


@router.get("/connections")
async def list_connections(
    tenant_id: uuid.UUID,
    params: ParamsDep,
    session: SessionDep,
    user: CurrentUser,
    end: Annotated[
        uuid.UUID | None, Query(description="Only the connections that have this entry as an end.")
    ] = None,
    q: Annotated[
        str | None,
        Query(description="Case-insensitive substring match against the connection's name."),
    ] = None,
) -> Page[ConnectionOut]:
    """The connections the reader may see with both their ends, by name then id (ADR 0363). A
    hidden connection or end is absent from every row, count and page."""
    vis = await standing(session, user, tenant_id)
    # The audience is joined under its own name: the visibility predicate has its own.
    own = aliased(EntityAudience)
    stmt: Select[Any] = (
        select(
            Entity.id,
            Connection.end_a,
            Connection.end_b,
            Connection.one_way,
            Entity.updated_at,
            own.is_public,
        )
        .join(Connection, Connection.entity_id == Entity.id)
        .outerjoin(own, own.entity_id == Entity.id)
        .where(Entity.tenant_id == tenant_id, _readable(vis))
        .order_by(Entity.name, Entity.id)
    )
    if end is not None:
        stmt = stmt.where((Connection.end_a == end) | (Connection.end_b == end))
    if q is not None:
        stmt = stmt.where(Entity.name.icontains(q, autoescape=True))
    manage = manages(vis)

    async def rows(found: Any) -> list[ConnectionOut]:
        ids = {row[0] for row in found} | {row[1] for row in found} | {row[2] for row in found}
        stubs = await _stubs(session, tenant_id, ids)
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

    page: Page[ConnectionOut] = await apaginate(session, stmt, params, transformer=rows)
    return page


@router.post("/connections", status_code=201)
async def create_connection(
    tenant_id: uuid.UUID,
    body: ConnectionCreate,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> ConnectionOut:
    """A connection between two entries the writer sees, restricted unless `is_public`."""
    vis = await require_manager(session, user, tenant_id)
    await _check_ends(session, user, tenant_id, body.end_a, body.end_b)
    prototypes = await _prototypes(session, user, tenant_id, body.prototypes)
    await require_connection_room(session, tenant_id=tenant_id)
    entity = await _make(
        session,
        tenant=tenant_id,
        user=user,
        name=body.name,
        slug=body.slug,
        end_a=body.end_a,
        end_b=body.end_b,
        one_way=body.one_way,
        prototypes=prototypes,
        is_public=body.is_public,
        identity=body.id,
    )
    await _commit(session, tenant_id)
    out = await _after_write(session, vis, tenant_id, entity.id)
    response.headers["ETag"] = etag_for(out.updated_at)
    return out


@router.post("/connections/hub", status_code=201)
async def create_hub(
    tenant_id: uuid.UUID, body: HubCreate, session: SessionDep, user: CurrentUser
) -> list[ConnectionOut]:
    """A connection from the hub to each spoke, all or none (ADR 0363)."""
    vis = await require_manager(session, user, tenant_id)
    ends = [spoke.end for spoke in body.spokes]
    if len(set(ends)) != len(ends):
        raise InvalidConnectionError(detail="An entry is a spoke once.")
    if body.hub in ends:
        raise InvalidConnectionError(detail="A hub is not its own spoke.")
    hub = await _visible_entry(session, user, tenant_id, body.hub)
    spokes = [await _visible_entry(session, user, tenant_id, end) for end in ends]
    prototypes = await _prototypes(session, user, tenant_id, body.prototypes)
    await require_connection_room(session, tenant_id=tenant_id, adding=len(spokes))
    made: list[Entity] = []
    for spoke, entry in zip(body.spokes, spokes, strict=True):
        into = spoke.direction == "to_hub"
        made.append(
            await _make(
                session,
                tenant=tenant_id,
                user=user,
                name=spoke.name or f"{hub.name} - {entry.name}"[:200],
                slug=None,
                end_a=entry.id if into else hub.id,
                end_b=hub.id if into else entry.id,
                one_way=spoke.direction != "both",
                prototypes=prototypes,
                is_public=body.is_public,
            )
        )
    await _commit(session, tenant_id)
    return [await _after_write(session, vis, tenant_id, entity.id) for entity in made]


@router.get("/connections/{connection_id}")
async def get_connection(
    tenant_id: uuid.UUID,
    connection_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> ConnectionOut:
    vis = await standing(session, user, tenant_id)
    found, marker = await _read(session, vis, tenant_id, connection_id)
    out = await _built(session, vis, tenant_id, found, marker)
    response.headers["ETag"] = etag_for(out.updated_at)
    return out


@router.put("/connections/{connection_id}")
async def put_connection(
    tenant_id: uuid.UUID,
    connection_id: uuid.UUID,
    body: ConnectionPut,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> ConnectionOut:
    """Replaces the ends and the direction under `If-Match`."""
    vis = await require_manager(session, user, tenant_id)
    entity, marker = await _read(session, vis, tenant_id, connection_id)
    if if_match is None:
        raise MapPreconditionRequiredError(detail="Send the connection's ETag as If-Match.")
    check_if_match(if_match, updated_at=entity.updated_at)
    await _check_ends(session, user, tenant_id, body.end_a, body.end_b)
    marker.end_a = body.end_a
    marker.end_b = body.end_b
    marker.one_way = True if body.one_way else None
    await session.flush()
    entity = await touch_connection(
        session, tenant_id=tenant_id, connection_id=connection_id, user_id=user.id
    )
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="connection.updated",
        target_type="entity",
        target_id=connection_id,
    )
    await _commit(session, tenant_id)
    found, current = await _read(session, vis, tenant_id, connection_id)
    out = await _built(session, vis, tenant_id, found, current)
    response.headers["ETag"] = etag_for(out.updated_at)
    return out


@router.get("/maps/{map_id}/links")
async def map_links(
    tenant_id: uuid.UUID, map_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> LinksOut:
    """The connections the reader sees at the places drawn on the Map (ADR 0364), derived from the
    ends alone."""
    vis = await standing(session, user, tenant_id)
    try:
        await require_visible_entry(session, tenant_id=tenant_id, entity_id=map_id, user_id=user.id)
    except EntityNotFoundError:
        raise EntityNotFoundError(detail=_NO_MAP) from None
    if await session.get(Map, map_id) is None:
        raise EntityNotFoundError(detail=_NO_MAP)
    placed = select(MapPlacement.entry_entity_id).where(
        MapPlacement.tenant_id == tenant_id,
        MapPlacement.map_entity_id == map_id,
        visible_entry_clause(vis, MapPlacement.entry_entity_id),
    )

    def side(here: Any, other: Any, direction: Any) -> Select[Any]:
        return (
            select(
                Connection.entity_id.label("c"),
                here.label("h"),
                other.label("o"),
                direction.label("d"),
            )
            .join(Entity, Entity.id == Connection.entity_id)
            .where(Connection.tenant_id == tenant_id, here.in_(placed), _readable(vis))
        )

    both = union_all(
        side(
            Connection.end_a,
            Connection.end_b,
            case((Connection.one_way.is_(True), "out"), else_="both"),
        ),
        side(
            Connection.end_b,
            Connection.end_a,
            case((Connection.one_way.is_(True), "in"), else_="both"),
        ),
    ).subquery()
    here_entity, other_entity = aliased(Entity), aliased(Entity)
    found = (
        await session.execute(
            select(both.c.c, both.c.h, both.c.o, both.c.d)
            .join(here_entity, here_entity.id == both.c.h)
            .join(other_entity, other_entity.id == both.c.o)
            .order_by(here_entity.name, other_entity.name, both.c.c, both.c.h)
            .limit(MAX_LINK_ROWS + 1)
        )
    ).all()
    truncated = len(found) > MAX_LINK_ROWS
    found = found[:MAX_LINK_ROWS]
    ids = {row[0] for row in found} | {row[1] for row in found} | {row[2] for row in found}
    stubs = await _stubs(session, tenant_id, ids)
    others = {row[2] for row in found}
    elsewhere: dict[uuid.UUID, list[EntryStub]] = {}
    if others:
        maps = (
            await session.execute(
                select(MapPlacement.entry_entity_id, MapPlacement.map_entity_id).where(
                    MapPlacement.tenant_id == tenant_id,
                    MapPlacement.entry_entity_id.in_(others),
                    MapPlacement.map_entity_id != map_id,
                    visible_entry_clause(vis, MapPlacement.map_entity_id),
                )
            )
        ).all()
        map_stubs = await _stubs(session, tenant_id, {row[1] for row in maps})
        for entry, drawn_on in maps:
            elsewhere.setdefault(entry, []).append(map_stubs[drawn_on])
        for stubs_list in elsewhere.values():
            stubs_list.sort(key=lambda stub: (stub.name, str(stub.id)))
    return LinksOut(
        items=[
            LinkOut(
                connection=stubs[row[0]],
                here=stubs[row[1]],
                other=stubs[row[2]],
                direction=row[3],
                other_maps=elsewhere.get(row[2], []),
            )
            for row in found
        ],
        truncated=truncated,
    )
