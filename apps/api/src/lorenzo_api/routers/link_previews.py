"""GET /tenants/{t}/entities/{id}/preview (ADR 0264): the small card a link shows when pointed at.

Open to a tenant participant, like `GET .../entities/{id}`, and it shows no more than that read:
information goes through the same `InformationVisibility.can_see`, and an entry that is missing
answers `404` exactly as the single read does. What the card holds, per kind, is the registry in
`link_previews.py`.
"""

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from lorenzo_api.dependencies import (
    CurrentUser,
    SessionDep,
    get_tenant_or_404,
    require_tenant_participant,
)
from lorenzo_api.entry_visibility import require_visible_entry
from lorenzo_api.exceptions import EntityNotFoundError
from lorenzo_api.information_visibility import (
    InformationVisibility,
    resolve_information_visibility,
)
from lorenzo_api.inherited_information import ancestors_of
from lorenzo_api.link_previews import PreviewTemplate, excerpt_of, pick_stats, template_for
from lorenzo_api.models import (
    Being,
    Entity,
    Information,
    Payload,
    PayloadPicture,
    StatDefinition,
    VEffectiveStat,
    formula_load_options,
)
from lorenzo_api.models.entity_view_mixin import description_pairs
from lorenzo_api.schemas.entities import _kinds_out, _stats_out
from lorenzo_api.schemas.link_previews import LinkPreviewOut, LinkPreviewStatOut
from lorenzo_api.stat_contents import attach_contents

router = APIRouter(
    prefix="/tenants/{tenant_id}/entities",
    tags=["entities"],
    dependencies=[Depends(get_tenant_or_404)],
)


def _main_picture_url(
    sources: list[Entity], request: Request, visibility: InformationVisibility
) -> str | None:
    """The first main picture the caller may see, the entry's own before an ancestor's."""
    for entity in sources:
        for info in entity.information:
            if info.type != "main_picture" or not visibility.can_see(info):
                continue
            for payload in info.payloads:
                if payload.picture is not None:
                    return str(
                        request.url_for(
                            "payload_content", tenant_id=payload.tenant_id, payload_id=payload.id
                        )
                    )
    return None


def _excerpt(
    sources: list[Entity], template: PreviewTemplate, visibility: InformationVisibility
) -> str:
    for entity in sources:
        for content, _locale in description_pairs(entity, visibility):
            text = excerpt_of(content, template.excerpt_chars)
            if text:
                return text
    return ""


@router.get("/{entity_id}/preview")
async def get_entity_preview(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    user: CurrentUser,
) -> LinkPreviewOut:
    """The card for one entry: name, kinds, link name, main picture, a few stats chosen by the
    entry's kind, and the start of the description. Only what the caller may read is in it."""
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    await require_visible_entry(session, entity_id=entity_id, tenant_id=tenant_id, user_id=user.id)
    entity = await session.scalar(
        select(Entity)
        .where(Entity.id == entity_id, Entity.tenant_id == tenant_id)
        .options(
            selectinload(Entity.effective_stats)
            .selectinload(VEffectiveStat.stat_definition)
            .selectinload(StatDefinition.stat_group),
            # Where an inherited value comes from (ADR 0276).
            selectinload(Entity.effective_stats).selectinload(VEffectiveStat.source_entity),
            *formula_load_options(
                selectinload(Entity.effective_stats).selectinload(VEffectiveStat.computed_stat)
            ),
            selectinload(Entity.stats),
            selectinload(Entity.information)
            .selectinload(Information.payloads)
            .selectinload(Payload.description),
            # The file's bytes are not read for a card, only that there is a picture.
            selectinload(Entity.information)
            .selectinload(Information.payloads)
            .selectinload(Payload.picture)
            .load_only(PayloadPicture.payload_id, PayloadPicture.file_type),
            selectinload(Entity.information).selectinload(Information.knowledge_links),
            selectinload(Entity.slug),
            selectinload(Entity.fact),
            selectinload(Entity.calendar),
            selectinload(Entity.calendar_period),
            selectinload(Entity.story_event),
            selectinload(Entity.calendar_observance),
            selectinload(Entity.item),
            selectinload(Entity.item_instance),
            selectinload(Entity.being).selectinload(Being.character),
        )
    )
    if entity is None:
        raise EntityNotFoundError(detail=f"No entity with id {entity_id} in tenant {tenant_id}")
    await attach_contents(session, [entity], tenant_id=tenant_id)
    visibility = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)

    kinds = _kinds_out(entity)
    template = template_for(kinds)
    sources = [entity]
    if template.inherits:
        sources += await ancestors_of(session, tenant_id=tenant_id, entity_id=entity.id)
    values = {stat.name: stat.value for stat in _stats_out(entity, visibility)}
    return LinkPreviewOut(
        entity_id=entity.id,
        name=entity.name,
        slug=entity.slug.slug if entity.slug is not None else None,
        kinds=kinds,
        template=template.name,
        picture_url=_main_picture_url(sources, request, visibility),
        stats=[
            LinkPreviewStatOut(name=name, value=value)
            for name, value in pick_stats(template, values)
            if not isinstance(value, bool)
        ],
        excerpt=_excerpt(sources, template, visibility),
    )
