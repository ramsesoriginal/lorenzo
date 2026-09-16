from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from fastapi_problem.error import Problem
from sqlalchemy import ColumnElement, Select, or_, select, true

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
    get_entity_or_404,
    get_tenant_or_404,
    set_tenant_rls_context,
)
from lorenzo_api.entity_access import (
    can_self_manage_entity,
    controlled_character_entity_ids,
    reachable_entity_ids,
    recursive_descendants_cte,
)
from lorenzo_api.etag import check_if_match, etag_for
from lorenzo_api.exceptions import (
    InvalidItemPrototypeError,
    InvalidMergeError,
    InvalidSplitQuantityError,
    ItemInstanceManagementForbiddenError,
    ItemInstanceNotFoundError,
    ItemInstanceSlugConflictError,
    ItemInstanceSlugNotFoundError,
    TenantNotFoundError,
)
from lorenzo_api.information_visibility import InformationVisibility, resolve_information_visibility
from lorenzo_api.models import (
    Containment,
    Entity,
    EntityPrototype,
    Item,
    ItemInstance,
    Ownership,
    VItemInstance,
)
from lorenzo_api.routers.items import eager_load_options
from lorenzo_api.schemas.common import EntitySummary
from lorenzo_api.schemas.items import (
    BulkAssignItem,
    BulkAssignResultItem,
    ItemInstanceCreate,
    ItemInstanceOut,
    ItemInstanceUpdate,
    MergeItemInstanceRequest,
    OwnedByResponse,
    OwnedGroupOut,
    ProblemOut,
    SetContainerRequest,
    SetOwnerRequest,
    SplitItemInstanceRequest,
)

# get_tenant_or_404 here, not get_tenant_context (ADR 0032/RFC 0005,
# mirroring routers/campaigns.py's identical ADR 0030/RFC 0003 precedent):
# neither an ordinary player nor a campaign's own GM implies a tenant-wide
# Membership row (ADR 0022), so gating this whole router on one would lock
# them out of their own inventory entirely. The three GET routes below each
# apply their own explicit is_tenant_participant check instead; the write
# routes use self-or-managed authorization, narrower still.
router = APIRouter(
    prefix="/tenants/{tenant_id}/item-instances",
    tags=["item-instances"],
    dependencies=[Depends(get_tenant_or_404)],
)


def _item_instances_by_container_stmt(
    tenant_id: uuid.UUID, container_id: uuid.UUID, *, recursive: bool
) -> Select[Any]:
    if not recursive:
        # Direct children only.
        return (
            select(VItemInstance)
            .join(Containment, Containment.child_entity_id == VItemInstance.entity_id)
            .where(
                Containment.parent_entity_id == container_id,
                Containment.tenant_id == tenant_id,
                VItemInstance.tenant_id == tenant_id,
            )
            .options(*eager_load_options(VItemInstance.entity))
            .order_by(VItemInstance.entity_id)
        )

    # Generalized, shared version (entity_access.py) - RFC 0005's own
    # flagged follow-up: moved there so this router's own container-filtered
    # listing and RFC 0005/0009's reachability walks share one
    # implementation, not two independent copies of the identical
    # containment traversal.
    cte = recursive_descendants_cte(frozenset({container_id}), tenant_id)
    return (
        select(VItemInstance)
        .select_from(cte.join(VItemInstance, VItemInstance.entity_id == cte.c.child_entity_id))
        .where(VItemInstance.tenant_id == tenant_id)
        .options(*eager_load_options(VItemInstance.entity))
        .order_by(VItemInstance.entity_id)
    )


async def _require_participant(
    session: SessionDep, *, tenant_id: uuid.UUID, user: CurrentUser
) -> None:
    """Gates every GET route below - broader than get_tenant_context's
    Membership requirement (a Player or CampaignGm row also qualifies,
    ADR 0022), narrower than wide open (an unrelated authenticated user
    with zero standing in this tenant still can't browse its inventory).
    Mirrors routers/campaigns.py's identical is_tenant_participant gate
    (ADR 0030/RFC 0003) - non-enumerable 404, same as everywhere else.
    """
    if not await is_tenant_participant(session, tenant_id=tenant_id, user_id=user.id):
        raise TenantNotFoundError(detail=f"No tenant with id {tenant_id}")


