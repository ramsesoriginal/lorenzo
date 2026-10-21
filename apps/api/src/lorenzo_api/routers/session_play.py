"""Explicit play records, independent of outline, dates and the Event graph."""

import hashlib
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select

from lorenzo_api.dependencies import (
    CurrentUser,
    SessionDep,
    get_tenant_or_404,
    require_tenant_participant,
)
from lorenzo_api.entry_visibility import require_visible_entry
from lorenzo_api.etag import etag_for
from lorenzo_api.exceptions import (
    AudiencePreconditionRequiredError,
    ClientIdUnavailableError,
    EntityNotFoundError,
    InvalidKindRequestError,
    PreconditionFailedError,
)
from lorenzo_api.information_visibility import resolve_information_visibility
from lorenzo_api.models import (
    Campaign,
    Entity,
    EventPresentation,
    SceneAppearance,
    SessionSequence,
    StoryEvent,
    StorySession,
)
from lorenzo_api.routers.story_context import source_access
from lorenzo_api.routers.story_sessions import require_version, touch

router = APIRouter(
    prefix="/tenants/{tenant_id}", tags=["Session play"], dependencies=[Depends(get_tenant_or_404)]
)


class PlayAppearance(BaseModel):
    id: uuid.UUID
    name: str
    status: Literal["planned", "played", "skipped"]


class PresentationOut(BaseModel):
    id: uuid.UUID
    appearance_id: uuid.UUID
    event_id: uuid.UUID
    name: str
    is_shared: bool


class PlayOut(BaseModel):
    appearances: list[PlayAppearance]
    played_appearance_ids: list[uuid.UUID]
    presentations: list[PresentationOut]


class PlayWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    played_appearance_ids: list[uuid.UUID] = Field(max_length=1000)
    skipped_appearance_ids: list[uuid.UUID] = Field(default_factory=list, max_length=1000)


class PresentationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    event_id: uuid.UUID
    is_shared: bool = False


class PresentationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_shared: bool


class PresentationOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")
    presentation_ids: list[uuid.UUID] = Field(max_length=1000)


async def appearance_rows(
    session: SessionDep, tenant: uuid.UUID, sid: uuid.UUID
) -> list[SceneAppearance]:
    return list(
        await session.scalars(
            select(SceneAppearance)
            .where(SceneAppearance.tenant_id == tenant, SceneAppearance.session_entity_id == sid)
            .order_by(SceneAppearance.position)
        )
    )


async def require_appearance(
    session: SessionDep, tenant: uuid.UUID, sid: uuid.UUID, aid: uuid.UUID
) -> SceneAppearance:
    row = await session.get(SceneAppearance, aid)
    if row is None or row.tenant_id != tenant or row.session_entity_id != sid:
        raise EntityNotFoundError(detail="No such Scene appearance")
    return row


