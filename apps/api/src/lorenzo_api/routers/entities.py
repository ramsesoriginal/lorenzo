import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from fastapi_problem.error import ForbiddenProblem
from sqlalchemy import delete, exists, select
from sqlalchemy.orm import selectinload

from lorenzo_api.activity_log import record_activity
from lorenzo_api.campaign_access import (
    campaign_ids_for_character,
    can_manage_any_campaign_in_tenant,
    can_manage_any_of_campaigns,
)
from lorenzo_api.dependencies import (
    CurrentUser,
    ParamsDep,
    SessionDep,
    get_entity_or_404,
    get_tenant_or_404,
    require_tenant_participant,
    set_tenant_rls_context,
)
from lorenzo_api.description_payloads import write_description
from lorenzo_api.entity_access import can_self_manage_entity
from lorenzo_api.exceptions import (
    EntityNotFoundError,
    EntitySlugConflictError,
    EntitySlugManagementForbiddenError,
    EntitySlugNotFoundError,
    InformationAlreadyExistsError,
    InformationManagementForbiddenError,
    InformationNotFoundError,
    InformationOrderConflictError,
)
from lorenzo_api.information_visibility import resolve_information_visibility
from lorenzo_api.models import (
    Being,
    Character,
    Containment,
    Entity,
    EntitySlug,
    Information,
    InformationType,
    Item,
    ItemInstance,
    Ownership,
    Payload,
    VEffectiveStat,
)
from lorenzo_api.schemas.common import EntitySummary
from lorenzo_api.schemas.entities import (
    EntityDetailOut,
    EntityKind,
    EntitySlugOut,
    EntitySlugUpdate,
    InformationCreate,
    InformationOut,
    ResolvedSlugOut,
)

# get_tenant_or_404 here, not get_tenant_context (ADR 0038/RFC 0011,
# mirroring routers/item_instances.py's identical ADR 0032/RFC 0005
# precedent): a plain player authoring information about their own
# character's own item needs no tenant-wide Membership row (ADR 0022), so
# gating the whole router on one would lock them out of self-service
# entirely. The two pre-existing GET routes each re-add their own explicit
# require_tenant_participant check instead, preserving their original ADR
# 0020 behavior - only tenant participants (broader than Membership) reach
# them, same as routers/item_instances.py's identical revision. The new
# POST route uses self-or-managed authorization, narrower still.
router = APIRouter(
    prefix="/tenants/{tenant_id}/entities",
    tags=["entities"],
    dependencies=[Depends(get_tenant_or_404)],
)


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
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
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
            selectinload(Entity.effective_stats).selectinload(VEffectiveStat.stat_definition),
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
            # ADR 0041: Entity.containment/contained_links (the Containment
            # association-object relationships), not Entity.parent/children
            # (the bare Entity lists) - only the former carry the per-edge
            # quantity column EntityDetailOut.parent/quantity/children now
            # need.
            selectinload(Entity.containment).selectinload(Containment.parent),
            selectinload(Entity.contained_links).selectinload(Containment.child),
            selectinload(Entity.slug),
        )
    )
    entity = await session.scalar(stmt)
    if entity is None:
        raise EntityNotFoundError(detail=f"No entity with id {entity_id} in tenant {tenant_id}")
    return entity


async def entity_detail_out(
    session: SessionDep,
    request: Request,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    user: CurrentUser,
) -> EntityDetailOut:
    """What GET /{entity_id} and GET /by-slug/{slug} both return, the caller
    already past require_tenant_participant."""
    entity = await get_entity_detail_or_404(session, entity_id, tenant_id)
    visibility = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    return EntityDetailOut.from_entity(entity, request, visibility=visibility)


# Registered before /{entity_id}: that route's path would otherwise match
# "resolve" and "by-slug" as an entity id (ADR 0043's routing-order note).
_KINDS: tuple[tuple[EntityKind, type[Item | ItemInstance | Being | Character]], ...] = (
    ("item", Item),
    ("item_instance", ItemInstance),
    ("being", Being),
    ("character", Character),
)


@router.get("/resolve")
async def resolve_slugs(
    tenant_id: uuid.UUID,
    slug: Annotated[list[str], Query(min_length=1, max_length=100)],
    session: SessionDep,
    user: CurrentUser,
) -> list[ResolvedSlugOut]:
    """Every slug a LorenzoScript text names, in one request (ADR 0107, RFC
    0027 §7). Same gate as GET /{entity_id}, so a slug resolves for exactly
    the readers who could open its entity. Slugs that don't resolve are
    simply absent: a missing entity and a hidden one look alike.
    """
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    kinds = [exists().where(model.entity_id == Entity.id).label(kind) for kind, model in _KINDS]
    stmt = (
        select(EntitySlug.slug, Entity.id, Entity.name, *kinds)
        .join(Entity, Entity.id == EntitySlug.entity_id)
        .where(EntitySlug.tenant_id == tenant_id, EntitySlug.slug.in_(slug))
    )
    found = {row["slug"]: row for row in (await session.execute(stmt)).mappings()}
    return [
        ResolvedSlugOut(
            slug=name,
            entity_id=row["id"],
            name=row["name"],
            kinds=[kind for kind, _ in _KINDS if row[kind]],
        )
        for name in dict.fromkeys(slug)
        if (row := found.get(name)) is not None
    ]


