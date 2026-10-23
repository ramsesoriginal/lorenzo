"""Locations and their part-of tree (ADR 0330)."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Response
from fastapi_pagination import Page, paginate
from fastapi_pagination.ext.sqlalchemy import apaginate
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Select, delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from lorenzo_api.dependencies import (
    CurrentUser,
    ParamsDep,
    SessionDep,
    get_tenant_or_404,
    require_tenant_participant,
    set_tenant_rls_context,
)
from lorenzo_api.entity_kinds import create_entry
from lorenzo_api.entry_visibility import require_visible_entry, visible_entry_clause
from lorenzo_api.etag import etag_for
from lorenzo_api.exceptions import (
    EntityNotFoundError,
    InvalidKindRequestError,
    LocationAuthoringForbiddenError,
)
from lorenzo_api.information_visibility import (
    InformationVisibility,
    resolve_information_visibility,
)
from lorenzo_api.location_address import address_of
from lorenzo_api.location_lint import lint_locations
from lorenzo_api.locations import (
    clear_part_of,
    nearest_visible_ancestor,
    set_part_of,
    visible_parts,
)
from lorenzo_api.models import (
    Character,
    Containment,
    Entity,
    EntityAudience,
    EntityLocation,
    EntitySlug,
    Location,
    LocationPart,
)
from lorenzo_api.placement import whereabouts_of
from lorenzo_api.routers.entities import authorize_entity_write, kinds_of
from lorenzo_api.routers.item_instances import caller_reach
from lorenzo_api.schemas.common import Slug
from lorenzo_api.schemas.entities import EntityKind

router = APIRouter(
    prefix="/tenants/{tenant_id}", tags=["locations"], dependencies=[Depends(get_tenant_or_404)]
)

_NOT_FOUND = "No such Location in this library"


class LocationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    slug: Slug | None = None
    is_public: bool = False
    parent_id: uuid.UUID | None = None
    level_ordinal: Decimal | None = None


class PartOfIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    parent_entity_id: uuid.UUID
    level_ordinal: Decimal | None = None


class LocationStub(BaseModel):
    """An entry as a Location list names it: no tags, no depth, no count of what is hidden."""

    id: uuid.UUID
    name: str
    slug: str | None = None
    kinds: list[EntityKind]
    level_ordinal: Decimal | None = None


class LocationOut(LocationStub):
    # The nearest ancestor this reader may see. A hidden level in between is not marked.
    within: LocationStub | None = None
    updated_at: datetime
    can_manage: bool
    # Only for those who may manage Locations: whether everyone in the library may see it.
    is_public: bool | None = None


async def standing(
    session: SessionDep, user: CurrentUser, tenant: uuid.UUID
) -> InformationVisibility:
    await require_tenant_participant(session, tenant_id=tenant, user=user)
    return await resolve_information_visibility(session, tenant_id=tenant, user_id=user.id)


def manages(vis: InformationVisibility) -> bool:
    return vis.is_admin or vis.manages_events


async def require_manager(
    session: SessionDep, user: CurrentUser, tenant: uuid.UUID
) -> InformationVisibility:
    vis = await standing(session, user, tenant)
    if not manages(vis):
        raise LocationAuthoringForbiddenError()
    return vis


async def _visible_location(
    session: SessionDep, user: CurrentUser, tenant: uuid.UUID, identity: uuid.UUID
) -> Entity:
    """A Location the reader may see. A hidden one and a missing one are the same 404, and so is
    an entry that is not a Location."""
    try:
        await require_visible_entry(session, tenant_id=tenant, entity_id=identity, user_id=user.id)
    except EntityNotFoundError:
        raise EntityNotFoundError(detail=_NOT_FOUND) from None
    entity = await session.scalar(
        select(Entity)
        .join(Location, Location.entity_id == Entity.id)
        .where(Entity.tenant_id == tenant, Entity.id == identity)
    )
    if entity is None:
        raise EntityNotFoundError(detail=_NOT_FOUND)
    return entity


async def _page(session: SessionDep, stmt: Select[Any], params: ParamsDep) -> Page[LocationStub]:
    async def rows(found: Sequence[Any]) -> list[LocationStub]:
        return await _stubs(session, [(r[0], r[1], r[2], r[3]) for r in found])

    page: Page[LocationStub] = await apaginate(session, stmt, params, transformer=rows)
    return page


async def _commit(session: SessionDep, tenant: uuid.UUID) -> None:
    await session.commit()
    await set_tenant_rls_context(session, tenant)


async def _stubs(
    session: SessionDep, rows: list[tuple[uuid.UUID, str, str | None, Decimal | None]]
) -> list[LocationStub]:
    kinds = await kinds_of(session, [identity for identity, *_ in rows])
    return [
        LocationStub(id=i, name=n, slug=s, kinds=kinds[i], level_ordinal=o) for i, n, s, o in rows
    ]


async def _out(
    session: SessionDep,
    vis: InformationVisibility,
    tenant: uuid.UUID,
    entity: Entity,
) -> LocationOut:
    ordinal = await session.scalar(
        select(LocationPart.level_ordinal).where(LocationPart.child_entity_id == entity.id)
    )
    slug = await session.scalar(select(EntitySlug.slug).where(EntitySlug.entity_id == entity.id))
    ancestor_id = await nearest_visible_ancestor(
        session, vis, tenant_id=tenant, location_id=entity.id
    )
    within = None
    if ancestor_id is not None:
        ancestor_row = (
            await session.execute(
                select(Entity.id, Entity.name, EntitySlug.slug)
                .outerjoin(EntitySlug, EntitySlug.entity_id == Entity.id)
                .where(Entity.id == ancestor_id)
            )
        ).one()
        (within,) = await _stubs(
            session, [(ancestor_row[0], ancestor_row[1], ancestor_row[2], None)]
        )
    (stub,) = await _stubs(session, [(entity.id, entity.name, slug, ordinal)])
    manage = manages(vis)
    is_public = None
    if manage:
        audience = await session.get(EntityAudience, entity.id)
        is_public = True if audience is None else audience.is_public
    return LocationOut(
        **stub.model_dump(),
        within=within,
        updated_at=entity.updated_at,
        can_manage=manage,
        is_public=is_public,
    )


@router.get("/locations")
async def list_locations(
    tenant_id: uuid.UUID,
    params: ParamsDep,
    session: SessionDep,
    user: CurrentUser,
    q: Annotated[
        str | None,
        Query(description="Case-insensitive substring match against the Location's name."),
    ] = None,
    root: Annotated[
        bool,
        Query(
            description=(
                "Only the Locations this reader sees as roots: those with no visible ancestor."
            )
        ),
    ] = False,
) -> Page[LocationStub]:
    """The Locations the reader may see, by name then id; with `root`, the visible roots, ordered
    by ordinal. Hidden Locations are absent: they appear in no row, count or page."""
    vis = await standing(session, user, tenant_id)
    stmt: Select[Any]
    if root:
        stmt = visible_parts(vis, tenant_id=tenant_id, parent_id=None)
        if q is not None:
            stmt = stmt.where(Entity.name.icontains(q, autoescape=True))
    else:
        stmt = (
            select(Entity.id, Entity.name, EntitySlug.slug, LocationPart.level_ordinal)
            .join(Location, Location.entity_id == Entity.id)
            .outerjoin(EntitySlug, EntitySlug.entity_id == Entity.id)
            .outerjoin(LocationPart, LocationPart.child_entity_id == Entity.id)
            .where(Entity.tenant_id == tenant_id, visible_entry_clause(vis, Entity.id))
            .order_by(Entity.name, Entity.id)
        )
        if q is not None:
            stmt = stmt.where(Entity.name.icontains(q, autoescape=True))

    return await _page(session, stmt, params)


@router.post("/locations", status_code=201)
async def create_location(
    tenant_id: uuid.UUID,
    body: LocationCreate,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> LocationOut:
    """A Location, restricted unless `is_public`. With `parent_id` it is made a part of that
    Location in the same transaction."""
    vis = await require_manager(session, user, tenant_id)
    parent = None
    if body.parent_id is not None:
        parent = await _visible_location(session, user, tenant_id, body.parent_id)
    entity = await create_entry(
        session,
        tenant_id=tenant_id,
        user_id=user.id,
        name=body.name,
        slug=body.slug,
        kinds=["location"],
        parents=[],
        in_public_catalog=False,
        entity_id=body.id,
    )
    if body.is_public:
        audience = await session.get(EntityAudience, entity.id)
        assert audience is not None
        audience.is_public = True
    if parent is not None:
        await set_part_of(
            session,
            tenant_id=tenant_id,
            child=entity.id,
            parent=parent.id,
            ordinal=body.level_ordinal,
        )
    await _commit(session, tenant_id)
    out = await _out(session, vis, tenant_id, entity)
    response.headers["ETag"] = etag_for(out.updated_at)
    return out


@router.get("/locations/{location_id}")
async def get_location(
    tenant_id: uuid.UUID,
    location_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> LocationOut:
    vis = await standing(session, user, tenant_id)
    entity = await _visible_location(session, user, tenant_id, location_id)
    out = await _out(session, vis, tenant_id, entity)
    response.headers["ETag"] = etag_for(out.updated_at)
    return out


@router.get("/locations/{location_id}/parts")
async def location_parts(
    tenant_id: uuid.UUID,
    location_id: uuid.UUID,
    params: ParamsDep,
    session: SessionDep,
    user: CurrentUser,
) -> Page[LocationStub]:
    """The Locations this reader sees directly in this one, through hidden levels without a
    trace, ordered by ordinal (none last), name and id."""
    vis = await standing(session, user, tenant_id)
    await _visible_location(session, user, tenant_id, location_id)
    stmt = visible_parts(vis, tenant_id=tenant_id, parent_id=location_id)

    return await _page(session, stmt, params)


@router.put("/locations/{location_id}/part-of")
async def put_part_of(
    tenant_id: uuid.UUID,
    location_id: uuid.UUID,
    body: PartOfIn,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> LocationOut:
    vis = await require_manager(session, user, tenant_id)
    entity = await _visible_location(session, user, tenant_id, location_id)
    parent = await _visible_location(session, user, tenant_id, body.parent_entity_id)
    await set_part_of(
        session,
        tenant_id=tenant_id,
        child=entity.id,
        parent=parent.id,
        ordinal=body.level_ordinal,
    )
    await _commit(session, tenant_id)
    out = await _out(session, vis, tenant_id, entity)
    response.headers["ETag"] = etag_for(out.updated_at)
    return out


@router.delete("/locations/{location_id}/part-of", status_code=204)
async def delete_part_of(
    tenant_id: uuid.UUID, location_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> None:
    await require_manager(session, user, tenant_id)
    await _visible_location(session, user, tenant_id, location_id)
    await clear_part_of(session, tenant_id=tenant_id, child=location_id)
    await _commit(session, tenant_id)


_NO_ENTRY = "No such entry in this library"


class AtIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    location_entity_id: uuid.UUID


class AtOut(BaseModel):
    entity_id: uuid.UUID
    location_entity_id: uuid.UUID


class PlaceOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str | None = None


class WhereaboutsOut(BaseModel):
    state: Literal["with_you", "stashed", "elsewhere", "unknown"]
    place: PlaceOut | None = None


async def _visible_entry(
    session: SessionDep, user: CurrentUser, tenant: uuid.UUID, identity: uuid.UUID
) -> Entity:
    """An entry the reader may see: a hidden one and a missing one are the same 404."""
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


async def _placer(
    session: SessionDep, user: CurrentUser, tenant: uuid.UUID, identity: uuid.UUID
) -> Entity:
    """Standing to place the entry (ADR 0333): the standing that writes Locations, and the
    standing that writes the entry."""
    await require_manager(session, user, tenant)
    entity = await _visible_entry(session, user, tenant, identity)
    await authorize_entity_write(session, tenant_id=tenant, user=user, entity_id=identity)
    return entity


@router.put("/entities/{entity_id}/at")
async def put_at(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    body: AtIn,
    session: SessionDep,
    user: CurrentUser,
) -> AtOut:
    """The entry is at this Location. An entry in a container is placed by the container: the
    request is accepted and changes nothing, and answers as it would otherwise."""
    entity = await _placer(session, user, tenant_id, entity_id)
    target = await _visible_location(session, user, tenant_id, body.location_entity_id)
    if target.id == entity.id:
        raise InvalidKindRequestError(detail="An entry cannot be at itself.")
    if await session.get(Containment, entity.id) is None:
        await session.execute(
            pg_insert(EntityLocation)
            .values(entity_id=entity.id, location_entity_id=target.id, tenant_id=tenant_id)
            .on_conflict_do_update(
                index_elements=[EntityLocation.entity_id],
                set_={"location_entity_id": target.id},
            )
        )
        await _commit(session, tenant_id)
    return AtOut(entity_id=entity.id, location_entity_id=target.id)


@router.delete("/entities/{entity_id}/at", status_code=204)
async def delete_at(
    tenant_id: uuid.UUID, entity_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> None:
    await _placer(session, user, tenant_id, entity_id)
    await session.execute(delete(EntityLocation).where(EntityLocation.entity_id == entity_id))
    await _commit(session, tenant_id)


@router.get("/entities/{entity_id}/whereabouts", response_model_exclude_none=True)
async def get_whereabouts(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    relative_to: Annotated[uuid.UUID, Query(description="The character the answer is for.")],
    session: SessionDep,
    user: CurrentUser,
) -> WhereaboutsOut:
    """Where the entry is, as that character would say it: `with_you`, `stashed`, `elsewhere` or
    `unknown`, and at most one name, the place when it is not the character's own (ADR 0334)."""
    vis = await standing(session, user, tenant_id)
    await _visible_entry(session, user, tenant_id, entity_id)
    reach = await caller_reach(session, tenant_id=tenant_id, user=user, visibility=vis)
    is_character = await session.scalar(
        select(Character.entity_id).where(
            Character.entity_id == relative_to, Character.tenant_id == tenant_id
        )
    )
    if is_character is None or (reach is not None and relative_to not in reach):
        raise EntityNotFoundError(detail=_NO_ENTRY)
    found = await whereabouts_of(
        session, vis, tenant_id=tenant_id, entity_ids=[entity_id], character_id=relative_to
    )
    answer = found[entity_id]
    return WhereaboutsOut(
        state=answer.state,
        place=None
        if answer.place is None
        else PlaceOut(id=answer.place.id, name=answer.place.name, slug=answer.place.slug),
    )