@router.get("/sessions/{session_id}/play")
async def read_play(
    tenant_id: uuid.UUID,
    session_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> PlayOut:
    entity, manager = await source_access(session, tenant_id, "sessions", session_id, user)
    vis = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    rows = [
        r
        for r in await appearance_rows(session, tenant_id, session_id)
        if vis.can_see_entry(r.entity_id) and vis.can_see_entry(r.scene_entity_id)
    ]
    names: dict[uuid.UUID, str] = dict(
        (
            (key, value)
            for key, value in (
                await session.execute(
                    select(Entity.id, Entity.name).where(Entity.tenant_id == tenant_id)
                )
            ).all()
        )
    )
    ids = {r.entity_id for r in rows}
    presentations = list(
        await session.scalars(
            select(EventPresentation)
            .where(
                EventPresentation.tenant_id == tenant_id,
                EventPresentation.appearance_entity_id.in_(ids),
            )
            .order_by(EventPresentation.position, EventPresentation.id)
        )
    )
    if manager:
        response.headers["ETag"] = etag_for(entity.updated_at)
    response.headers["Cache-Control"] = "private, no-store"
    return PlayOut(
        appearances=[
            PlayAppearance(id=r.entity_id, name=names[r.scene_entity_id], status=r.play_status)
            for r in rows
        ],
        played_appearance_ids=[
            r.entity_id
            for r in sorted(
                (r for r in rows if r.played_position is not None),
                key=lambda r: r.played_position if r.played_position is not None else -1,
            )
        ],
        presentations=[
            PresentationOut(
                id=p.id,
                appearance_id=p.appearance_entity_id,
                event_id=p.event_entity_id,
                name=names[p.event_entity_id],
                is_shared=p.is_shared,
            )
            for p in presentations
            if (manager or p.is_shared) and vis.can_see_entry(p.event_entity_id)
        ],
    )


@router.put("/sessions/{session_id}/play", status_code=204)
async def write_play(
    tenant_id: uuid.UUID,
    session_id: uuid.UUID,
    body: PlayWrite,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> None:
    entity, _ = await source_access(session, tenant_id, "sessions", session_id, user, write=True)
    require_version(if_match, entity)
    rows = await appearance_rows(session, tenant_id, session_id)
    for row in rows:
        await require_visible_entry(
            session, tenant_id=tenant_id, entity_id=row.scene_entity_id, user_id=user.id
        )
    played, skipped = body.played_appearance_ids, body.skipped_appearance_ids
    if len(set(played + skipped)) != len(played + skipped) or not set(played + skipped) <= {
        r.entity_id for r in rows
    }:
        raise InvalidKindRequestError(detail="Use distinct appearances from this Session")
    for row in rows:
        row.play_status = (
            "played"
            if row.entity_id in played
            else "skipped"
            if row.entity_id in skipped
            else "planned"
        )
        row.played_position = played.index(row.entity_id) if row.entity_id in played else None
    await touch(session, entity, user)
    await session.commit()


@router.post("/sessions/{session_id}/scenes/{appearance_id}/presentations", status_code=201)
async def add_presentation(
    tenant_id: uuid.UUID,
    session_id: uuid.UUID,
    appearance_id: uuid.UUID,
    body: PresentationCreate,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> PresentationOut:
    entity, _ = await source_access(session, tenant_id, "sessions", session_id, user, write=True)
    appearance = await require_appearance(session, tenant_id, session_id, appearance_id)
    await require_visible_entry(
        session, tenant_id=tenant_id, entity_id=appearance.scene_entity_id, user_id=user.id
    )
    await require_visible_entry(
        session, tenant_id=tenant_id, entity_id=body.event_id, user_id=user.id
    )
    target = await session.get(StoryEvent, body.event_id)
    if target is None or target.tenant_id != tenant_id:
        raise EntityNotFoundError(detail="No such Event")
    name = await session.scalar(
        select(Entity.name).where(Entity.id == body.event_id, Entity.tenant_id == tenant_id)
    )
    old = await session.get(EventPresentation, body.id)
    if old is not None:
        if (
            old.tenant_id != tenant_id
            or old.appearance_entity_id != appearance_id
            or old.event_entity_id != body.event_id
            or old.is_shared != body.is_shared
        ):
            raise ClientIdUnavailableError(detail="That presentation id is not available")
        return PresentationOut(
            id=old.id,
            appearance_id=appearance_id,
            event_id=body.event_id,
            name=name,
            is_shared=old.is_shared,
        )
    require_version(if_match, entity)
    positions = list(
        await session.scalars(
            select(EventPresentation.position).where(
                EventPresentation.tenant_id == tenant_id,
                EventPresentation.appearance_entity_id == appearance_id,
            )
        )
    )
    session.add(
        EventPresentation(
            id=body.id,
            tenant_id=tenant_id,
            appearance_entity_id=appearance_id,
            event_entity_id=body.event_id,
            is_shared=body.is_shared,
            position=max(positions, default=-1) + 1,
        )
    )
    await touch(session, entity, user)
    await session.commit()
    return PresentationOut(
        id=body.id,
        appearance_id=appearance_id,
        event_id=body.event_id,
        name=name,
        is_shared=body.is_shared,
    )


@router.put("/sessions/{session_id}/scenes/{appearance_id}/presentations/order", status_code=204)
async def order_presentations(
    tenant_id: uuid.UUID,
    session_id: uuid.UUID,
    appearance_id: uuid.UUID,
    body: PresentationOrder,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> None:
    entity, _ = await source_access(session, tenant_id, "sessions", session_id, user, write=True)
    require_version(if_match, entity)
    appearance = await require_appearance(session, tenant_id, session_id, appearance_id)
    await require_visible_entry(
        session, tenant_id=tenant_id, entity_id=appearance.scene_entity_id, user_id=user.id
    )
    rows = list(
        await session.scalars(
            select(EventPresentation).where(
                EventPresentation.tenant_id == tenant_id,
                EventPresentation.appearance_entity_id == appearance_id,
            )
        )
    )
    if len(set(body.presentation_ids)) != len(body.presentation_ids) or set(
        body.presentation_ids
    ) != {p.id for p in rows}:
        raise InvalidKindRequestError(
            detail="Supply each presentation in this appearance exactly once"
        )
    for row in rows:
        await require_visible_entry(
            session, tenant_id=tenant_id, entity_id=row.event_entity_id, user_id=user.id
        )
        row.position = body.presentation_ids.index(row.id)
    await touch(session, entity, user)
    await session.commit()


@router.patch(
    "/sessions/{session_id}/scenes/{appearance_id}/presentations/{presentation_id}", status_code=204
)
async def share_presentation(
    tenant_id: uuid.UUID,
    session_id: uuid.UUID,
    appearance_id: uuid.UUID,
    presentation_id: uuid.UUID,
    body: PresentationUpdate,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> None:
    await change_presentation(
        tenant_id,
        session_id,
        appearance_id,
        presentation_id,
        body.is_shared,
        session,
        user,
        if_match,
    )


@router.delete(
    "/sessions/{session_id}/scenes/{appearance_id}/presentations/{presentation_id}", status_code=204
)
async def remove_presentation(
    tenant_id: uuid.UUID,
    session_id: uuid.UUID,
    appearance_id: uuid.UUID,
    presentation_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> None:
    await change_presentation(
        tenant_id, session_id, appearance_id, presentation_id, None, session, user, if_match
    )


async def change_presentation(
    tenant: uuid.UUID,
    sid: uuid.UUID,
    aid: uuid.UUID,
    pid: uuid.UUID,
    shared: bool | None,
    session: SessionDep,
    user: CurrentUser,
    version: str | None,
) -> None:
    entity, _ = await source_access(session, tenant, "sessions", sid, user, write=True)
    require_version(version, entity)
    appearance = await require_appearance(session, tenant, sid, aid)
    await require_visible_entry(
        session, tenant_id=tenant, entity_id=appearance.scene_entity_id, user_id=user.id
    )
    row = await session.get(EventPresentation, pid)
    if row is None:
        return
    if row.tenant_id != tenant or row.appearance_entity_id != aid:
        raise EntityNotFoundError(detail="No such presentation")
    await require_visible_entry(
        session, tenant_id=tenant, entity_id=row.event_entity_id, user_id=user.id
    )
    if shared is None:
        await session.delete(row)
    else:
        row.is_shared = shared
    await touch(session, entity, user)
    await session.commit()


class OrderedSession(BaseModel):
    id: uuid.UUID
    name: str
    can_manage: bool


class SessionSequenceOut(BaseModel):
    ordered: list[OrderedSession]
    unplaced: list[OrderedSession]


class SessionSequenceWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_ids: list[uuid.UUID] = Field(max_length=1000)


async def sequence_state(
    session: SessionDep, tenant: uuid.UUID, campaign: uuid.UUID, user: CurrentUser
) -> tuple[set[uuid.UUID], set[uuid.UUID], dict[uuid.UUID, str], list[SessionSequence], str]:
    await require_tenant_participant(session, tenant_id=tenant, user=user)
    vis = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant)
    from lorenzo_api.session_access import session_scope

    entries = list(
        await session.scalars(
            select(StorySession).where(
                StorySession.tenant_id == tenant, StorySession.campaign_id == campaign
            )
        )
    )
    visible = {r.entity_id for r in entries if vis.can_see_entry(r.entity_id)}
    managers = (
        visible
        if vis.is_admin
        else visible & set((await session_scope(session, tenant, user.id)).managers)
    )
    names: dict[uuid.UUID, str] = dict(
        (
            (key, value)
            for key, value in (
                await session.execute(
                    select(Entity.id, Entity.name).where(
                        Entity.tenant_id == tenant, Entity.id.in_(visible)
                    )
                )
            ).all()
        )
    )
    rows = list(
        await session.scalars(
            select(SessionSequence)
            .where(SessionSequence.tenant_id == tenant, SessionSequence.campaign_id == campaign)
            .order_by(SessionSequence.position)
        )
    )
    token = hashlib.sha256(
        (
            str(sorted(managers))
            + str([r.session_entity_id for r in rows if r.session_entity_id in managers])
        ).encode()
    ).hexdigest()
    return visible, managers, names, rows, f'W/"{token}"'


@router.get("/campaigns/{campaign_id}/session-sequence")
async def read_session_sequence(
    tenant_id: uuid.UUID,
    campaign_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> SessionSequenceOut:
    visible, managers, names, rows, token = await sequence_state(
        session, tenant_id, campaign_id, user
    )
    ordered = [r.session_entity_id for r in rows if r.session_entity_id in visible]
    if managers:
        response.headers["ETag"] = token
    response.headers["Cache-Control"] = "private, no-store"
    return SessionSequenceOut(
        ordered=[OrderedSession(id=i, name=names[i], can_manage=i in managers) for i in ordered],
        unplaced=[
            OrderedSession(id=i, name=names[i], can_manage=i in managers)
            for i in sorted(visible - set(ordered))
        ],
    )


@router.put("/campaigns/{campaign_id}/session-sequence", status_code=204)
async def write_session_sequence(
    tenant_id: uuid.UUID,
    campaign_id: uuid.UUID,
    body: SessionSequenceWrite,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> None:
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    campaign = await session.scalar(
        select(Campaign)
        .where(Campaign.tenant_id == tenant_id, Campaign.id == campaign_id)
        .with_for_update()
    )
    if campaign is None:
        raise EntityNotFoundError(detail="No such campaign")
    _, managers, _, rows, token = await sequence_state(session, tenant_id, campaign_id, user)
    if not managers:
        raise EntityNotFoundError(detail="No manageable Sessions")
    if if_match is None:
        raise AudiencePreconditionRequiredError(detail="Read Session order and send its ETag")
    if if_match != token:
        raise PreconditionFailedError(detail="Session order changed; review the saved sequence")
    ids = body.session_ids
    if len(set(ids)) != len(ids) or not set(ids) <= managers:
        raise InvalidKindRequestError(detail="Order only your manageable Sessions")
    # Preserve inaccessible slots and relative positions.
    # The scoped token carries no hidden revisions.
    slots = [r.position for r in rows if r.session_entity_id in managers]
    next_position = max([r.position for r in rows], default=-1) + 1
    await session.execute(
        delete(SessionSequence).where(
            SessionSequence.tenant_id == tenant_id,
            SessionSequence.campaign_id == campaign_id,
            SessionSequence.session_entity_id.in_(managers),
        )
    )
    for index, sid in enumerate(ids):
        position = slots[index] if index < len(slots) else next_position + index - len(slots)
        session.add(
            SessionSequence(
                session_entity_id=sid,
                tenant_id=tenant_id,
                campaign_id=campaign_id,
                position=position,
            )
        )
    await session.commit()