async def _visible_owner_predicate(
    session: SessionDep,
    *,
    tenant_id: uuid.UUID,
    user: CurrentUser,
    visibility: InformationVisibility,
) -> ColumnElement[bool]:
    """ADR 0040: narrows which *owned* item instances a read route may
    return to whoever can reach the owner - self (the caller's own
    characters, the identical entity_access.reachable_entity_ids shape
    RFC 0005's self-or-managed write authorization already uses),
    GM (visibility.gm_reachable_entity_ids, already resolved once per
    request by every caller of this function), or is_orga.

    Deliberately visibility.is_orga, not campaign_access.is_tenant_admin -
    whether an admin can see that a character owns a hidden item is read
    as a narrative-knowledge question, not an administrative-capability
    one, mirroring RFC 0009's "administrative access != automatic
    character/GM knowledge" principle. is_orga already carries the correct
    per-tenant TenantAdminCampaignOptOut suppression for exactly this
    reason - reused as-is rather than re-derived.

    Ownerless instances are never filtered by this at all (the OR's first
    branch, unconditional) - only instances a character actually owns
    narrow. Not used by _get_v_item_instance_or_404's own default (no
    predicate) path, which the post-write response builders below still
    rely on - a write is already independently authorized via
    _authorize_instance_write/_authorize_create_instance before this
    would ever run, and those checks (can_manage_campaign, in particular)
    are not a subset of this read predicate - a plain tenant OWNER managing
    someone else's item via can_manage_any_of_campaigns, without holding
    ORGA, would otherwise 404 on the very write they just made.
    """
    if visibility.is_orga:
        return true()
    self_reachable = await reachable_entity_ids(
        session,
        root_entity_ids=await controlled_character_entity_ids(
            session, user_id=user.id, tenant_id=tenant_id
        ),
        tenant_id=tenant_id,
    )
    visible_entity_ids = self_reachable | visibility.gm_reachable_entity_ids
    return or_(
        VItemInstance.owner_entity_id.is_(None),
        VItemInstance.entity_id.in_(visible_entity_ids),
    )


@router.get("")
async def list_item_instances(
    tenant_id: uuid.UUID,
    request: Request,
    params: ParamsDep,
    session: SessionDep,
    user: CurrentUser,
    container_id: Annotated[
        uuid.UUID | None,
        Query(description="Only return item instances contained in this entity."),
    ] = None,
    recursive: Annotated[
        bool,
        Query(
            description=(
                "With container_id, also include instances nested arbitrarily deep "
                "inside it, not just its direct contents."
            )
        ),
    ] = False,
) -> Page[ItemInstanceOut]:
    """Every item instance for this tenant, optionally filtered to one
    container's contents (?container_id=&recursive=). `recursive` defaults
    to false - the costlier, cycle-risk-bearing traversal is explicit
    opt-in, not the default (ADR 0020 / task brief) - consistent with
    owned-by-grouped below also being non-recursive by design. Filtering by
    container is an ordinary query-param filter on this same list, unlike
    the structurally-different owned-by grouping, which is its own
    endpoint (ADR 0020).
    """
    await _require_participant(session, tenant_id=tenant_id, user=user)
    # Resolved once per request, not once per row - reused by every item
    # instance on the page (ADR 0028's addendum), and now also by
    # _visible_owner_predicate below (ADR 0040) rather than a second query.
    visibility = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    predicate = await _visible_owner_predicate(
        session, tenant_id=tenant_id, user=user, visibility=visibility
    )
    if container_id is not None:
        # Validate container_id belongs to *this* tenant before anything
        # else - a cross-tenant probe must 404 exactly like an unknown id,
        # with no other response difference either.
        await get_entity_or_404(session, container_id, tenant_id)
        stmt = _item_instances_by_container_stmt(
            tenant_id, container_id, recursive=recursive
        ).where(predicate)
    else:
        stmt = (
            select(VItemInstance)
            .where(VItemInstance.tenant_id == tenant_id)
            .where(predicate)
            .options(*eager_load_options(VItemInstance.entity))
            .order_by(VItemInstance.entity_id)
        )

    def _item_instances_out(items: Sequence[VItemInstance]) -> list[ItemInstanceOut]:
        return [
            ItemInstanceOut.from_v_item_instance(item, request, visibility=visibility)
            for item in items
        ]

    # apaginate is typed to return Any (fastapi_pagination's own signature) -
    # cast rather than suppress, the declared return type is otherwise
    # exact.
    return cast(
        Page[ItemInstanceOut],
        await apaginate(session, stmt, params, transformer=_item_instances_out),
    )


