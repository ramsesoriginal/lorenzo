"""Maps and their placements (ADR 0336 to 0338)."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import math
import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Query, Response
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from lorenzo_map import (
    MAX_BATCH_OPERATIONS,
    MapDocumentError,
    validate_placement,
    validate_system,
    validate_theme_hint,
    validate_view,
)
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Select, delete, func, literal, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.activity_log import record_activity
from lorenzo_api.dependencies import (
    CurrentUser,
    ParamsDep,
    SessionDep,
    get_tenant_or_404,
    set_tenant_rls_context,
)
from lorenzo_api.entity_kinds import create_entry
from lorenzo_api.entry_visibility import require_visible_entry, visible_entry_clause
from lorenzo_api.etag import check_if_match, etag_for, matches_if_none_match
from lorenzo_api.exceptions import (
    EntityNotFoundError,
    InvalidMapError,
    MapPreconditionRequiredError,
    MapSystemConflictError,
)
from lorenzo_api.information_visibility import InformationVisibility
from lorenzo_api.map_systems import refusal, warnings
from lorenzo_api.maps import require_placement_room, touch_map
from lorenzo_api.models import (
    Entity,
    EntityAudience,
    EntitySlug,
    Location,
    Map,
    MapPlacement,
)
from lorenzo_api.routers.entities import kinds_of
from lorenzo_api.routers.locations import manages, require_manager, standing
from lorenzo_api.schemas.common import Slug
from lorenzo_api.schemas.entities import EntityKind

router = APIRouter(
    prefix="/tenants/{tenant_id}", tags=["maps"], dependencies=[Depends(get_tenant_or_404)]
)

_NOT_FOUND = "No such Map in this library"
_NO_LOCATION = "No such Location in this library"
_NO_ENTRY = "No such entry in this library"

MAX_PAGE_ROWS = 200
# A page ends at this much body (ADR 0338), counting each row's geometry and a fixed share for
# the rest of it.
PAGE_BYTES = 1_000_000
ROW_OVERHEAD = 400


class MapStub(BaseModel):
    id: uuid.UUID
    name: str
    slug: str | None = None
    kinds: list[EntityKind]


class MapCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    slug: Slug | None = None
    system: dict[str, Any]
    subject_entity_id: uuid.UUID | None = None
    # A theme name (ADR 0352); none draws the default.
    theme_hint: str | None = None
    # What is only drawn: a visual grid over a plane or an outline (ADR 0354).
    view: dict[str, Any] | None = None
    is_public: bool = False


class MapPut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    system: dict[str, Any]
    subject_entity_id: uuid.UUID | None = None
    theme_hint: str | None = None
    view: dict[str, Any] | None = None


class MapOut(MapStub):
    system: dict[str, Any]
    # The theme name the Map asks for; one this version does not know draws as the default.
    theme_hint: str | None = None
    view: dict[str, Any] | None = None
    # What a change of the system may leave out of line, said on the write that made it.
    warnings: list[str] = Field(default_factory=list)
    # The Location it shows, only when this reader may see that Location.
    subject: MapStub | None = None
    updated_at: datetime
    can_manage: bool
    # Only for those who may manage Maps: whether everyone in the library may see it.
    is_public: bool | None = None


class PlacementIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    geometry: dict[str, Any]
    role: str | None = None
    style: dict[str, Any] | None = None
    z: Annotated[int, Field(strict=True)] = 0


class PlacementOut(MapStub):
    """The entry's stub with how it is drawn here."""

    geometry: dict[str, Any]
    role: str | None = None
    style: dict[str, Any] | None = None
    z: int


class PlacementsPage(BaseModel):
    items: list[PlacementOut]
    # Leave it out of the next request to start again; there is no total.
    next_cursor: str | None = None


async def _commit(session: SessionDep, tenant: uuid.UUID) -> None:
    await session.commit()
    await set_tenant_rls_context(session, tenant)