@router.get("/by-slug/{slug}")
async def get_entity_by_slug(
    tenant_id: uuid.UUID,
    slug: str,
    request: Request,
    session: SessionDep,
    user: CurrentUser,
) -> EntityDetailOut:
    """GET /{entity_id}, addressed by slug (ADR 0107)."""
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    entity_id = await session.scalar(
        select(EntitySlug.entity_id).where(
            EntitySlug.tenant_id == tenant_id, EntitySlug.slug == slug
        )
    )
    if entity_id is None:
        raise EntitySlugNotFoundError(detail=f"No entity with slug {slug!r} in tenant {tenant_id}")
    return await entity_detail_out(
        session, request, tenant_id=tenant_id, entity_id=entity_id, user=user
    )


@router.get("/{entity_id}")
async def get_entity(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    user: CurrentUser,
) -> EntityDetailOut:
    """The full detail shape, with every relationship eager-loaded up front."""
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    return await entity_detail_out(
        session, request, tenant_id=tenant_id, entity_id=entity_id, user=user
    )


@router.put("/{entity_id}/slug")
async def set_entity_slug(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    body: EntitySlugUpdate,
    session: SessionDep,
    user: CurrentUser,
) -> EntitySlugOut:
    """Sets or replaces the entity's one slug (ADR 0107). 404 for an unknown
    entity, then the same self-or-managed tier as authoring its information
    (403), then 409 if another entity in the tenant already has the slug.
    Setting the entity's current slug again changes nothing.
    """
    await get_entity_or_404(session, entity_id, tenant_id)
    await authorize_entity_write(
        session,
        tenant_id=tenant_id,
        user=user,
        entity_id=entity_id,
        forbidden=EntitySlugManagementForbiddenError(
            detail=f"Not authorized to manage the slug of entity {entity_id}"
        ),
    )
    holder = await session.scalar(
        select(EntitySlug.entity_id).where(
            EntitySlug.tenant_id == tenant_id, EntitySlug.slug == body.slug
        )
    )
    if holder is not None and holder != entity_id:
        raise EntitySlugConflictError(
            detail=f"Slug {body.slug!r} is already in use in tenant {tenant_id}"
        )
    current = await session.get(EntitySlug, entity_id)
    if current is None:
        session.add(EntitySlug(entity_id=entity_id, tenant_id=tenant_id, slug=body.slug))
    else:
        current.slug = body.slug
    await session.commit()
    return EntitySlugOut(entity_id=entity_id, slug=body.slug)