@router.get("/owned-by/{owner_entity_id}")
async def list_item_instances_owned_by(
    tenant_id: uuid.UUID,
    owner_entity_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    user: CurrentUser,
) -> OwnedByResponse:
    """Every item instance owned by owner_entity_id, grouped by *direct*
    container only (a None group for uncontained instances) - a one-level
    grouping, not a recursive container-tree walk. Deliberately not
    paginated - bounded by one owner's inventory (ADR 0020 / task brief).
    """
    await _require_participant(session, tenant_id=tenant_id, user=user)
    # ADR 0040: an owner_entity_id the caller can't reach (not one of their
    # own characters, not GM-reachable, not is_orga) contributes zero rows
    # below - the response comes back as an empty groups list, identical in
    # shape to "this character owns nothing." No separate existence check
    # needed, and no way to distinguish "doesn't exist" from "hidden from
    # you" from the response alone.
    visibility = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    predicate = await _visible_owner_predicate(
        session, tenant_id=tenant_id, user=user, visibility=visibility
    )
    stmt = (
        select(VItemInstance, Containment.parent_entity_id)
        .outerjoin(Containment, Containment.child_entity_id == VItemInstance.entity_id)
        .where(
            VItemInstance.owner_entity_id == owner_entity_id,
            VItemInstance.tenant_id == tenant_id,
        )
        .where(predicate)
        .options(*eager_load_options(VItemInstance.entity))
        .order_by(Containment.parent_entity_id, VItemInstance.entity_id)
    )
    rows = (await session.execute(stmt)).all()

    container_ids = {container_id for _, container_id in rows if container_id is not None}
    containers: dict[uuid.UUID, Entity] = {}
    if container_ids:
        container_entities = (
            await session.execute(
                select(Entity).where(Entity.id.in_(container_ids), Entity.tenant_id == tenant_id)
            )
        ).scalars()
        containers = {entity.id: entity for entity in container_entities}

    groups: dict[uuid.UUID | None, list[ItemInstanceOut]] = {}
    for view, container_id in rows:
        groups.setdefault(container_id, []).append(
            ItemInstanceOut.from_v_item_instance(view, request, visibility=visibility)
        )

    return OwnedByResponse(
        groups=[
            OwnedGroupOut(
                container=(
                    EntitySummary.from_entity(containers[container_id])
                    if container_id is not None
                    else None
                ),
                item_instances=instances,
            )
            for container_id, instances in groups.items()
        ]
    )