async def _visible_map(
    session: SessionDep, user: CurrentUser, tenant: uuid.UUID, identity: uuid.UUID
) -> Entity:
    """A Map the reader may see. A hidden one and a missing one are the same 404, and so is an
    entry that is not a Map."""
    try:
        await require_visible_entry(session, tenant_id=tenant, entity_id=identity, user_id=user.id)
    except EntityNotFoundError:
        raise EntityNotFoundError(detail=_NOT_FOUND) from None
    entity = await session.scalar(
        select(Entity)
        .join(Map, Map.entity_id == Entity.id)
        .where(Entity.tenant_id == tenant, Entity.id == identity)
    )
    if entity is None:
        raise EntityNotFoundError(detail=_NOT_FOUND)
    return entity


async def _visible_location(
    session: SessionDep, user: CurrentUser, tenant: uuid.UUID, identity: uuid.UUID
) -> None:
    try:
        await require_visible_entry(session, tenant_id=tenant, entity_id=identity, user_id=user.id)
    except EntityNotFoundError:
        raise EntityNotFoundError(detail=_NO_LOCATION) from None
    if await session.get(Location, identity) is None:
        raise EntityNotFoundError(detail=_NO_LOCATION)


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


async def _stubs(
    session: SessionDep, rows: Sequence[tuple[uuid.UUID, str, str | None]]
) -> list[MapStub]:
    kinds = await kinds_of(session, [identity for identity, *_ in rows])
    return [MapStub(id=i, name=n, slug=s, kinds=kinds[i]) for i, n, s in rows]


async def _out(
    session: SessionDep, vis: InformationVisibility, tenant: uuid.UUID, entity: Entity
) -> MapOut:
    row = await session.get(Map, entity.id)
    assert row is not None
    slug = await session.scalar(select(EntitySlug.slug).where(EntitySlug.entity_id == entity.id))
    (stub,) = await _stubs(session, [(entity.id, entity.name, slug)])
    subject = None
    if row.subject_entity_id is not None:
        shown = (
            await session.execute(
                select(Entity.id, Entity.name, EntitySlug.slug)
                .join(Location, Location.entity_id == Entity.id)
                .outerjoin(EntitySlug, EntitySlug.entity_id == Entity.id)
                .where(
                    Entity.tenant_id == tenant,
                    Entity.id == row.subject_entity_id,
                    visible_entry_clause(vis, Entity.id),
                )
            )
        ).first()
        if shown is not None:
            (subject,) = await _stubs(session, [(shown[0], shown[1], shown[2])])
    manage = manages(vis)
    is_public = None
    if manage:
        audience = await session.get(EntityAudience, entity.id)
        is_public = True if audience is None else audience.is_public
    return MapOut(
        **stub.model_dump(),
        system=row.system,
        theme_hint=row.theme_hint,
        view=row.view,
        subject=subject,
        updated_at=entity.updated_at,
        can_manage=manage,
        is_public=is_public,
    )


@router.get("/maps")
async def list_maps(
    tenant_id: uuid.UUID,
    params: ParamsDep,
    session: SessionDep,
    user: CurrentUser,
    q: Annotated[
        str | None, Query(description="Case-insensitive substring match against the Map's name.")
    ] = None,
) -> Page[MapStub]:
    """The Maps the reader may see, by name then id. A hidden Map is absent from every row and
    page."""
    vis = await standing(session, user, tenant_id)
    stmt: Select[Any] = (
        select(Entity.id, Entity.name, EntitySlug.slug)
        .join(Map, Map.entity_id == Entity.id)
        .outerjoin(EntitySlug, EntitySlug.entity_id == Entity.id)
        .where(Entity.tenant_id == tenant_id, visible_entry_clause(vis, Entity.id))
        .order_by(Entity.name, Entity.id)
    )
    if q is not None:
        stmt = stmt.where(Entity.name.icontains(q, autoescape=True))

    async def rows(found: Sequence[Any]) -> list[MapStub]:
        return await _stubs(session, [(r[0], r[1], r[2]) for r in found])

    page: Page[MapStub] = await apaginate(session, stmt, params, transformer=rows)
    return page


