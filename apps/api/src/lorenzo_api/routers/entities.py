import uuid

from fastapi import APIRouter, Depends, Request, Response
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from lorenzo_api.campaign_access import (
    campaign_ids_for_character,
    can_manage_any_campaign_in_tenant,
    can_manage_any_of_campaigns,
    is_tenant_participant,
)
from lorenzo_api.dependencies import (
    CurrentUser,
    ParamsDep,
    SessionDep,
    get_tenant_or_404,
    set_tenant_rls_context,
)
from lorenzo_api.entity_access import can_self_manage_entity
from lorenzo_api.exceptions import (
    EntityNotFoundError,
    InformationAlreadyExistsError,
    InformationManagementForbiddenError,
    InformationNotFoundError,
    TenantNotFoundError,
)
from lorenzo_api.information_visibility import resolve_information_visibility
from lorenzo_api.models import (
    Entity,
    EntityStat,
    Information,
    Ownership,
    Payload,
    PayloadDescription,
)
from lorenzo_api.schemas.common import EntitySummary
from lorenzo_api.schemas.entities import EntityDetailOut, InformationCreate, InformationOut

# get_tenant_or_404 here, not get_tenant_context (ADR 0038/RFC 0011,
# mirroring routers/item_instances.py's identical ADR 0032/RFC 0005
# precedent): a plain player authoring information about their own
# character's own item needs no tenant-wide Membership row (ADR 0022), so
# gating the whole router on one would lock them out of self-service
# entirely. The two pre-existing GET routes each re-add their own explicit
# is_tenant_participant check instead (see _require_participant), preserving
# their original ADR 0020 behavior - only tenant participants (broader than
# Membership) reach them, same as routers/item_instances.py's identical
# revision. The new POST route uses self-or-managed authorization, narrower
# still.
router = APIRouter(
    prefix="/tenants/{tenant_id}/entities",
    tags=["entities"],
    dependencies=[Depends(get_tenant_or_404)],
)


async def _require_participant(
    session: SessionDep, *, tenant_id: uuid.UUID, user: CurrentUser
) -> None:
    """Gates the two GET routes below - broader than get_tenant_context's
    Membership requirement (a Player or CampaignGm row also qualifies, ADR
    0022), narrower than wide open. Mirrors routers/item_instances.py's
    identical gate (ADR 0032/RFC 0005) - non-enumerable 404, same as
    everywhere else.
    """
    if not await is_tenant_participant(session, tenant_id=tenant_id, user_id=user.id):
        raise TenantNotFoundError(detail=f"No tenant with id {tenant_id}")


@router.get("")
async def list_entities(
    tenant_id: uuid.UUID,
    params: ParamsDep,
    session: SessionDep,
    user: CurrentUser,
) -> Page[EntitySummary]:
    """A lightweight listing - EntitySummary rather than EntityDetailOut, to
    avoid an N+1-heavy response when listing many entities.
    """
    await _require_participant(session, tenant_id=tenant_id, user=user)
    stmt = select(Entity).where(Entity.tenant_id == tenant_id).order_by(Entity.name, Entity.id)
    page: Page[EntitySummary] = await apaginate(session, stmt, params)
    return page