@router.get("/by-slug/{slug}")
async def get_item_instance_by_slug(
    tenant_id: uuid.UUID,
    slug: str,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> ItemInstanceOut:
    """ADR 0043. Registered *before* /{entity_id} below, for the identical
    routing-order reason that route's own docstring already documents for
    /owned-by/{owner_entity_id} - a wildcard entity_id segment registered
    first would otherwise greedily match "by-slug" as an id and shadow this
    route entirely.

    Applies the same ADR 0040 read-visibility predicate as GET
    /{entity_id} - a slug is just an alternate way to name an instance, not
    a separate, unfiltered lookup path into someone else's hidden
    inventory.
    """
    await _require_participant(session, tenant_id=tenant_id, user=user)
    visibility = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    predicate = await _visible_owner_predicate(
        session, tenant_id=tenant_id, user=user, visibility=visibility
    )
    stmt = (
        select(VItemInstance)
        .where(
            VItemInstance.tenant_id == tenant_id,
            VItemInstance.slug == slug,
            predicate,
        )
        .options(*eager_load_options(VItemInstance.entity))
    )
    view = (await session.execute(stmt)).scalar_one_or_none()
    if view is None:
        raise ItemInstanceSlugNotFoundError(
            detail=f"No item instance with slug {slug!r} in tenant {tenant_id}"
        )
    response.headers["ETag"] = etag_for(view.entity.updated_at)
    return ItemInstanceOut.from_v_item_instance(view, request, visibility=visibility)


@router.get("/{entity_id}")
async def get_item_instance(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> ItemInstanceOut:
    """Not in the original task brief, added for REST symmetry with
    GET /items/{entity_id} - a resource with a list and filtered views but
    no direct single-item lookup by id would be a real gap.

    Registered *after* /owned-by/{owner_entity_id} above - FastAPI/Starlette
    matches routes in registration order, and a wildcard path segment here
    would otherwise greedily match "owned-by" as an entity_id and shadow
    that route entirely. Confirmed empirically (not just reasoned through)
    that getting this order backwards really does break /owned-by/... with
    a 422, not just in theory.
    """
    await _require_participant(session, tenant_id=tenant_id, user=user)
    visibility = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    # ADR 0040: an item instance the caller can't reach 404s here, the same
    # "no row matched" path an unknown or cross-tenant id already takes -
    # existence hidden, not a redacted 200. _item_instance_out below (used
    # only after an already-independently-authorized write) deliberately
    # does not pass this predicate - see _visible_owner_predicate's own
    # docstring for why that would be a real bug, not just a redundant
    # extra check.
    predicate = await _visible_owner_predicate(
        session, tenant_id=tenant_id, user=user, visibility=visibility
    )
    view = await _get_v_item_instance_or_404(
        tenant_id, entity_id, session, extra_predicate=predicate
    )
    response.headers["ETag"] = etag_for(view.entity.updated_at)
    return ItemInstanceOut.from_v_item_instance(view, request, visibility=visibility)


async def _get_v_item_instance_or_404(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    session: SessionDep,
    *,
    extra_predicate: ColumnElement[bool] | None = None,
) -> VItemInstance:
    stmt = (
        select(VItemInstance)
        .where(VItemInstance.entity_id == entity_id, VItemInstance.tenant_id == tenant_id)
        .options(*eager_load_options(VItemInstance.entity))
    )
    if extra_predicate is not None:
        stmt = stmt.where(extra_predicate)
    view = (await session.execute(stmt)).scalar_one_or_none()
    if view is None:
        raise ItemInstanceNotFoundError(
            detail=f"No item instance with id {entity_id} in tenant {tenant_id}"
        )
    return view


async def _get_item_instance_entity_or_404(
    tenant_id: uuid.UUID, entity_id: uuid.UUID, session: SessionDep
) -> Entity:
    """Loads the writable Entity row for a known item instance - PATCH/
    DELETE/the owner+container actions act on Entity/Ownership/Containment
    directly, mirroring routers/items.py's own view-for-reads/table-for-
    writes split.
    """
    stmt = (
        select(Entity)
        .join(ItemInstance, ItemInstance.entity_id == Entity.id)
        .where(Entity.id == entity_id, Entity.tenant_id == tenant_id)
    )
    entity = (await session.execute(stmt)).scalar_one_or_none()
    if entity is None:
        raise ItemInstanceNotFoundError(
            detail=f"No item instance with id {entity_id} in tenant {tenant_id}"
        )
    return entity


async def _item_instance_out(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    request: Request,
    response: Response | None,
    session: SessionDep,
    user: CurrentUser,
) -> ItemInstanceOut:
    """response is None only for bulk-assign's per-item results (ADR 0044) -
    a batch response representing N resources has no single ETag of its
    own to set, unlike every single-item route that calls this.
    """
    view = await _get_v_item_instance_or_404(tenant_id, entity_id, session)
    visibility = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    if response is not None:
        response.headers["ETag"] = etag_for(view.entity.updated_at)
    return ItemInstanceOut.from_v_item_instance(view, request, visibility=visibility)


async def _current_owner_character_id(
    session: SessionDep, *, entity_id: uuid.UUID, tenant_id: uuid.UUID
) -> uuid.UUID | None:
    stmt = select(Ownership.owner_character_id).where(
        Ownership.owned_entity_id == entity_id, Ownership.tenant_id == tenant_id
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def _authorize_create_instance(
    session: SessionDep,
    *,
    tenant_id: uuid.UUID,
    user: CurrentUser,
    owner_character_id: uuid.UUID | None,
) -> None:
    """RFC 0005's instantiate authorization: self-service if
    owner_character_id resolves to one of the caller's own characters (no
    existing entity to walk reachability from yet, unlike an existing
    instance - checked directly against controlled_character_entity_ids
    instead); otherwise can_manage_campaign on any one of that character's
    campaigns; ownerless creation falls back to can_manage_campaign on any
    campaign in the tenant.
    """
    if owner_character_id is not None:
        controlled = await controlled_character_entity_ids(
            session, user_id=user.id, tenant_id=tenant_id
        )
        if owner_character_id in controlled:
            return
        campaign_ids = await campaign_ids_for_character(
            session, character_entity_id=owner_character_id, tenant_id=tenant_id
        )
        if campaign_ids and await can_manage_any_of_campaigns(
            session, user_id=user.id, campaign_ids=campaign_ids, tenant_id=tenant_id
        ):
            return
    elif await can_manage_any_campaign_in_tenant(session, user_id=user.id, tenant_id=tenant_id):
        return
    raise ItemInstanceManagementForbiddenError(
        detail="Not authorized to create an item instance for that owner"
    )


async def _authorize_instance_write(
    session: SessionDep, *, tenant_id: uuid.UUID, user: CurrentUser, entity_id: uuid.UUID
) -> None:
    """RFC 0005's self-or-managed check for PATCH/DELETE/the owner and
    container actions on an *existing* instance - checked against its
    current state before the write, uniformly regardless of what the write
    itself changes (moving your own sword, or giving it to someone else's
    character, is equally self-service as long as you already control it
    now).
    """
    if await can_self_manage_entity(
        session, entity_id=entity_id, user_id=user.id, tenant_id=tenant_id
    ):
        return
    current_owner_id = await _current_owner_character_id(
        session, entity_id=entity_id, tenant_id=tenant_id
    )
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
    raise ItemInstanceManagementForbiddenError(
        detail=f"Not authorized to manage item instance {entity_id}"
    )


@router.post("", status_code=201)
async def create_item_instance(
    tenant_id: uuid.UUID,
    body: ItemInstanceCreate,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> ItemInstanceOut:
    proto_stmt = (
        select(Entity)
        .join(Item, Item.entity_id == Entity.id)
        .where(Entity.id == body.prototype_id, Entity.tenant_id == tenant_id)
    )
    prototype_entity = (await session.execute(proto_stmt)).scalar_one_or_none()
    if prototype_entity is None:
        raise InvalidItemPrototypeError(
            detail=f"{body.prototype_id} is not a base item in tenant {tenant_id}"
        )

    await _authorize_create_instance(
        session, tenant_id=tenant_id, user=user, owner_character_id=body.owner_character_id
    )

    if body.slug is not None:
        slug_stmt = select(ItemInstance.entity_id).where(
            ItemInstance.tenant_id == tenant_id, ItemInstance.slug == body.slug
        )
        if (await session.execute(slug_stmt)).first() is not None:
            raise ItemInstanceSlugConflictError(
                detail=f"Slug {body.slug!r} is already in use in tenant {tenant_id}"
            )

    entity = Entity(
        tenant_id=tenant_id,
        name=body.name if body.name is not None else prototype_entity.name,
        created_by=user.id,
        updated_by=user.id,
    )
    session.add(entity)
    await session.flush()
    session.add(ItemInstance(entity_id=entity.id, tenant_id=tenant_id, slug=body.slug))
    session.add(
        EntityPrototype(entity_id=entity.id, prototype_id=body.prototype_id, tenant_id=tenant_id)
    )
    if body.owner_character_id is not None:
        session.add(
            Ownership(
                owned_entity_id=entity.id,
                owner_character_id=body.owner_character_id,
                tenant_id=tenant_id,
            )
        )
    if body.container_entity_id is not None:
        session.add(
            Containment(
                child_entity_id=entity.id,
                parent_entity_id=body.container_entity_id,
                tenant_id=tenant_id,
            )
        )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    response.headers["Location"] = str(
        request.url_for("get_item_instance", tenant_id=tenant_id, entity_id=entity.id)
    )
    return await _item_instance_out(tenant_id, entity.id, request, response, session, user)


@router.patch("/{entity_id}")
async def update_item_instance(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    body: ItemInstanceUpdate,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> ItemInstanceOut:
    entity = await _get_item_instance_entity_or_404(tenant_id, entity_id, session)
    check_if_match(if_match, updated_at=entity.updated_at)
    await _authorize_instance_write(session, tenant_id=tenant_id, user=user, entity_id=entity_id)
    update = body.model_dump(exclude_unset=True)
    if "name" in update:
        entity.name = update["name"]
        entity.updated_by = user.id
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return await _item_instance_out(tenant_id, entity_id, request, response, session, user)


@router.delete("/{entity_id}", status_code=204)
async def delete_item_instance(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> None:
    """Plain cascade delete, no guard - an instance has nothing else
    depending on it the way a base item does (ADR 0018's default cascade
    is exactly right here, unmodified).
    """
    entity = await _get_item_instance_entity_or_404(tenant_id, entity_id, session)
    check_if_match(if_match, updated_at=entity.updated_at)
    await _authorize_instance_write(session, tenant_id=tenant_id, user=user, entity_id=entity_id)
    await session.delete(entity)
    await session.commit()


async def _perform_set_owner(
    session: SessionDep,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    owner_character_id: uuid.UUID,
) -> None:
    """Core owner-set mechanics only - no auth, no If-Match, no response
    shaping, no commit - shared by the single-item PUT .../owner route and
    bulk-assign's own quantity-omitted branch (ADR 0044), so the two can't
    drift.
    """
    existing = await session.get(Ownership, entity_id)
    if existing is not None:
        existing.owner_character_id = owner_character_id
    else:
        session.add(
            Ownership(
                owned_entity_id=entity_id,
                owner_character_id=owner_character_id,
                tenant_id=tenant_id,
            )
        )


@router.put("/{entity_id}/owner")
async def set_item_instance_owner(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    body: SetOwnerRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> ItemInstanceOut:
    """Owner as a singular sub-resource, not an RPC verb - PUT replaces the
    relationship (ownership already enforces at most one owner per entity
    at the schema level, ADR 0025), giving "transfer to a new owner" and
    "set an owner for the first time" the same call shape.
    """
    entity = await _get_item_instance_entity_or_404(tenant_id, entity_id, session)
    check_if_match(if_match, updated_at=entity.updated_at)
    await _authorize_instance_write(session, tenant_id=tenant_id, user=user, entity_id=entity_id)

    await _perform_set_owner(
        session,
        tenant_id=tenant_id,
        entity_id=entity_id,
        owner_character_id=body.owner_character_id,
    )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return await _item_instance_out(tenant_id, entity_id, request, response, session, user)


@router.delete("/{entity_id}/owner")
async def clear_item_instance_owner(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> ItemInstanceOut:
    """200 + the parent resource, not 204 - deleting a *singular sub-
    resource* leaves the parent itself intact, and returning nothing would
    just force an immediate follow-up GET (ADR 0032/RFC 0005).
    """
    entity = await _get_item_instance_entity_or_404(tenant_id, entity_id, session)
    check_if_match(if_match, updated_at=entity.updated_at)
    await _authorize_instance_write(session, tenant_id=tenant_id, user=user, entity_id=entity_id)

    existing = await session.get(Ownership, entity_id)
    if existing is not None:
        await session.delete(existing)
        await session.commit()
        await set_tenant_rls_context(session, tenant_id)
    return await _item_instance_out(tenant_id, entity_id, request, response, session, user)


@router.put("/{entity_id}/container")
async def set_item_instance_container(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    body: SetContainerRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> ItemInstanceOut:
    """No cycle check - ADR 0016 deliberately allows containment cycles
    ("game worlds can be legitimately non-Euclidean"), and this API layer
    doesn't second-guess that by rejecting what the schema was explicitly
    built to allow.
    """
    entity = await _get_item_instance_entity_or_404(tenant_id, entity_id, session)
    check_if_match(if_match, updated_at=entity.updated_at)
    await _authorize_instance_write(session, tenant_id=tenant_id, user=user, entity_id=entity_id)

    existing = await session.get(Containment, entity_id)
    if existing is not None:
        existing.parent_entity_id = body.container_entity_id
    else:
        session.add(
            Containment(
                child_entity_id=entity_id,
                parent_entity_id=body.container_entity_id,
                tenant_id=tenant_id,
            )
        )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return await _item_instance_out(tenant_id, entity_id, request, response, session, user)


@router.delete("/{entity_id}/container")
async def clear_item_instance_container(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> ItemInstanceOut:
    entity = await _get_item_instance_entity_or_404(tenant_id, entity_id, session)
    check_if_match(if_match, updated_at=entity.updated_at)
    await _authorize_instance_write(session, tenant_id=tenant_id, user=user, entity_id=entity_id)

    existing = await session.get(Containment, entity_id)
    if existing is not None:
        await session.delete(existing)
        await session.commit()
        await set_tenant_rls_context(session, tenant_id)
    return await _item_instance_out(tenant_id, entity_id, request, response, session, user)


async def _perform_split(
    session: SessionDep,
    *,
    tenant_id: uuid.UUID,
    entity: Entity,
    quantity: int,
    owner_character_id: uuid.UUID | None,
    user: CurrentUser,
) -> uuid.UUID:
    """Core split mechanics only - no auth, no If-Match, no response
    shaping, no commit - shared by the single-item POST .../split route and
    bulk-assign's own quantity-given branch (ADR 0044), so the two can't
    drift. Returns the new (split-off) instance's entity_id.

    Splits `quantity` units off entity's current stack into a new sibling
    instance at the same container, decrementing the source's own
    Containment.quantity by that amount - see ADR 0041. The new instance
    copies the source's own direct EntityPrototype link(s) - it's a fresh
    instance of the same prototype(s), created the same way
    POST /item-instances creates one, not a deep clone of the source's own
    accumulated entity_stat overrides, Information, or attribution trail.
    `owner_character_id` (ADR 0044): the new instance's owner if given,
    else the source's own current owner (ADR 0041's original behavior).
    """
    entity_id = entity.id
    source_containment = await session.get(Containment, entity_id)
    if source_containment is None or quantity >= source_containment.quantity:
        current = source_containment.quantity if source_containment is not None else None
        raise InvalidSplitQuantityError(
            detail=(
                f"Cannot split {quantity} unit(s) off item instance {entity_id} "
                f"(current stack quantity: {current})"
            )
        )

    prototype_ids = (
        (
            await session.execute(
                select(EntityPrototype.prototype_id).where(
                    EntityPrototype.entity_id == entity_id, EntityPrototype.tenant_id == tenant_id
                )
            )
        )
        .scalars()
        .all()
    )
    new_owner_id: uuid.UUID | None
    if owner_character_id is not None:
        new_owner_id = owner_character_id
    else:
        new_owner_id = await _current_owner_character_id(
            session, entity_id=entity_id, tenant_id=tenant_id
        )

    new_entity = Entity(
        tenant_id=tenant_id, name=entity.name, created_by=user.id, updated_by=user.id
    )
    session.add(new_entity)
    await session.flush()
    session.add(ItemInstance(entity_id=new_entity.id, tenant_id=tenant_id))
    for prototype_id in prototype_ids:
        session.add(
            EntityPrototype(entity_id=new_entity.id, prototype_id=prototype_id, tenant_id=tenant_id)
        )
    if new_owner_id is not None:
        session.add(
            Ownership(
                owned_entity_id=new_entity.id, owner_character_id=new_owner_id, tenant_id=tenant_id
            )
        )
    session.add(
        Containment(
            child_entity_id=new_entity.id,
            parent_entity_id=source_containment.parent_entity_id,
            tenant_id=tenant_id,
            quantity=quantity,
        )
    )
    source_containment.quantity -= quantity
    return new_entity.id


@router.post("/{entity_id}/split", status_code=201)
async def split_item_instance(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    body: SplitItemInstanceRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> ItemInstanceOut:
    """Self-or-managed authorization against the *source* entity
    (_authorize_instance_write, unchanged) - splitting your own stack is
    acting on your own stuff, the same tier every other instance write
    already uses. See _perform_split for the actual mechanics.

    201 + Location + the *new* instance's canonical shape, mirroring
    POST /item-instances's own convention - a caller that wants the
    source's own new (decremented) quantity re-GETs it, same as any other
    write's side effects on a different resource.
    """
    entity = await _get_item_instance_entity_or_404(tenant_id, entity_id, session)
    check_if_match(if_match, updated_at=entity.updated_at)
    await _authorize_instance_write(session, tenant_id=tenant_id, user=user, entity_id=entity_id)

    new_entity_id = await _perform_split(
        session,
        tenant_id=tenant_id,
        entity=entity,
        quantity=body.quantity,
        owner_character_id=body.owner_character_id,
        user=user,
    )

    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    response.headers["Location"] = str(
        request.url_for("get_item_instance", tenant_id=tenant_id, entity_id=new_entity_id)
    )
    return await _item_instance_out(tenant_id, new_entity_id, request, response, session, user)


@router.post("/{entity_id}/merge")
async def merge_item_instance(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    body: MergeItemInstanceRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> ItemInstanceOut:
    """The inverse of split (ADR 0044): entity_id's entire current stack is
    added onto into_entity_id's, then entity_id is deleted. Authorized
    against *both* sides (_authorize_instance_write) - this mutates both
    rows, unlike every other write in this router, which only ever touches
    one. If-Match (optional, as everywhere) is checked against the source
    (entity_id) only, mirroring split's own single-sided precondition.

    200 + the *target*'s resulting shape, not 201 - nothing new is created
    here, unlike split.
    """
    if entity_id == body.into_entity_id:
        raise InvalidMergeError(detail="Cannot merge an item instance into itself")

    source_entity = await _get_item_instance_entity_or_404(tenant_id, entity_id, session)
    check_if_match(if_match, updated_at=source_entity.updated_at)
    await _authorize_instance_write(session, tenant_id=tenant_id, user=user, entity_id=entity_id)
    # Also 404s (via the identical tenant-scoped lookup every other route
    # here uses) if into_entity_id doesn't resolve to an item instance in
    # this tenant at all.
    await _get_item_instance_entity_or_404(tenant_id, body.into_entity_id, session)
    await _authorize_instance_write(
        session, tenant_id=tenant_id, user=user, entity_id=body.into_entity_id
    )

    source_containment = await session.get(Containment, entity_id)
    target_containment = await session.get(Containment, body.into_entity_id)
    if source_containment is None or target_containment is None:
        raise InvalidMergeError(
            detail="Both item instances must currently be contained somewhere to merge"
        )
    if source_containment.parent_entity_id != target_containment.parent_entity_id:
        raise InvalidMergeError(detail="Cannot merge item instances in different containers")

    source_owner_id = await _current_owner_character_id(
        session, entity_id=entity_id, tenant_id=tenant_id
    )
    target_owner_id = await _current_owner_character_id(
        session, entity_id=body.into_entity_id, tenant_id=tenant_id
    )
    if source_owner_id != target_owner_id:
        raise InvalidMergeError(detail="Cannot merge item instances with different owners")

    target_containment.quantity += source_containment.quantity
    await session.delete(source_entity)

    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return await _item_instance_out(
        tenant_id, body.into_entity_id, request, response, session, user
    )


@router.post("/bulk-assign")
async def bulk_assign_item_instances(
    tenant_id: uuid.UUID,
    body: list[BulkAssignItem],
    request: Request,
    session: SessionDep,
    user: CurrentUser,
) -> list[BulkAssignResultItem]:
    """Assigns several already-decided items to characters in one call
    (ADR 0044) - a GM's own "resolve a whole loot session" step. quantity
    given delegates to split-with-owner (_perform_split); omitted
    delegates to the plain owner-PUT path (_perform_set_owner) -both share
    exactly the mechanics (and, for split, the authorization) the
    single-item routes above use.

    Never all-or-nothing: each item runs inside its own session.
    begin_nested() (a SQL SAVEPOINT) so one item's failure rolls back only
    that item, not the others sharing this request's session/transaction -
    a caught fastapi_problem.error.Problem (404/403/412/422) becomes that
    item's own "error" entry (via the identical .marshal() shape a real
    single-item error response would have), everything else already
    applied by earlier items in the batch proceeds to the one shared
    commit at the end. An unexpected (non-Problem) exception is not caught
    here and fails the whole request as a 500 - this only ever gracefully
    handles anticipated, typed failure modes, matching this codebase's
    general practice.
    """
    results: list[BulkAssignResultItem] = []
    for item in body:
        try:
            async with session.begin_nested():
                entity = await _get_item_instance_entity_or_404(tenant_id, item.entity_id, session)
                check_if_match(item.if_match, updated_at=entity.updated_at)
                await _authorize_instance_write(
                    session, tenant_id=tenant_id, user=user, entity_id=item.entity_id
                )
                if item.quantity is not None:
                    result_entity_id = await _perform_split(
                        session,
                        tenant_id=tenant_id,
                        entity=entity,
                        quantity=item.quantity,
                        owner_character_id=item.owner_character_id,
                        user=user,
                    )
                else:
                    await _perform_set_owner(
                        session,
                        tenant_id=tenant_id,
                        entity_id=item.entity_id,
                        owner_character_id=item.owner_character_id,
                    )
                    result_entity_id = item.entity_id
        except Problem as exc:
            results.append(
                BulkAssignResultItem(
                    entity_id=item.entity_id,
                    status="error",
                    item_instance=None,
                    problem=ProblemOut(**exc.marshal()),
                )
            )
            continue
        item_instance = await _item_instance_out(
            tenant_id, result_entity_id, request, None, session, user
        )
        results.append(
            BulkAssignResultItem(
                entity_id=item.entity_id, status="ok", item_instance=item_instance, problem=None
            )
        )

    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return results