class StepOut(BaseModel):
    via: Literal["contained_in", "with", "at", "part_of"]
    entity_id: uuid.UUID
    name: str
    slug: str | None = None


class AddressOut(BaseModel):
    segments: list[StepOut]
    # Only for an entry that is a Location: the Locations above it.
    interior: list[StepOut] | None = None


class LintEntry(BaseModel):
    id: uuid.UUID
    name: str


class LintFindingOut(BaseModel):
    finding: Literal["dormant_place", "place_hidden", "part_hidden", "part_loop"]
    message: str
    entries: list[LintEntry]


@router.get("/entities/{entity_id}/address", response_model_exclude_none=True)
async def get_address(
    tenant_id: uuid.UUID, entity_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> AddressOut:
    """Where the entry sits, step by step, for those who write Locations (ADR 0335): what holds
    it, its owner for a thing in no container, the place of the top of that, every Location above
    the place, and, for a Location, what it is within."""
    vis = await require_manager(session, user, tenant_id)
    await _visible_entry(session, user, tenant_id, entity_id)
    found = await address_of(session, vis, tenant_id=tenant_id, entity_id=entity_id)

    def steps(items: list[Any]) -> list[StepOut]:
        return [StepOut(via=s.via, entity_id=s.entity_id, name=s.name, slug=s.slug) for s in items]

    return AddressOut(
        segments=steps(found.segments),
        interior=None if found.interior is None else steps(found.interior),
    )


@router.get("/lint/locations")
async def get_location_lint(
    tenant_id: uuid.UUID, params: ParamsDep, session: SessionDep, user: CurrentUser
) -> Page[LintFindingOut]:
    """What is probably a mistake in the library's places, for those who write Locations to fix
    (ADR 0335). It stores nothing and changes nothing."""
    await require_manager(session, user, tenant_id)
    findings = await lint_locations(session, tenant_id=tenant_id)
    page: Page[LintFindingOut] = paginate(
        [
            LintFindingOut(
                finding=f.finding,
                message=f.message,
                entries=[LintEntry(id=i, name=n) for i, n in f.entries],
            )
            for f in findings
        ],
        params,
    )
    return page