async def get_entity_detail_or_404(
    session: SessionDep, entity_id: uuid.UUID, tenant_id: uuid.UUID
) -> Entity:
    """The full .options() eager-load chain EntityDetailOut needs - factored
    out of get_entity below so routers/entity_stats.py's stat-write endpoint
    (ADR 0037/RFC 0008) can return this same canonical entity-detail shape
    after a write, rather than keeping a second, drifting copy of this
    seven-relationship chain (mirrors routers/items.py's own
    eager_load_options, reused as-is by routers/item_instances.py).

    Not dependencies.get_entity_or_404 - that helper's plain session.get()
    wouldn't have any of these relationships loaded, so reusing it here
    would just mean a second, redundant round trip for this same row. The
    404 check below covers exactly what that helper covers (missing id, or
    an id that belongs to a different tenant).
    """
    stmt = (
        select(Entity)
        .where(Entity.id == entity_id, Entity.tenant_id == tenant_id)
        .options(
            selectinload(Entity.stats).selectinload(EntityStat.stat_definition),
            selectinload(Entity.stat_groups),
            selectinload(Entity.information)
            .selectinload(Information.payloads)
            .selectinload(Payload.description),
            selectinload(Entity.information)
            .selectinload(Information.payloads)
            .selectinload(Payload.number),
            selectinload(Entity.information)
            .selectinload(Information.payloads)
            .selectinload(Payload.picture),
            selectinload(Entity.information)
            .selectinload(Information.payloads)
            .selectinload(Payload.document),
            selectinload(Entity.information).selectinload(Information.knowledge_links),
            selectinload(Entity.prototypes),
            selectinload(Entity.instances),
            selectinload(Entity.parent),
            selectinload(Entity.children),
        )
    )
    entity = await session.scalar(stmt)
    if entity is None:
        raise EntityNotFoundError(detail=f"No entity with id {entity_id} in tenant {tenant_id}")
    return entity


@router.get("/{entity_id}")
async def get_entity(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    user: CurrentUser,
) -> EntityDetailOut:
    """The full detail shape, with every relationship eager-loaded up front."""
    await _require_participant(session, tenant_id=tenant_id, user=user)
    entity = await get_entity_detail_or_404(session, entity_id, tenant_id)
    visibility = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    return EntityDetailOut.from_entity(entity, request, visibility=visibility)


async def authorize_entity_write(
    session: SessionDep, *, tenant_id: uuid.UUID, user: CurrentUser, entity_id: uuid.UUID
) -> None:
    """RFC 0011/ADR 0038's self-or-managed tier for authoring Information/
    Payload on an entity, and for granting/revoking a Knowledge row about
    one (routers/information.py, which imports this directly rather than
    keeping a second copy) - the identical shape routers/entity_stats.py's
    own _authorize_entity_stat_write already established for RFC 0008/ADR
    0037 (self-service if reachable from the caller's own characters;
    otherwise the current Ownership-owner's own campaign(s) need
    can_manage_campaign; an unowned entity falls back to
    can_manage_any_campaign_in_tenant). Duplicated here rather than
    extracted into entity_access.py - this is now the third copy of this
    exact shape (item_instances.py, entity_stats.py, here), a reasonable
    candidate for a future shared `entity_access.can_manage_entity`
    helper, not done speculatively as part of this ADR. Not private (no
    leading underscore), unlike this router's other single-file-scoped
    helpers - matching entity_access.recursive_descendants_cte's own
    precedent for a name genuinely meant to be imported elsewhere.
    """
    if await can_self_manage_entity(
        session, entity_id=entity_id, user_id=user.id, tenant_id=tenant_id
    ):
        return
    owner_stmt = select(Ownership.owner_character_id).where(
        Ownership.owned_entity_id == entity_id, Ownership.tenant_id == tenant_id
    )
    current_owner_id = (await session.execute(owner_stmt)).scalar_one_or_none()
    if current_owner_id is not None:
        campaign_ids = await campaign_ids_for_character(
            session, character_entity_id=current_owner_id, tenant_id=tenant_id
        )
        if campaign_ids and await can_manage_any_of_campaigns(
            session, user_id=user.id, campaign_ids=campaign_ids, tenant_id=tenant_id
        ):
            return
    elif await can_manage_any_campaign_in_tenant(session, user_id=user.id, tenant_id=tenant_id):
        return
    raise InformationManagementForbiddenError(
        detail=f"Not authorized to manage information on entity {entity_id}"
    )


