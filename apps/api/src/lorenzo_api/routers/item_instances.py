from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Query, Request
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import CTE, Select, any_, func, select
from sqlalchemy.dialects.postgresql import array as pg_array

from lorenzo_api.dependencies import (
    CurrentUser,
    ParamsDep,
    SessionDep,
    get_entity_or_404,
    get_tenant_context,
)
from lorenzo_api.exceptions import ItemInstanceNotFoundError
from lorenzo_api.information_visibility import resolve_information_visibility
from lorenzo_api.models import Containment, Entity, VItemInstance
from lorenzo_api.routers.items import eager_load_options
from lorenzo_api.schemas.common import EntitySummary
from lorenzo_api.schemas.items import ItemInstanceOut, OwnedByResponse, OwnedGroupOut

# get_tenant_context here, not per-route (ADR 0020's revised guidance) -
# every route on this router needs it and none read its return value, the
# textbook case FastAPI's own docs give for a router-level dependency.
router = APIRouter(
    prefix="/tenants/{tenant_id}/item-instances",
    tags=["item-instances"],
    dependencies=[Depends(get_tenant_context)],
)

# Bounds the cost of a recursive container traversal on a legitimately deep
# (but acyclic) containment tree. Orthogonal to the path-array cycle guard
# in _recursive_descendants_cte below - that guard handles actual cycles,
# this handles a merely-deep tree; see ADR 0016 and the task brief for why
# both are kept rather than relying on just one.
_MAX_CONTAINMENT_DEPTH = 50


def _recursive_descendants_cte(container_id: uuid.UUID, tenant_id: uuid.UUID) -> CTE:
    """Every entity transitively contained in container_id, cycle-safe.

    containment's PK is child_entity_id alone (ADR 0016: at most one
    parent per entity, globally), so a parent->child traversal can never
    diamond-merge - two distinct paths can never converge on the same
    node, since that node's single containment row can only name one
    parent. A node can therefore only reappear via an actual cycle, which
    makes a path-array guard alone provably sufficient here (no closure
    table or SCC precomputation needed). Empirically verified (not just
    reasoned through) against a real 2-cycle and a legitimately deep
    acyclic chain before this was wired into any route.
    """
    base = select(
        Containment.child_entity_id.label("child_entity_id"),
        pg_array([Containment.parent_entity_id, Containment.child_entity_id]).label("path"),
    ).where(
        Containment.parent_entity_id == container_id,
        Containment.tenant_id == tenant_id,
    )
    cte = base.cte("contained", recursive=True)
    recursive_term = (
        select(
            Containment.child_entity_id.label("child_entity_id"),
            (cte.c.path.op("||")(Containment.child_entity_id)).label("path"),
        )
        .select_from(cte.join(Containment, Containment.parent_entity_id == cte.c.child_entity_id))
        .where(
            Containment.tenant_id == tenant_id,
            ~(Containment.child_entity_id == any_(cte.c.path)),
            func.array_length(cte.c.path, 1) < _MAX_CONTAINMENT_DEPTH,
        )
    )
    return cte.union_all(recursive_term)


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

    cte = _recursive_descendants_cte(container_id, tenant_id)
    return (
        select(VItemInstance)
        .select_from(cte.join(VItemInstance, VItemInstance.entity_id == cte.c.child_entity_id))
        .where(VItemInstance.tenant_id == tenant_id)
        .options(*eager_load_options(VItemInstance.entity))
        .order_by(VItemInstance.entity_id)
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
    visibility = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    return ItemInstanceOut.from_v_item_instance(view, request, visibility=visibility)