@router.post("/maps", status_code=201)
async def create_map(
    tenant_id: uuid.UUID,
    body: MapCreate,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> MapOut:
    """A Map, restricted unless `is_public`."""
    vis = await require_manager(session, user, tenant_id)
    try:
        system = validate_system(body.system)
        theme = validate_theme_hint(body.theme_hint)
        view = validate_view(body.view, system)
    except MapDocumentError as error:
        raise InvalidMapError(detail=error.reason) from None
    if body.subject_entity_id is not None:
        await _visible_location(session, user, tenant_id, body.subject_entity_id)
    entity = await create_entry(
        session,
        tenant_id=tenant_id,
        user_id=user.id,
        name=body.name,
        slug=body.slug,
        kinds=["map"],
        parents=[],
        in_public_catalog=False,
        entity_id=body.id,
        system=body.system,
    )
    row = await session.get(Map, entity.id)
    assert row is not None
    row.subject_entity_id = body.subject_entity_id
    row.theme_hint = theme
    row.view = view
    if body.is_public:
        audience = await session.get(EntityAudience, entity.id)
        assert audience is not None
        audience.is_public = True
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="map.created",
        target_type="entity",
        target_id=entity.id,
    )
    await _commit(session, tenant_id)
    out = await _out(session, vis, tenant_id, entity)
    response.headers["ETag"] = etag_for(out.updated_at)
    return out


@router.get("/maps/{map_id}")
async def get_map(
    tenant_id: uuid.UUID,
    map_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> MapOut:
    vis = await standing(session, user, tenant_id)
    entity = await _visible_map(session, user, tenant_id, map_id)
    out = await _out(session, vis, tenant_id, entity)
    response.headers["ETag"] = etag_for(out.updated_at)
    return out


@router.put("/maps/{map_id}")
async def put_map(
    tenant_id: uuid.UUID,
    map_id: uuid.UUID,
    body: MapPut,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> MapOut:
    """Replaces the system, the subject, the theme name and the view under `If-Match`. No placement
    is touched, but a change that would move every one of them is a 409, and what else may no longer
    line up comes back as `warnings` (ADR 0354)."""
    vis = await require_manager(session, user, tenant_id)
    entity = await _visible_map(session, user, tenant_id, map_id)
    if if_match is None:
        raise MapPreconditionRequiredError(detail="Send the Map's ETag as If-Match.")
    check_if_match(if_match, updated_at=entity.updated_at)
    try:
        stored = validate_system(body.system)
        theme = validate_theme_hint(body.theme_hint)
        view = validate_view(body.view, stored)
    except MapDocumentError as error:
        raise InvalidMapError(detail=error.reason) from None
    if body.subject_entity_id is not None:
        await _visible_location(session, user, tenant_id, body.subject_entity_id)
    row = await session.get(Map, map_id)
    assert row is not None
    said: list[str] = []
    placed = await session.scalar(
        select(func.count())
        .select_from(MapPlacement)
        .where(MapPlacement.tenant_id == tenant_id, MapPlacement.map_entity_id == map_id)
    )
    if placed:
        why = refusal(row.system, stored)
        if why is not None:
            raise MapSystemConflictError(detail=why)
        said = warnings(row.system, stored)
    row.system = stored
    row.subject_entity_id = body.subject_entity_id
    row.theme_hint = theme
    row.view = view
    entity = await touch_map(session, tenant_id=tenant_id, map_id=map_id, user_id=user.id)
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="map.updated",
        target_type="entity",
        target_id=map_id,
    )
    await _commit(session, tenant_id)
    out = await _out(session, vis, tenant_id, entity)
    out.warnings = said
    response.headers["ETag"] = etag_for(out.updated_at)
    return out


async def _system_of(session: AsyncSession, map_id: uuid.UUID) -> dict[str, Any] | None:
    """The Map's own system, which a sphere's geometry is held to (ADR 0357)."""
    row = await session.get(Map, map_id)
    return row.system if row is not None else None


@router.put("/maps/{map_id}/placements/{entry_id}")
async def put_placement(
    tenant_id: uuid.UUID,
    map_id: uuid.UUID,
    entry_id: uuid.UUID,
    body: PlacementIn,
    session: SessionDep,
    user: CurrentUser,
) -> PlacementOut:
    """Draws the entry on the Map, or redraws it. The validator runs on every write."""
    await require_manager(session, user, tenant_id)
    await _visible_map(session, user, tenant_id, map_id)
    entry = await _visible_entry(session, user, tenant_id, entry_id)
    try:
        checked = validate_placement(
            body.geometry, body.role, body.style, body.z, await _system_of(session, map_id)
        )
    except MapDocumentError as error:
        raise InvalidMapError(detail=error.reason) from None
    placed = await session.get(MapPlacement, (map_id, entry_id))
    if placed is None:
        await require_placement_room(session, tenant_id=tenant_id, map_id=map_id)
        placed = MapPlacement(map_entity_id=map_id, entry_entity_id=entry_id, tenant_id=tenant_id)
        session.add(placed)
    placed.geometry = checked.geometry
    placed.role = checked.role
    placed.style = checked.style
    placed.z = checked.z
    placed.bytes = checked.bytes
    placed.minx, placed.miny, placed.maxx, placed.maxy = checked.bbox
    await touch_map(session, tenant_id=tenant_id, map_id=map_id, user_id=user.id)
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="map.placement_set",
        target_type="entity",
        target_id=map_id,
        detail=str(entry_id),
    )
    slug = await session.scalar(select(EntitySlug.slug).where(EntitySlug.entity_id == entry_id))
    (stub,) = await _stubs(session, [(entry.id, entry.name, slug)])
    out = PlacementOut(
        **stub.model_dump(),
        geometry=checked.geometry,
        role=checked.role,
        style=checked.style,
        z=checked.z,
    )
    await _commit(session, tenant_id)
    return out


