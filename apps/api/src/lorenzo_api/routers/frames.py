"""Frames and axes: who is a frame, who is on one, and what is on a frame (ADR 0369, 0370).

Every route is for those who write Locations. An entry's address (`/address`) carries the frames it
resolves to; no player read does.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Select, delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from lorenzo_api.dependencies import (
    CurrentUser,
    ParamsDep,
    SessionDep,
    get_tenant_or_404,
    set_tenant_rls_context,
)
from lorenzo_api.entry_visibility import visible_entry_clause
from lorenzo_api.exceptions import EntityNotFoundError, InvalidFrameError
from lorenzo_api.frames import (
    AXES,
    check_membership,
    lock_frames,
    require_axis,
    require_room,
)
from lorenzo_api.models import Entity, EntityFrame, Frame
from lorenzo_api.routers.connections import EntryStub, entry_stubs
from lorenzo_api.routers.locations import placer, require_manager, visible_entry

router = APIRouter(
    prefix="/tenants/{tenant_id}", tags=["frames"], dependencies=[Depends(get_tenant_or_404)]
)

_NO_FRAME = "No such frame in this library"


class FrameAxisOut(BaseModel):
    entity_id: uuid.UUID
    axis: str


class FrameIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    frame_entity_id: uuid.UUID


class MembershipOut(BaseModel):
    entity_id: uuid.UUID
    axis: str
    frame_entity_id: uuid.UUID


class FrameRowOut(BaseModel):
    axis: str
    frame: EntryStub


class EntryFramesOut(BaseModel):
    """What an entry is a frame on and the frames it is on itself: its own rows, never inherited."""

    frame_axes: list[str]
    frames: list[FrameRowOut]


class FrameOut(BaseModel):
    entry: EntryStub
    axes: list[str]


class MemberOut(BaseModel):
    entry: EntryStub
    axis: str


def _in_order(axes: list[str]) -> list[str]:
    return sorted(axes, key=AXES.index)


async def _commit(session: SessionDep, tenant: uuid.UUID) -> None:
    await session.commit()
    await set_tenant_rls_context(session, tenant)


@router.put("/entities/{entity_id}/frame-axes/{axis}")
async def put_frame_axis(
    tenant_id: uuid.UUID, entity_id: uuid.UUID, axis: str, session: SessionDep, user: CurrentUser
) -> FrameAxisOut:
    """The entry is a frame on the axis. Saying it again changes nothing."""
    await placer(session, user, tenant_id, entity_id)
    require_axis(axis)
    if await session.get(Frame, (entity_id, axis)) is None:
        await require_room(session, tenant_id=tenant_id, frames=True)
        await session.execute(
            pg_insert(Frame)
            .values(entity_id=entity_id, axis=axis, tenant_id=tenant_id)
            .on_conflict_do_nothing()
        )
        await _commit(session, tenant_id)
    return FrameAxisOut(entity_id=entity_id, axis=axis)


@router.delete("/entities/{entity_id}/frame-axes/{axis}", status_code=204)
async def delete_frame_axis(
    tenant_id: uuid.UUID, entity_id: uuid.UUID, axis: str, session: SessionDep, user: CurrentUser
) -> None:
    """The entry is no longer a frame on the axis, and nothing is on it any more."""
    await placer(session, user, tenant_id, entity_id)
    await session.execute(
        delete(Frame).where(
            Frame.tenant_id == tenant_id, Frame.entity_id == entity_id, Frame.axis == axis
        )
    )
    await _commit(session, tenant_id)


@router.put("/entities/{entity_id}/frames/{axis}")
async def put_frame(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    axis: str,
    body: FrameIn,
    session: SessionDep,
    user: CurrentUser,
) -> MembershipOut:
    """The entry is on this frame on the axis, replacing the frame it was on."""
    await placer(session, user, tenant_id, entity_id)
    require_axis(axis)
    target = await visible_entry(session, user, tenant_id, body.frame_entity_id)
    if await session.get(Frame, (target.id, axis)) is None:
        raise InvalidFrameError(detail="That entry is not a frame on this axis")
    await lock_frames(session, tenant_id)
    await check_membership(
        session, tenant_id=tenant_id, entity_id=entity_id, axis=axis, frame_id=target.id
    )
    if await session.get(EntityFrame, (entity_id, axis)) is None:
        await require_room(session, tenant_id=tenant_id, frames=False)
    await session.execute(
        pg_insert(EntityFrame)
        .values(entity_id=entity_id, axis=axis, frame_entity_id=target.id, tenant_id=tenant_id)
        .on_conflict_do_update(
            index_elements=[EntityFrame.entity_id, EntityFrame.axis],
            set_={"frame_entity_id": target.id},
        )
    )
    await _commit(session, tenant_id)
    return MembershipOut(entity_id=entity_id, axis=axis, frame_entity_id=target.id)


@router.delete("/entities/{entity_id}/frames/{axis}", status_code=204)
async def delete_frame(
    tenant_id: uuid.UUID, entity_id: uuid.UUID, axis: str, session: SessionDep, user: CurrentUser
) -> None:
    await placer(session, user, tenant_id, entity_id)
    await session.execute(
        delete(EntityFrame).where(
            EntityFrame.tenant_id == tenant_id,
            EntityFrame.entity_id == entity_id,
            EntityFrame.axis == axis,
        )
    )
    await _commit(session, tenant_id)


@router.get("/entities/{entity_id}/frames")
async def get_entry_frames(
    tenant_id: uuid.UUID, entity_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> EntryFramesOut:
    """The entry's own rows: the axes it is a frame on and the frames it is on (ADR 0370)."""
    vis = await require_manager(session, user, tenant_id)
    await visible_entry(session, user, tenant_id, entity_id)
    designated = (
        await session.scalars(
            select(Frame.axis).where(
                Frame.tenant_id == tenant_id, Frame.entity_id == entity_id, Frame.axis.in_(AXES)
            )
        )
    ).all()
    rows = (
        await session.execute(
            select(EntityFrame.axis, EntityFrame.frame_entity_id).where(
                EntityFrame.tenant_id == tenant_id,
                EntityFrame.entity_id == entity_id,
                EntityFrame.axis.in_(AXES),
                visible_entry_clause(vis, EntityFrame.frame_entity_id),
            )
        )
    ).all()
    stubs = await entry_stubs(session, tenant_id, {row[1] for row in rows})
    ordered = sorted(rows, key=lambda row: AXES.index(row[0]))
    return EntryFramesOut(
        frame_axes=_in_order(list(designated)),
        frames=[FrameRowOut(axis=axis, frame=stubs[frame]) for axis, frame in ordered],
    )


