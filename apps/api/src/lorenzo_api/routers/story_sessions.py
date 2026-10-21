"""Session preparation, roster and entry-backed Scene appearances (ADR 0317)."""

import uuid
from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select

from lorenzo_api.client_ids import existing_in_tenant, insert_with_client_id
from lorenzo_api.dependencies import (
    CurrentUser,
    SessionDep,
    get_tenant_or_404,
    require_tenant_participant,
    set_tenant_rls_context,
)
from lorenzo_api.entry_visibility import require_visible_entry, visible_entry_clause
from lorenzo_api.etag import check_if_match, etag_for
from lorenzo_api.exceptions import (
    ClientIdUnavailableError,
    EntityNotFoundError,
    EventOrderPreconditionRequiredError,
    InformationManagementForbiddenError,
    InvalidKindRequestError,
)
from lorenzo_api.information_visibility import resolve_information_visibility
from lorenzo_api.models import (
    CampaignGm,
    CharacterPlayer,
    Entity,
    EntityAudience,
    EntitySlug,
    Player,
    Scene,
    SceneAppearance,
    SessionCharacter,
    SessionGm,
    SessionPlayer,
    StorySession,
)
from lorenzo_api.schemas.common import Slug
from lorenzo_api.session_access import manages_planning_entry

router = APIRouter(
    prefix="/tenants/{tenant_id}", tags=["Sessions"], dependencies=[Depends(get_tenant_or_404)]
)


