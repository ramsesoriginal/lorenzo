from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import Select, select

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
    recursive_descendants_cte,
)
from lorenzo_api.etag import check_if_match
from lorenzo_api.exceptions import (
    InvalidItemPrototypeError,
    ItemInstanceManagementForbiddenError,
    ItemInstanceNotFoundError,
    TenantNotFoundError,
)
from lorenzo_api.information_visibility import resolve_information_visibility
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
    ItemInstanceCreate,
    ItemInstanceOut,
    ItemInstanceUpdate,
    OwnedByResponse,
    OwnedGroupOut,
    SetContainerRequest,
    SetOwnerRequest,
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
    if container_id is not None:
        # Validate container_id belongs to *this* tenant before anything
        # else - a cross-tenant probe must 404 exactly like an unknown id,
        # with no other response difference either.
        await get_entity_or_404(session, container_id, tenant_id)
        stmt = _item_instances_by_container_stmt(tenant_id, container_id, recursive=recursive)
    else:
        stmt = (
            select(VItemInstance)
            .where(VItemInstance.tenant_id == tenant_id)
            .options(*eager_load_options(VItemInstance.entity))
            .order_by(VItemInstance.entity_id)
        )

    # Resolved once per request, not once per row - reused by every item
    # instance on the page (ADR 0028's addendum).
    visibility = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)

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
    stmt = (
        select(VItemInstance, Containment.parent_entity_id)
        .outerjoin(Containment, Containment.child_entity_id == VItemInstance.entity_id)
        .where(
            VItemInstance.owner_entity_id == owner_entity_id,
            VItemInstance.tenant_id == tenant_id,
        )
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

    visibility = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
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


@router.get("/{entity_id}")
async def get_item_instance(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    request: Request,
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
    view = await _get_v_item_instance_or_404(tenant_id, entity_id, session)
    visibility = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    return ItemInstanceOut.from_v_item_instance(view, request, visibility=visibility)


async def _get_v_item_instance_or_404(
    tenant_id: uuid.UUID, entity_id: uuid.UUID, session: SessionDep
) -> VItemInstance:
    stmt = (
        select(VItemInstance)
        .where(VItemInstance.entity_id == entity_id, VItemInstance.tenant_id == tenant_id)
        .options(*eager_load_options(VItemInstance.entity))
    )
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
    session: SessionDep,
    user: CurrentUser,
) -> ItemInstanceOut:
    view = await _get_v_item_instance_or_404(tenant_id, entity_id, session)
    visibility = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
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

    entity = Entity(
        tenant_id=tenant_id,
        name=body.name if body.name is not None else prototype_entity.name,
        created_by=user.id,
        updated_by=user.id,
    )
    session.add(entity)
    await session.flush()
    session.add(ItemInstance(entity_id=entity.id, tenant_id=tenant_id))
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
    return await _item_instance_out(tenant_id, entity.id, request, session, user)


@router.patch("/{entity_id}")
async def update_item_instance(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    body: ItemInstanceUpdate,
    request: Request,
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
    return await _item_instance_out(tenant_id, entity_id, request, session, user)


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


@router.put("/{entity_id}/owner")
async def set_item_instance_owner(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    body: SetOwnerRequest,
    request: Request,
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

    existing = await session.get(Ownership, entity_id)
    if existing is not None:
        existing.owner_character_id = body.owner_character_id
    else:
        session.add(
            Ownership(
                owned_entity_id=entity_id,
                owner_character_id=body.owner_character_id,
                tenant_id=tenant_id,
            )
        )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return await _item_instance_out(tenant_id, entity_id, request, session, user)


@router.delete("/{entity_id}/owner")
async def clear_item_instance_owner(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    request: Request,
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
    return await _item_instance_out(tenant_id, entity_id, request, session, user)


@router.put("/{entity_id}/container")
async def set_item_instance_container(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    body: SetContainerRequest,
    request: Request,
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
    return await _item_instance_out(tenant_id, entity_id, request, session, user)


@router.delete("/{entity_id}/container")
async def clear_item_instance_container(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    request: Request,
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
    return await _item_instance_out(tenant_id, entity_id, request, session, user)