@router.delete("/maps/{map_id}/placements/{entry_id}", status_code=204)
async def delete_placement(
    tenant_id: uuid.UUID,
    map_id: uuid.UUID,
    entry_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> None:
    await require_manager(session, user, tenant_id)
    await _visible_map(session, user, tenant_id, map_id)
    await _visible_entry(session, user, tenant_id, entry_id)
    gone = await session.execute(
        delete(MapPlacement).where(
            MapPlacement.tenant_id == tenant_id,
            MapPlacement.map_entity_id == map_id,
            MapPlacement.entry_entity_id == entry_id,
        )
    )
    if gone.rowcount:  # type: ignore[attr-defined]
        await touch_map(session, tenant_id=tenant_id, map_id=map_id, user_id=user.id)
        await record_activity(
            session,
            tenant_id=tenant_id,
            actor_id=user.id,
            action="map.placement_removed",
            target_type="entity",
            target_id=map_id,
            detail=str(entry_id),
        )
    await _commit(session, tenant_id)


class BatchPut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entry_id: uuid.UUID
    geometry: dict[str, Any]
    role: str | None = None
    style: dict[str, Any] | None = None
    z: Annotated[int, Field(strict=True)] = 0


class PlacementBatchIn(BaseModel):
    """At most 100 operations in all (ADR 0351): redraws or draws, and removals."""

    model_config = ConfigDict(extra="forbid")
    put: list[BatchPut] = Field(default_factory=list)
    remove: list[uuid.UUID] = Field(default_factory=list)


class PlacementBatchOut(BaseModel):
    put: int
    removed: int


@router.post("/maps/{map_id}/placements/batch")
async def batch_placements(
    tenant_id: uuid.UUID,
    map_id: uuid.UUID,
    body: PlacementBatchIn,
    session: SessionDep,
    user: CurrentUser,
) -> PlacementBatchOut:
    """Draws, redraws and removes placements as one transaction: if any operation is refused,
    nothing is written, and the answer names the first refusal by its place in the request."""
    vis = await require_manager(session, user, tenant_id)
    await _visible_map(session, user, tenant_id, map_id)
    entries = [item.entry_id for item in body.put] + body.remove
    if len(entries) > MAX_BATCH_OPERATIONS:
        raise InvalidMapError(detail=f"A batch holds at most {MAX_BATCH_OPERATIONS} operations")
    if len(set(entries)) != len(entries):
        raise InvalidMapError(detail="An entry appears more than once in one batch")
    checked = []
    system = await _system_of(session, map_id)
    for index, item in enumerate(body.put):
        try:
            checked.append(validate_placement(item.geometry, item.role, item.style, item.z, system))
        except MapDocumentError as error:
            raise InvalidMapError(detail=f"put[{index}]: {error.reason}") from None
    if entries:
        found = set(
            await session.scalars(
                select(Entity.id).where(
                    Entity.tenant_id == tenant_id,
                    Entity.id.in_(entries),
                    visible_entry_clause(vis, Entity.id),
                )
            )
        )
        if found != set(entries):
            raise EntityNotFoundError(detail=_NO_ENTRY)
    existing = {
        row.entry_entity_id: row
        for row in await session.scalars(
            select(MapPlacement).where(
                MapPlacement.tenant_id == tenant_id,
                MapPlacement.map_entity_id == map_id,
                MapPlacement.entry_entity_id.in_([item.entry_id for item in body.put]),
            )
        )
    }
    added = sum(1 for item in body.put if item.entry_id not in existing)
    if added:
        await require_placement_room(session, tenant_id=tenant_id, map_id=map_id, adding=added)
    for item, valid in zip(body.put, checked, strict=True):
        placed = existing.get(item.entry_id)
        if placed is None:
            placed = MapPlacement(
                map_entity_id=map_id, entry_entity_id=item.entry_id, tenant_id=tenant_id
            )
            session.add(placed)
        placed.geometry = valid.geometry
        placed.role = valid.role
        placed.style = valid.style
        placed.z = valid.z
        placed.bytes = valid.bytes
        placed.minx, placed.miny, placed.maxx, placed.maxy = valid.bbox
    removed = 0
    if body.remove:
        gone = await session.execute(
            delete(MapPlacement).where(
                MapPlacement.tenant_id == tenant_id,
                MapPlacement.map_entity_id == map_id,
                MapPlacement.entry_entity_id.in_(body.remove),
            )
        )
        removed = gone.rowcount  # type: ignore[attr-defined]
    if body.put or removed:
        await touch_map(session, tenant_id=tenant_id, map_id=map_id, user_id=user.id)
        await record_activity(
            session,
            tenant_id=tenant_id,
            actor_id=user.id,
            action="map.placements_changed",
            target_type="entity",
            target_id=map_id,
            detail=f"put={len(body.put)} removed={removed}",
        )
    await _commit(session, tenant_id)
    return PlacementBatchOut(put=len(body.put), removed=removed)


def _encode_cursor(z: int, entry_id: uuid.UUID) -> str:
    raw = json.dumps([z, str(entry_id)], separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[int, uuid.UUID]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        z, entry = json.loads(base64.urlsafe_b64decode(padded.encode()))
        if isinstance(z, bool) or not isinstance(z, int):
            raise ValueError
        return z, uuid.UUID(entry)
    except ValueError, TypeError, binascii.Error:
        raise InvalidMapError(detail="That is not a cursor this Map gave") from None


def _parse_bbox(bbox: str) -> tuple[float, float, float, float]:
    try:
        x0, y0, x1, y1 = (float(part) for part in bbox.split(","))
    except ValueError:
        raise InvalidMapError(detail="bbox is four numbers: x0,y0,x1,y1") from None
    if not all(math.isfinite(v) for v in (x0, y0, x1, y1)) or x0 > x1 or y0 > y1:
        raise InvalidMapError(detail="bbox is four numbers: x0,y0,x1,y1, low corner first")
    return x0, y0, x1, y1


@router.get(
    "/maps/{map_id}/placements",
    response_model=PlacementsPage,
    responses={304: {"description": "The page is unchanged; reuse the cached one."}},
)
async def list_placements(
    tenant_id: uuid.UUID,
    map_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_ROWS)] = MAX_PAGE_ROWS,
    cursor: Annotated[
        str | None,
        Query(description="The `next_cursor` of the previous page; leave out for the first."),
    ] = None,
    bbox: Annotated[
        str | None,
        Query(description="`x0,y0,x1,y1`: only what overlaps this box, in the Map's own units."),
    ] = None,
    role: Annotated[
        list[str] | None, Query(max_length=32, description="Only these roles (repeatable).")
    ] = None,
    min_diag: Annotated[
        float | None,
        Query(ge=0, description="Drops what is drawn smaller than this diagonal."),
    ] = None,
    if_none_match: Annotated[str | None, Header()] = None,
) -> Response:
    """The placements this reader may see, by drawing order then entry, as keyset pages after the
    visibility join: a hidden entry leaves no row, gap or count (ADR 0338). A page ends at
    `limit` rows or about 1 MiB of body. The `ETag` is the hash of the body, and
    `If-None-Match` answers 304."""
    vis = await standing(session, user, tenant_id)
    await _visible_map(session, user, tenant_id, map_id)
    stmt = (
        select(
            Entity.id,
            Entity.name,
            EntitySlug.slug,
            MapPlacement.geometry,
            MapPlacement.role,
            MapPlacement.style,
            MapPlacement.z,
            MapPlacement.bytes,
        )
        .join(MapPlacement, MapPlacement.entry_entity_id == Entity.id)
        .outerjoin(EntitySlug, EntitySlug.entity_id == Entity.id)
        .where(
            Entity.tenant_id == tenant_id,
            MapPlacement.tenant_id == tenant_id,
            MapPlacement.map_entity_id == map_id,
            visible_entry_clause(vis, Entity.id),
        )
        .order_by(MapPlacement.z, MapPlacement.entry_entity_id)
        .limit(limit + 1)
    )
    if cursor is not None:
        after_z, after_entry = _decode_cursor(cursor)
        stmt = stmt.where(
            tuple_(MapPlacement.z, MapPlacement.entry_entity_id)
            > tuple_(literal(after_z), literal(after_entry))
        )
    if bbox is not None:
        x0, y0, x1, y1 = _parse_bbox(bbox)
        stmt = stmt.where(
            MapPlacement.maxx >= x0,
            MapPlacement.minx <= x1,
            MapPlacement.maxy >= y0,
            MapPlacement.miny <= y1,
        )
    if role:
        stmt = stmt.where(MapPlacement.role.in_(role))
    if min_diag:
        stmt = stmt.where(
            func.sqrt(
                func.power(MapPlacement.maxx - MapPlacement.minx, 2)
                + func.power(MapPlacement.maxy - MapPlacement.miny, 2)
            )
            >= min_diag
        )
    found = list((await session.execute(stmt)).all())
    kept: list[Any] = []
    spent = 0
    for row in found[:limit]:
        spent += row.bytes + ROW_OVERHEAD
        if kept and spent > PAGE_BYTES:
            break
        kept.append(row)
    more = len(found) > len(kept)
    stubs = await _stubs(session, [(r.id, r.name, r.slug) for r in kept])
    page = PlacementsPage(
        items=[
            PlacementOut(
                **stub.model_dump(), geometry=r.geometry, role=r.role, style=r.style, z=r.z
            )
            for stub, r in zip(stubs, kept, strict=True)
        ],
        next_cursor=_encode_cursor(kept[-1].z, kept[-1].id) if more and kept else None,
    )
    body = page.model_dump_json()
    token = hashlib.sha256(body.encode()).hexdigest()[:32]
    headers = {"ETag": f'W/"{token}"', "Cache-Control": "private, no-cache"}
    if matches_if_none_match(if_none_match, token):
        return Response(status_code=304, headers=headers)
    return Response(content=body, media_type="application/json", headers=headers)