class SessionCreate(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str = Field(min_length=1, max_length=300)
    slug: Slug | None = None
    campaign_id: uuid.UUID
    real_date: date | None = None
    start_period_id: uuid.UUID | None = None


class SessionUpdate(BaseModel):
    slug: Slug | None = None
    name: str | None = Field(default=None, min_length=1, max_length=300)
    real_date: date | None = None
    start_period_id: uuid.UUID | None = None


class Attendee(BaseModel):
    player_id: uuid.UUID
    character_ids: list[uuid.UUID] = []


class SessionRoster(BaseModel):
    gm_user_ids: list[uuid.UUID] = Field(min_length=1)
    players: list[Attendee] = []


class SceneCreate(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str = Field(min_length=1, max_length=300)
    slug: Slug | None = None
    period_entity_id: uuid.UUID | None = None
    is_public: bool = False


class AppearanceCreate(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    scene_entity_id: uuid.UUID
    is_shared: bool = False


class AppearanceUpdate(BaseModel):
    is_shared: bool


class OutlineOrder(BaseModel):
    appearance_ids: list[uuid.UUID]


class AppearanceOut(BaseModel):
    id: uuid.UUID
    scene_entity_id: uuid.UUID
    name: str
    is_shared: bool


class SessionOut(BaseModel):
    tenant_id: uuid.UUID
    id: uuid.UUID
    name: str
    slug: str | None
    campaign_id: uuid.UUID
    real_date: date | None
    start_period_id: uuid.UUID | None
    can_manage: bool
    gm_user_ids: list[uuid.UUID]
    players: list[Attendee]
    scenes: list[AppearanceOut]


async def planning_access(
    session: SessionDep,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    user: CurrentUser,
    *,
    write: bool = False,
) -> Entity:
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    await require_visible_entry(session, entity_id=entity_id, tenant_id=tenant_id, user_id=user.id)
    entity = await session.scalar(
        select(Entity)
        .where(Entity.id == entity_id, Entity.tenant_id == tenant_id)
        .with_for_update()
        if write
        else select(Entity).where(Entity.id == entity_id, Entity.tenant_id == tenant_id)
    )
    if entity is None:
        raise EntityNotFoundError(detail="No such entry in this library")
    if write and not await manages_planning_entry(session, tenant_id, entity_id, user.id):
        raise InformationManagementForbiddenError(
            detail="Only this Session's GMs can edit its preparation"
        )
    return entity


def require_version(if_match: str | None, entity: Entity) -> None:
    if if_match is None:
        raise EventOrderPreconditionRequiredError(
            detail="Refresh this Session and send its ETag in If-Match"
        )
    check_if_match(if_match, updated_at=entity.updated_at)


async def touch(session: SessionDep, entity: Entity, user: CurrentUser) -> None:
    entity.updated_at = datetime.now(UTC)
    entity.updated_by = user.id
    await session.flush()
    session.info.pop("visible_entry_checks", None)


async def check_period(
    session: SessionDep, tenant_id: uuid.UUID, period_id: uuid.UUID | None, user: CurrentUser
) -> None:
    if period_id is None:
        return
    from lorenzo_api.models import CalendarPeriod

    await require_visible_entry(session, entity_id=period_id, tenant_id=tenant_id, user_id=user.id)
    if (
        await session.scalar(
            select(CalendarPeriod.entity_id).where(
                CalendarPeriod.entity_id == period_id, CalendarPeriod.tenant_id == tenant_id
            )
        )
        is None
    ):
        raise EntityNotFoundError(detail="No such calendar period in this library")


async def create_entry(
    session: SessionDep,
    tenant_id: uuid.UUID,
    user: CurrentUser,
    id: uuid.UUID,
    name: str,
    slug: str | None = None,
    *,
    public: bool = False,
) -> Entity:
    entry = Entity(id=id, tenant_id=tenant_id, name=name, created_by=user.id, updated_by=user.id)
    await insert_with_client_id(session, entry)
    session.add(EntityAudience(entity_id=id, tenant_id=tenant_id, is_public=public))
    if slug:
        from lorenzo_api.exceptions import EntitySlugConflictError

        if (
            await session.scalar(
                select(EntitySlug.entity_id).where(
                    EntitySlug.tenant_id == tenant_id, EntitySlug.slug == slug
                )
            )
            is not None
        ):
            raise EntitySlugConflictError(detail="That link name is already in use")
        session.add(EntitySlug(entity_id=id, tenant_id=tenant_id, slug=slug))
    return entry


async def session_result(
    session: SessionDep, tenant_id: uuid.UUID, id: uuid.UUID, user: CurrentUser, response: Response
) -> SessionOut:
    entity = await planning_access(session, tenant_id, id, user)
    row = await session.get(StorySession, id)
    if row is None:
        raise EntityNotFoundError(detail="No such Session in this library")
    vis = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    manager = await manages_planning_entry(session, tenant_id, id, user.id)
    appearances = list(
        await session.scalars(
            select(SceneAppearance)
            .join(Entity, Entity.id == SceneAppearance.entity_id)
            .where(
                SceneAppearance.tenant_id == tenant_id,
                SceneAppearance.session_entity_id == id,
                visible_entry_clause(vis, Entity.id),
            )
            .order_by(SceneAppearance.position)
        )
    )
    scene_rows = []
    for appearance in appearances:
        e = await session.get(Entity, appearance.entity_id)
        assert e is not None
        scene_rows.append(
            AppearanceOut(
                id=e.id,
                scene_entity_id=appearance.scene_entity_id,
                name=e.name,
                is_shared=appearance.is_shared,
            )
        )
    attendee_rows = []
    for pid in await session.scalars(
        select(SessionPlayer.player_id)
        .where(SessionPlayer.tenant_id == tenant_id, SessionPlayer.session_entity_id == id)
        .order_by(SessionPlayer.player_id)
    ):
        chars = list(
            await session.scalars(
                select(SessionCharacter.character_entity_id).where(
                    SessionCharacter.tenant_id == tenant_id,
                    SessionCharacter.session_entity_id == id,
                    SessionCharacter.player_id == pid,
                )
            )
        )
        attendee_rows.append(Attendee(player_id=pid, character_ids=chars))
    response.headers["ETag"] = etag_for(entity.updated_at)
    response.headers["Cache-Control"] = "private, no-store"
    start = (
        row.start_period_id
        if row.start_period_id is None or vis.can_see_entry(row.start_period_id)
        else None
    )
    return SessionOut(
        tenant_id=tenant_id,
        id=id,
        name=entity.name,
        slug=await session.scalar(select(EntitySlug.slug).where(EntitySlug.entity_id == id)),
        campaign_id=row.campaign_id,
        real_date=row.real_date,
        start_period_id=start,
        can_manage=manager,
        gm_user_ids=list(
            await session.scalars(
                select(SessionGm.user_id).where(
                    SessionGm.tenant_id == tenant_id, SessionGm.session_entity_id == id
                )
            )
        ),
        players=attendee_rows,
        scenes=scene_rows,
    )


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(
    tenant_id: uuid.UUID, response: Response, session: SessionDep, user: CurrentUser
) -> list[SessionOut]:
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    vis = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    ids = list(
        await session.scalars(
            select(StorySession.entity_id)
            .join(Entity, Entity.id == StorySession.entity_id)
            .where(StorySession.tenant_id == tenant_id, visible_entry_clause(vis, Entity.id))
            .order_by(Entity.name, Entity.id)
        )
    )
    return [await session_result(session, tenant_id, id, user, response) for id in ids]


@router.post("/sessions", status_code=201)
async def create_session(
    tenant_id: uuid.UUID,
    body: SessionCreate,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> SessionOut:
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    if (
        await session.scalar(
            select(CampaignGm.user_id).where(
                CampaignGm.tenant_id == tenant_id,
                CampaignGm.campaign_id == body.campaign_id,
                CampaignGm.user_id == user.id,
            )
        )
        is None
    ):
        raise InformationManagementForbiddenError(
            detail="Choose a campaign you GM to prepare a Session"
        )
    old = await existing_in_tenant(session, Entity, body.id, tenant_id)
    if old is not None:
        row = await session.get(StorySession, body.id)
        if row is None or old.created_by != user.id or row.campaign_id != body.campaign_id:
            raise ClientIdUnavailableError(detail="That id is not available")
        response.status_code = 200
        return await session_result(session, tenant_id, body.id, user, response)
    await check_period(session, tenant_id, body.start_period_id, user)
    await create_entry(session, tenant_id, user, body.id, body.name, body.slug)
    session.add(
        StorySession(
            entity_id=body.id,
            tenant_id=tenant_id,
            campaign_id=body.campaign_id,
            real_date=body.real_date,
            start_period_id=body.start_period_id,
        )
    )
    await session.flush()
    session.add(SessionGm(session_entity_id=body.id, user_id=user.id, tenant_id=tenant_id))
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return await session_result(session, tenant_id, body.id, user, response)


@router.get("/sessions/{session_id}")
async def get_session(
    tenant_id: uuid.UUID,
    session_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> SessionOut:
    return await session_result(session, tenant_id, session_id, user, response)


@router.patch("/sessions/{session_id}")
async def update_session(
    tenant_id: uuid.UUID,
    session_id: uuid.UUID,
    body: SessionUpdate,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> SessionOut:
    entity = await planning_access(session, tenant_id, session_id, user, write=True)
    row = await session.get(StorySession, session_id)
    if row is None:
        raise EntityNotFoundError(detail="No such Session")
    require_version(if_match, entity)
    if "start_period_id" in body.model_fields_set:
        await check_period(session, tenant_id, body.start_period_id, user)
    for key, value in body.model_dump(exclude_unset=True).items():
        if key == "slug":
            current = await session.get(EntitySlug, session_id)
            if value:
                from lorenzo_api.exceptions import EntitySlugConflictError

                occupied = await session.scalar(
                    select(EntitySlug.entity_id).where(
                        EntitySlug.tenant_id == tenant_id, EntitySlug.slug == value
                    )
                )
                if occupied is not None and occupied != session_id:
                    raise EntitySlugConflictError(detail="That link name is already in use")
                if current is None:
                    session.add(EntitySlug(entity_id=session_id, tenant_id=tenant_id, slug=value))
                else:
                    current.slug = value
            elif current is not None:
                await session.delete(current)
        elif key == "name":
            if value is not None:
                entity.name = value
        else:
            setattr(row, key, value)
    await touch(session, entity, user)
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return await session_result(session, tenant_id, session_id, user, response)


@router.put("/sessions/{session_id}/roster", status_code=204)
async def replace_session_roster(
    tenant_id: uuid.UUID,
    session_id: uuid.UUID,
    body: SessionRoster,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> None:
    entity = await planning_access(session, tenant_id, session_id, user, write=True)
    row = await session.get(StorySession, session_id)
    if row is None:
        raise EntityNotFoundError(detail="No such Session")
    require_version(if_match, entity)
    gms = set(body.gm_user_ids)
    permitted = set(
        await session.scalars(
            select(CampaignGm.user_id).where(
                CampaignGm.tenant_id == tenant_id, CampaignGm.campaign_id == row.campaign_id
            )
        )
    )
    if not gms <= permitted:
        raise InvalidKindRequestError(detail="Session GMs must already GM this campaign")
    if len({p.player_id for p in body.players}) != len(body.players):
        raise InvalidKindRequestError(detail="List each player once")
    for attendee in body.players:
        player = await session.get(Player, attendee.player_id)
        if player is None or player.tenant_id != tenant_id or player.campaign_id != row.campaign_id:
            raise InvalidKindRequestError(detail="Choose players from this campaign")
        controlled = set(
            await session.scalars(
                select(CharacterPlayer.character_entity_id).where(
                    CharacterPlayer.tenant_id == tenant_id, CharacterPlayer.player_id == player.id
                )
            )
        )
        if not set(attendee.character_ids) <= controlled:
            raise InvalidKindRequestError(detail="Choose Characters this player controls")
    for model in (SessionCharacter, SessionPlayer, SessionGm):
        await session.execute(
            delete(model).where(model.tenant_id == tenant_id, model.session_entity_id == session_id)
        )
    session.add_all(
        SessionGm(session_entity_id=session_id, tenant_id=tenant_id, user_id=uid) for uid in gms
    )
    session.add_all(
        SessionPlayer(
            session_entity_id=session_id,
            tenant_id=tenant_id,
            campaign_id=row.campaign_id,
            player_id=p.player_id,
        )
        for p in body.players
    )
    await session.flush()
    session.add_all(
        SessionCharacter(
            session_entity_id=session_id,
            tenant_id=tenant_id,
            player_id=p.player_id,
            character_entity_id=cid,
        )
        for p in body.players
        for cid in set(p.character_ids)
    )
    await touch(session, entity, user)
    await session.commit()


@router.post("/scenes", status_code=201)
async def create_scene(
    tenant_id: uuid.UUID,
    body: SceneCreate,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> dict[str, uuid.UUID]:
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    from lorenzo_api.campaign_access import can_manage_any_campaign_in_tenant, is_tenant_author

    if not await can_manage_any_campaign_in_tenant(
        session, tenant_id=tenant_id, user_id=user.id
    ) and not await is_tenant_author(session, tenant_id=tenant_id, user_id=user.id):
        raise InformationManagementForbiddenError(detail="Only GMs and Authors can create Scenes")
    old = await existing_in_tenant(session, Entity, body.id, tenant_id)
    if old is not None:
        if old.created_by != user.id or await session.get(Scene, body.id) is None:
            raise ClientIdUnavailableError(detail="That id is not available")
        await require_visible_entry(
            session, entity_id=body.id, tenant_id=tenant_id, user_id=user.id
        )
        response.status_code = 200
        return {"id": body.id}
    await check_period(session, tenant_id, body.period_entity_id, user)
    await create_entry(
        session, tenant_id, user, body.id, body.name, body.slug, public=body.is_public
    )
    session.add(
        Scene(entity_id=body.id, tenant_id=tenant_id, period_entity_id=body.period_entity_id)
    )
    await session.commit()
    return {"id": body.id}


@router.post("/sessions/{session_id}/scenes", status_code=201)
async def add_scene_appearance(
    tenant_id: uuid.UUID,
    session_id: uuid.UUID,
    body: AppearanceCreate,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> SessionOut:
    entity = await planning_access(session, tenant_id, session_id, user, write=True)
    await require_visible_entry(
        session, entity_id=body.scene_entity_id, tenant_id=tenant_id, user_id=user.id
    )
    scene = await session.get(Scene, body.scene_entity_id)
    source = await session.get(Entity, body.scene_entity_id)
    if scene is None or scene.tenant_id != tenant_id or source is None:
        raise EntityNotFoundError(detail="No such Scene")
    old = await existing_in_tenant(session, Entity, body.id, tenant_id)
    if old is not None:
        appearance = await session.get(SceneAppearance, body.id)
        if (
            appearance is None
            or appearance.session_entity_id != session_id
            or appearance.scene_entity_id != body.scene_entity_id
        ):
            raise ClientIdUnavailableError(detail="That id is not available")
        response.status_code = 200
        return await session_result(session, tenant_id, session_id, user, response)
    require_version(if_match, entity)
    position = (
        await session.scalar(
            select(func.max(SceneAppearance.position)).where(
                SceneAppearance.tenant_id == tenant_id,
                SceneAppearance.session_entity_id == session_id,
            )
        )
        or 0
    ) + 1
    await create_entry(session, tenant_id, user, body.id, source.name)
    session.add(
        SceneAppearance(
            entity_id=body.id,
            tenant_id=tenant_id,
            session_entity_id=session_id,
            scene_entity_id=scene.entity_id,
            position=position,
            is_shared=body.is_shared,
        )
    )
    await touch(session, entity, user)
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return await session_result(session, tenant_id, session_id, user, response)


@router.put("/sessions/{session_id}/scenes/order")
async def reorder_scene_outline(
    tenant_id: uuid.UUID,
    session_id: uuid.UUID,
    body: OutlineOrder,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> SessionOut:
    entity = await planning_access(session, tenant_id, session_id, user, write=True)
    require_version(if_match, entity)
    rows = list(
        await session.scalars(
            select(SceneAppearance).where(
                SceneAppearance.tenant_id == tenant_id,
                SceneAppearance.session_entity_id == session_id,
            )
        )
    )
    if set(body.appearance_ids) != {r.entity_id for r in rows} or len(body.appearance_ids) != len(
        rows
    ):
        raise InvalidKindRequestError(detail="Refresh and include every Scene appearance once")
    for row in rows:
        row.position = body.appearance_ids.index(row.entity_id)
    await touch(session, entity, user)
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return await session_result(session, tenant_id, session_id, user, response)


@router.patch("/sessions/{session_id}/scenes/{appearance_id}")
async def share_scene_appearance(
    tenant_id: uuid.UUID,
    session_id: uuid.UUID,
    appearance_id: uuid.UUID,
    body: AppearanceUpdate,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> SessionOut:
    entity = await planning_access(session, tenant_id, session_id, user, write=True)
    require_version(if_match, entity)
    row = await session.get(SceneAppearance, appearance_id)
    if row is None or row.session_entity_id != session_id or row.tenant_id != tenant_id:
        raise EntityNotFoundError(detail="No such Scene appearance")
    row.is_shared = body.is_shared
    await touch(session, entity, user)
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return await session_result(session, tenant_id, session_id, user, response)


my_router = APIRouter(tags=["Sessions"])


@my_router.get("/me/sessions")
async def my_sessions(
    response: Response, session: SessionDep, user: CurrentUser
) -> list[SessionOut]:
    from lorenzo_api.session_access import session_scope

    tenant_ids = set(
        await session.scalars(select(Player.tenant_id).where(Player.user_id == user.id))
    ) | set(
        await session.scalars(select(CampaignGm.tenant_id).where(CampaignGm.user_id == user.id))
    )
    result = []
    for tenant_id in sorted(tenant_ids):
        await set_tenant_rls_context(session, tenant_id)
        scope = await session_scope(session, tenant_id, user.id)
        ids = await session.scalars(
            select(StorySession.entity_id)
            .where(StorySession.tenant_id == tenant_id, StorySession.entity_id.in_(scope.readers))
            .order_by(StorySession.real_date.desc().nullslast(), StorySession.entity_id)
        )
        for id in ids:
            result.append(await session_result(session, tenant_id, id, user, response))
    if "etag" in response.headers:
        del response.headers["etag"]
    response.headers["Cache-Control"] = "private, no-store"
    return result