@router.delete("/{entity_id}/slug", status_code=204)
async def clear_entity_slug(
    tenant_id: uuid.UUID, entity_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> None:
    """Clears the entity's slug, if it has one (ADR 0107): 204 either way,
    like this API's other idempotent sub-resource DELETEs (ADR 0064)."""
    await get_entity_or_404(session, entity_id, tenant_id)
    await authorize_entity_write(
        session,
        tenant_id=tenant_id,
        user=user,
        entity_id=entity_id,
        forbidden=EntitySlugManagementForbiddenError(
            detail=f"Not authorized to manage the slug of entity {entity_id}"
        ),
    )
    await session.execute(
        delete(EntitySlug).where(
            EntitySlug.entity_id == entity_id, EntitySlug.tenant_id == tenant_id
        )
    )
    await session.commit()


async def authorize_entity_write(
    session: SessionDep,
    *,
    tenant_id: uuid.UUID,
    user: CurrentUser,
    entity_id: uuid.UUID,
    forbidden: ForbiddenProblem | None = None,
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

    `forbidden` is what to raise instead of InformationManagementForbiddenError,
    for a write that isn't about information (an entity's slug, ADR 0107).
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
    raise forbidden or InformationManagementForbiddenError(
        detail=f"Not authorized to manage information on entity {entity_id}"
    )


async def lock_entity_information(
    session: SessionDep, *, entity_id: uuid.UUID, tenant_id: uuid.UUID
) -> None:
    """Row-locks the entity (SELECT ... FOR UPDATE) for the rest of the
    transaction - ADR 0101. Every singleton-type check and `order`
    assignment on an entity's information runs under this lock, so two
    concurrent writers can't both pass a pre-check and then collide on the
    unique index/constraint (a 500 instead of a 409).
    """
    await session.execute(
        select(Entity.id)
        .where(Entity.id == entity_id, Entity.tenant_id == tenant_id)
        .with_for_update()
    )


async def require_singleton_type_free(
    session: SessionDep,
    *,
    entity_id: uuid.UUID,
    tenant_id: uuid.UUID,
    type_: str,
    exclude_information_id: uuid.UUID | None = None,
) -> None:
    """409 if `type_` is a singleton type (information_type.is_singleton,
    ADR 0101) the entity already holds - other types repeat freely.
    `exclude_information_id` is the row being PATCHed, which may keep its
    own type.
    """
    is_singleton = await session.scalar(
        select(InformationType.is_singleton).where(InformationType.name == type_)
    )
    if not is_singleton:
        return
    stmt = select(Information.id).where(
        Information.entity_id == entity_id,
        Information.type == type_,
        Information.tenant_id == tenant_id,
    )
    if exclude_information_id is not None:
        stmt = stmt.where(Information.id != exclude_information_id)
    if (await session.execute(stmt)).first() is not None:
        raise InformationAlreadyExistsError(
            detail=f"Entity {entity_id} already has information of type {type_!r}"
        )


async def require_information_order_free(
    session: SessionDep, *, entity_id: uuid.UUID, tenant_id: uuid.UUID, order: int
) -> None:
    stmt = select(Information.id).where(
        Information.entity_id == entity_id,
        Information.order == order,
        Information.tenant_id == tenant_id,
    )
    if (await session.execute(stmt)).first() is not None:
        raise InformationOrderConflictError(
            detail=f"Entity {entity_id} already has information at position {order}"
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
    permission over it), then - under the entity's row lock (ADR 0101) - a
    duplicate *singleton* `type` (409) and a taken explicit `order` (409),
    pre-checked explicitly rather than relying on the constraint violation
    to surface, matching MembershipAlreadyExistsError/
    PlayerAlreadyExistsError's own established precedent (ADR 0036), then
    the write itself. The description text goes through
    description_payloads.write_description, the one write path for it.
    """
    entity_stmt = select(Entity.id).where(Entity.id == entity_id, Entity.tenant_id == tenant_id)
    if (await session.execute(entity_stmt)).first() is None:
        raise EntityNotFoundError(detail=f"No entity with id {entity_id} in tenant {tenant_id}")

    await authorize_entity_write(session, tenant_id=tenant_id, user=user, entity_id=entity_id)

    await lock_entity_information(session, entity_id=entity_id, tenant_id=tenant_id)
    await require_singleton_type_free(
        session, entity_id=entity_id, tenant_id=tenant_id, type_=body.type
    )
    if body.order is not None:
        await require_information_order_free(
            session, entity_id=entity_id, tenant_id=tenant_id, order=body.order
        )

    information = Information(
        tenant_id=tenant_id,
        entity_id=entity_id,
        title=body.title,
        type=body.type,
        is_public=body.is_public,
        created_by=user.id,
    )
    # Left unset, the database's BEFORE INSERT trigger appends it after the
    # entity's last row (ADR 0101), serialized by the lock taken above. Not
    # passed as order=None: an explicit None would be sent as NULL and not
    # read back from the INSERT's RETURNING.
    if body.order is not None:
        information.order = body.order
    session.add(information)
    await session.flush()
    payload = Payload(tenant_id=tenant_id, information_id=information.id)
    await write_description(session, payload=payload, content=body.content, locale=body.locale)
    # Entity and visibility tier only - never the title, type, or content,
    # since a GM-only secret must not be readable from the activity log
    # (ADR 0084).
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="information.created",
        target_type="information",
        target_id=information.id,
        detail=f"entity={entity_id}, visibility={'public' if body.is_public else 'restricted'}",
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
        # A re-read after a write in the same session must see the stored
        # row (updated_at is set by the database), not the stale identity-
        # map copy expire_on_commit=False leaves behind.
        .execution_options(populate_existing=True)
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


async def authorize_information_edit(
    session: SessionDep, *, tenant_id: uuid.UUID, user: CurrentUser, information: Information
) -> None:
    """ADR 0101's gate for changing an *existing* Information row (PATCH,
    DELETE, its payloads, its knowers). Two parts, in this order:

    1. Sight of the row: information_visibility.can_see, or being its
       `created_by`. Otherwise 404, the same as a missing row - the row's
       existence isn't revealed. Without this, self-or-managed alone would
       let a player publish, delete, or self-grant the GM's secret about
       their own sword. The authorship clause keeps a player able to edit a
       restricted note they wrote, which has no knowers yet.
    2. Standing over the entity it describes: authorize_entity_write, 403.

    `information.knowledge_links` must be loaded (get_information_or_404
    does).
    """
    if information.created_by != user.id:
        visibility = await resolve_information_visibility(
            session, user_id=user.id, tenant_id=tenant_id
        )
        if not visibility.can_see(information):
            raise InformationNotFoundError(
                detail=f"No information with id {information.id} in tenant {tenant_id}"
            )
    await authorize_entity_write(
        session, tenant_id=tenant_id, user=user, entity_id=information.entity_id
    )
