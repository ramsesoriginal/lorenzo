"""Permission-filtered world references, without inferred participation or learning."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select, true

from lorenzo_api.dependencies import (
    CurrentUser,
    SessionDep,
    get_tenant_or_404,
    require_tenant_participant,
    set_tenant_rls_context,
)
from lorenzo_api.entry_visibility import require_visible_entry, visible_entry_clause
from lorenzo_api.etag import etag_for
from lorenzo_api.exceptions import (
    EntityNotFoundError,
    EntitySlugConflictError,
    InformationManagementForbiddenError,
    InvalidKindRequestError,
)
from lorenzo_api.information_visibility import resolve_information_visibility
from lorenzo_api.models import (
    Entity,
    EntityAudience,
    EntitySlug,
    Scene,
    SceneAppearance,
    StorySession,
)
from lorenzo_api.routers.entities import authorize_entity_write
from lorenzo_api.routers.story_sessions import check_period, require_version, touch
from lorenzo_api.schemas.common import Slug
from lorenzo_api.story_context import SCENE_REFERENCES, SESSION_REFERENCES

router = APIRouter(
    prefix="/tenants/{tenant_id}", tags=["Scenes"], dependencies=[Depends(get_tenant_or_404)]
)
SourceKind = Literal["scenes", "sessions"]
ReferenceKind = Literal["facts", "events", "beings"]


class ReferenceShare(BaseModel):
    is_shared: bool = False


class ReferenceOut(BaseModel):
    id: uuid.UUID
    name: str
    kind: ReferenceKind
    is_shared: bool


class SceneOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str | None
    period_entity_id: uuid.UUID | None
    is_public: bool
    can_manage: bool


class SceneUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    slug: Slug | None = None
    period_entity_id: uuid.UUID | None = None
    is_public: bool | None = None


async def source_access(
    session: SessionDep,
    tenant_id: uuid.UUID,
    source_kind: SourceKind,
    source_id: uuid.UUID,
    user: CurrentUser,
    *,
    write: bool = False,
) -> tuple[Entity, bool]:
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    await require_visible_entry(session, entity_id=source_id, tenant_id=tenant_id, user_id=user.id)
    model = Scene if source_kind == "scenes" else StorySession
    if (
        await session.scalar(
            select(model.entity_id).where(
                model.entity_id == source_id, model.tenant_id == tenant_id
            )
        )
        is None
    ):
        raise EntityNotFoundError(detail="No such Scene or Session in this library")
    stmt = select(Entity).where(Entity.tenant_id == tenant_id, Entity.id == source_id)
    entity = await session.scalar(stmt.with_for_update() if write else stmt)
    assert entity is not None
    try:
        await authorize_entity_write(session, tenant_id=tenant_id, entity_id=source_id, user=user)
        manager = True
    except InformationManagementForbiddenError:
        manager = False
    if write and not manager:
        raise InformationManagementForbiddenError(
            detail="Only this entry's managers can edit its references"
        )
    return entity, manager


@router.get("/{source_kind}/{source_id}/references")
async def list_story_references(
    tenant_id: uuid.UUID,
    source_kind: SourceKind,
    source_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> list[ReferenceOut]:
    entity, manager = await source_access(session, tenant_id, source_kind, source_id, user)
    vis = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    output = []
    for kind, binding in (
        SCENE_REFERENCES if source_kind == "scenes" else SESSION_REFERENCES
    ).items():
        rows = await session.execute(
            select(Entity, binding.model.is_shared)
            .join(binding.model, getattr(binding.model, binding.target) == Entity.id)
            .where(
                binding.model.tenant_id == tenant_id,
                getattr(binding.model, binding.source) == source_id,
                visible_entry_clause(vis, Entity.id),
                true() if manager else binding.model.is_shared.is_(True),
            )
            .order_by(Entity.name, Entity.id)
        )
        for target, shared in rows:
            output.append(ReferenceOut(id=target.id, name=target.name, kind=kind, is_shared=shared))
    if manager:
        response.headers["ETag"] = etag_for(entity.updated_at)
    response.headers["Cache-Control"] = "private, no-store"
    return output


async def change_reference(
    tenant_id: uuid.UUID,
    source_kind: SourceKind,
    source_id: uuid.UUID,
    kind: ReferenceKind,
    target_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    if_match: str | None,
    sharing: bool | None,
) -> None:
    entity, _ = await source_access(session, tenant_id, source_kind, source_id, user, write=True)
    require_version(if_match, entity)
    binding = (SCENE_REFERENCES if source_kind == "scenes" else SESSION_REFERENCES).get(kind)
    if binding is None:
        raise InvalidKindRequestError(
            detail="Session players and Characters are managed through its roster"
        )
    await require_visible_entry(session, entity_id=target_id, tenant_id=tenant_id, user_id=user.id)
    if (
        await session.scalar(
            select(binding.target_model.entity_id).where(
                binding.target_model.entity_id == target_id,
                binding.target_model.tenant_id == tenant_id,
            )
        )
        is None
    ):
        raise EntityNotFoundError(detail="No such target in this library")
    existing = await session.get(binding.model, (source_id, target_id))
    changed = False
    if sharing is None:
        if existing is not None:
            await session.delete(existing)
            changed = True
    elif existing is None:
        session.add(
            binding.model(
                **{
                    binding.source: source_id,
                    binding.target: target_id,
                    "tenant_id": tenant_id,
                    "is_shared": sharing,
                }
            )
        )
        changed = True
    elif existing.is_shared != sharing:
        existing.is_shared = sharing
        changed = True
    if changed:
        await touch(session, entity, user)
    await session.commit()


@router.put("/{source_kind}/{source_id}/references/{kind}/{target_id}", status_code=204)
async def set_story_reference(
    tenant_id: uuid.UUID,
    source_kind: SourceKind,
    source_id: uuid.UUID,
    kind: ReferenceKind,
    target_id: uuid.UUID,
    body: ReferenceShare,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> None:
    await change_reference(
        tenant_id, source_kind, source_id, kind, target_id, session, user, if_match, body.is_shared
    )


@router.delete("/{source_kind}/{source_id}/references/{kind}/{target_id}", status_code=204)
async def remove_story_reference(
    tenant_id: uuid.UUID,
    source_kind: SourceKind,
    source_id: uuid.UUID,
    kind: ReferenceKind,
    target_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> None:
    await change_reference(
        tenant_id, source_kind, source_id, kind, target_id, session, user, if_match, None
    )


@router.get("/scenes/{scene_id}")
async def get_scene(
    tenant_id: uuid.UUID,
    scene_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> SceneOut:
    entity, manager = await source_access(session, tenant_id, "scenes", scene_id, user)
    row = await session.get(Scene, scene_id)
    assert row is not None
    vis = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    audience = await session.get(EntityAudience, scene_id)
    response.headers["ETag"] = etag_for(entity.updated_at)
    response.headers["Cache-Control"] = "private, no-store"
    return SceneOut(
        id=scene_id,
        name=entity.name,
        slug=await session.scalar(select(EntitySlug.slug).where(EntitySlug.entity_id == scene_id)),
        period_entity_id=row.period_entity_id
        if row.period_entity_id is None or vis.can_see_entry(row.period_entity_id)
        else None,
        is_public=audience.is_public if audience else True,
        can_manage=manager,
    )


@router.patch("/scenes/{scene_id}")
async def update_scene(
    tenant_id: uuid.UUID,
    scene_id: uuid.UUID,
    body: SceneUpdate,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> SceneOut:
    entity, _ = await source_access(session, tenant_id, "scenes", scene_id, user, write=True)
    require_version(if_match, entity)
    row = await session.get(Scene, scene_id)
    assert row is not None
    if "period_entity_id" in body.model_fields_set:
        if row.period_entity_id != body.period_entity_id:
            await check_period(session, tenant_id, row.period_entity_id, user)
        await check_period(session, tenant_id, body.period_entity_id, user)
        row.period_entity_id = body.period_entity_id
    if body.name is not None:
        entity.name = body.name
    if "slug" in body.model_fields_set:
        existing = await session.get(EntitySlug, scene_id)
        if body.slug:
            occupied = await session.scalar(
                select(EntitySlug.entity_id).where(
                    EntitySlug.tenant_id == tenant_id, EntitySlug.slug == body.slug
                )
            )
            if occupied is not None and occupied != scene_id:
                raise EntitySlugConflictError(detail="That link name is already in use")
            if existing is None:
                session.add(EntitySlug(entity_id=scene_id, tenant_id=tenant_id, slug=body.slug))
            else:
                existing.slug = body.slug
        elif existing is not None:
            await session.delete(existing)
    if body.is_public is not None:
        audience = await session.get(EntityAudience, scene_id)
        if audience is None:
            audience = EntityAudience(
                entity_id=scene_id, tenant_id=tenant_id, is_public=body.is_public
            )
            session.add(audience)
        else:
            audience.is_public = body.is_public
    await touch(session, entity, user)
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return await get_scene(tenant_id, scene_id, response, session, user)


@router.delete("/sessions/{session_id}/scenes/{appearance_id}", status_code=204)
async def delete_scene_appearance(
    tenant_id: uuid.UUID,
    session_id: uuid.UUID,
    appearance_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> None:
    entity, _ = await source_access(session, tenant_id, "sessions", session_id, user, write=True)
    require_version(if_match, entity)
    appearance = await session.get(SceneAppearance, appearance_id)
    if appearance is None:
        return
    if appearance.session_entity_id != session_id or appearance.tenant_id != tenant_id:
        raise EntityNotFoundError(detail="No such Scene appearance")
    from lorenzo_api.exceptions import EntityKindInUseError

    await require_visible_entry(
        session, tenant_id=tenant_id, entity_id=appearance_id, user_id=user.id
    )
    from lorenzo_api.models import EventPresentation

    if (
        appearance.play_status != "planned"
        or await session.scalar(
            select(EventPresentation.id)
            .where(
                EventPresentation.tenant_id == tenant_id,
                EventPresentation.appearance_entity_id == appearance_id,
            )
            .limit(1)
        )
        is not None
    ):
        raise EntityKindInUseError(
            detail="Resolve this appearance's played record and presentations before removing it"
        )
    from lorenzo_api.learning import require_no_learning

    await require_no_learning(session, tenant_id, entity_id=appearance_id)
    await session.execute(
        delete(Entity).where(Entity.id == appearance_id, Entity.tenant_id == tenant_id)
    )
    await touch(session, entity, user)
    await session.commit()