@router.get("/frames")
async def list_frames(
    tenant_id: uuid.UUID,
    params: ParamsDep,
    session: SessionDep,
    user: CurrentUser,
    axis: Annotated[str | None, Query(description="Only frames on this axis.")] = None,
    q: Annotated[
        str | None, Query(description="Case-insensitive substring match against the name.")
    ] = None,
) -> Page[FrameOut]:
    """The entries that are frames, with the axes each is a frame on, by name then id (ADR 0370)."""
    vis = await require_manager(session, user, tenant_id)
    stmt: Select[Any] = (
        select(Entity.id, Entity.name, func.array_agg(Frame.axis).label("axes"))
        .join(Frame, Frame.entity_id == Entity.id)
        .where(
            Entity.tenant_id == tenant_id,
            Frame.tenant_id == tenant_id,
            Frame.axis.in_(AXES),
            visible_entry_clause(vis, Entity.id),
        )
        .group_by(Entity.id, Entity.name)
        .order_by(Entity.name, Entity.id)
    )
    if axis is not None:
        stmt = stmt.where(Frame.axis == require_axis(axis))
    if q is not None:
        stmt = stmt.where(Entity.name.icontains(q, autoescape=True))

    async def rows(found: Any) -> list[FrameOut]:
        stubs = await entry_stubs(session, tenant_id, {row[0] for row in found})
        return [FrameOut(entry=stubs[row[0]], axes=_in_order(list(row[2]))) for row in found]

    page: Page[FrameOut] = await apaginate(session, stmt, params, transformer=rows, unique=False)
    return page


@router.get("/entities/{entity_id}/frame-members")
async def list_frame_members(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    params: ParamsDep,
    session: SessionDep,
    user: CurrentUser,
    axis: Annotated[str | None, Query(description="Only what is on it on this axis.")] = None,
) -> Page[MemberOut]:
    """What is explicitly on the frame, by name then id (ADR 0370): "everything on the Ethereal"."""
    vis = await require_manager(session, user, tenant_id)
    try:
        await visible_entry(session, user, tenant_id, entity_id)
    except EntityNotFoundError:
        raise EntityNotFoundError(detail=_NO_FRAME) from None
    wanted = require_axis(axis) if axis is not None else None
    designated = select(Frame.entity_id).where(
        Frame.tenant_id == tenant_id, Frame.entity_id == entity_id, Frame.axis.in_(AXES)
    )
    if wanted is not None:
        designated = designated.where(Frame.axis == wanted)
    if await session.scalar(designated.limit(1)) is None:
        raise EntityNotFoundError(detail=_NO_FRAME)
    stmt: Select[Any] = (
        select(EntityFrame.entity_id, EntityFrame.axis)
        .join(Entity, Entity.id == EntityFrame.entity_id)
        .where(
            EntityFrame.tenant_id == tenant_id,
            EntityFrame.frame_entity_id == entity_id,
            EntityFrame.axis.in_(AXES),
            visible_entry_clause(vis, EntityFrame.entity_id),
        )
        .order_by(Entity.name, Entity.id, EntityFrame.axis)
    )
    if wanted is not None:
        stmt = stmt.where(EntityFrame.axis == wanted)

    async def rows(found: Any) -> list[MemberOut]:
        stubs = await entry_stubs(session, tenant_id, {row[0] for row in found})
        return [MemberOut(entry=stubs[row[0]], axis=row[1]) for row in found]

    page: Page[MemberOut] = await apaginate(session, stmt, params, transformer=rows)
    return page