@router.post("/{entity_id}/information", status_code=201)
async def create_information(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    body: InformationCreate,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> InformationOut:
    """One transaction creates Information + Payload + PayloadDescription -
    see ADR 0038/RFC 0011. `entity_id` existence is checked first (404,
    non-enumerable), then self-or-managed authorization (403 - the caller
    already knows the entity exists, they just lack a specific write
    permission over it), then a duplicate `type` for this entity (409,
    Information's own UniqueConstraint(entity_id, type) - pre-checked
    explicitly rather than relying on the constraint violation to surface,
    matching MembershipAlreadyExistsError/PlayerAlreadyExistsError's own
    established precedent, ADR 0036), then the write itself.
    """
    entity_stmt = select(Entity.id).where(Entity.id == entity_id, Entity.tenant_id == tenant_id)
    if (await session.execute(entity_stmt)).first() is None:
        raise EntityNotFoundError(detail=f"No entity with id {entity_id} in tenant {tenant_id}")

    await authorize_entity_write(session, tenant_id=tenant_id, user=user, entity_id=entity_id)

    duplicate_stmt = select(Information.id).where(
        Information.entity_id == entity_id,
        Information.type == body.type,
        Information.tenant_id == tenant_id,
    )
    if (await session.execute(duplicate_stmt)).first() is not None:
        raise InformationAlreadyExistsError(
            detail=f"Entity {entity_id} already has information of type {body.type!r}"
        )

    information = Information(
        tenant_id=tenant_id,
        entity_id=entity_id,
        title=body.title,
        type=body.type,
        is_public=body.is_public,
    )
    session.add(information)
    await session.flush()
    payload = Payload(tenant_id=tenant_id, information_id=information.id)
    session.add(payload)
    await session.flush()
    session.add(
        PayloadDescription(
            payload_id=payload.id, tenant_id=tenant_id, locale=body.locale, content=body.content
        )
    )

    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    response.headers["Location"] = str(
        request.url_for("get_information", tenant_id=tenant_id, information_id=information.id)
    )
    return await information_out_or_404(
        tenant_id, information.id, request, session, user=user, require_visible=False
    )


async def get_information_or_404(
    session: SessionDep, information_id: uuid.UUID, tenant_id: uuid.UUID
) -> Information:
    """The eager-load chain payload_to_schema/InformationOut.from_information
    need - shared by create_information above and routers/information.py's
    own GET/PUT/DELETE, mirroring routers/items.py's eager_load_options
    being imported as-is by item_instances.py.
    """
    stmt = (
        select(Information)
        .where(Information.id == information_id, Information.tenant_id == tenant_id)
        .options(
            selectinload(Information.payloads).selectinload(Payload.description),
            selectinload(Information.payloads).selectinload(Payload.number),
            selectinload(Information.payloads).selectinload(Payload.picture),
            selectinload(Information.payloads).selectinload(Payload.document),
            selectinload(Information.knowledge_links),
        )
    )
    information = (await session.execute(stmt)).scalar_one_or_none()
    if information is None:
        raise InformationNotFoundError(
            detail=f"No information with id {information_id} in tenant {tenant_id}"
        )
    return information


async def information_out_or_404(
    tenant_id: uuid.UUID,
    information_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    *,
    user: CurrentUser,
    require_visible: bool = True,
) -> InformationOut:
    """Loads and wraps one Information row as the canonical response shape
    every write route in this ADR returns (ADR 0032's own "a follow-up GET
    would return the same thing" convention). `require_visible=False` for
    create_information's own immediate post-write read: a freshly-authored,
    non-public row has no Knowledge rows yet for anyone but is_public/orga/
    GM-reachable to match against, so information_visibility.can_see would
    otherwise 404 the caller on the very row they just proved self-or-
    managed authorization over. Every other caller (GET, and
    routers/information.py's own knower PUT/DELETE) keeps the real check -
    a caller who isn't the author and isn't otherwise allowed to see this
    row must not be able to determine its content or existence by poking
    these routes either.
    """
    information = await get_information_or_404(session, information_id, tenant_id)
    if require_visible:
        visibility = await resolve_information_visibility(
            session, user_id=user.id, tenant_id=tenant_id
        )
        if not visibility.can_see(information):
            raise InformationNotFoundError(
                detail=f"No information with id {information_id} in tenant {tenant_id}"
            )
    return InformationOut.from_information(information, request)
