from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from fastapi_problem.error import Problem
from sqlalchemy import CTE, delete, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import InstrumentedAttribute, selectinload
from sqlalchemy.orm.interfaces import ORMOption

from lorenzo_api.activity_log import record_activity
from lorenzo_api.dependencies import (
    CurrentUser,
    ParamsDep,
    SessionDep,
    get_entity_or_404,
    get_tenant_context,
    set_tenant_rls_context,
)
from lorenzo_api.etag import check_if_match, etag_for
from lorenzo_api.exceptions import (
    EntityPrototypeCycleError,
    InvalidPrototypeError,
    ItemNotFoundError,
    ItemPrototypeInUseError,
)
from lorenzo_api.information_visibility import resolve_information_visibility
from lorenzo_api.models import (
    ComputedStat,
    Entity,
    EntityPrototype,
    Information,
    Item,
    ItemInstance,
    Payload,
    StatDefinition,
    VEffectiveStat,
    VItem,
)
from lorenzo_api.schemas.items import (
    BulkAddPrototypeRequest,
    BulkAddPrototypeResultItem,
    BulkRemovePrototypeRequest,
    BulkRemovePrototypeResultItem,
    BulkReparentPrototypeRequest,
    BulkReparentResultItem,
    ItemCreate,
    ItemOut,
    ItemUpdate,
    ProblemOut,
    PrototypeAncestorOut,
    SetPrototypesRequest,
)

# get_tenant_context here, not per-route (ADR 0020's revised guidance) -
# every route on this router needs it and none read its return value, the
# textbook case FastAPI's own docs give for a router-level dependency.
router = APIRouter(
    prefix="/tenants/{tenant_id}/items",
    tags=["items"],
    dependencies=[Depends(get_tenant_context)],
)


def eager_load_options(
    view_entity_attr: InstrumentedAttribute[Entity],
) -> tuple[ORMOption, ...]:
    """The exact eager-load recipe proven in `tests/test_v_item.py`'s own
    `_eager_load_options` - required before touching any of
    `EntityViewMixin`'s six properties/methods (ADR 0019/0020), or they
    raise `MissingGreenlet` rather than lazily loading. Parameterized on the
    view's own `entity` relationship attribute (`VItem.entity` here,
    `VItemInstance.entity` in `routers/item_instances.py`, which imports
    this same helper) since each view's join condition differs.

    Loads `Entity.effective_stats` (ADR 0039's resolved, prototype-
    inheriting view), not `Entity.stats` - `EntityViewMixin`'s
    `physical_stats`/`tags`/etc. read the former so they agree with
    `weight`/`hp`/`armor`/etc. instead of silently showing an entity's own
    direct stats only.

    Also loads `Entity.contained_links` (ADR 0041's association-object
    containment list, `parent_entity_id`-side) - not an `EntityViewMixin`
    property, but `schemas/items.py`'s `_is_container_out` (ADR 0066)
    reads it directly off `view.entity` for its own "does this actually
    contain something" fallback - and `Entity.prototype_links` (ADR 0072's
    `prototype_ids`) - the identical `lazy="raise_on_sql"` trap every other
    relationship here already has to be eager-loaded around.
    """
    return (
        selectinload(view_entity_attr)
        .selectinload(Entity.information)
        .selectinload(Information.payloads)
        .selectinload(Payload.description),
        selectinload(view_entity_attr)
        .selectinload(Entity.information)
        .selectinload(Information.payloads)
        .selectinload(Payload.picture),
        selectinload(view_entity_attr)
        .selectinload(Entity.information)
        .selectinload(Information.knowledge_links),
        selectinload(view_entity_attr)
        .selectinload(Entity.effective_stats)
        .selectinload(VEffectiveStat.stat_definition)
        .selectinload(StatDefinition.stat_group),
        # A winning formula's parameters, for stat_evaluation (ADR 0104).
        selectinload(view_entity_attr)
        .selectinload(Entity.effective_stats)
        .selectinload(VEffectiveStat.computed_stat)
        .selectinload(ComputedStat.linear),
        selectinload(view_entity_attr)
        .selectinload(Entity.effective_stats)
        .selectinload(VEffectiveStat.computed_stat)
        .selectinload(ComputedStat.comparison),
        selectinload(view_entity_attr).selectinload(Entity.contained_links),
        selectinload(view_entity_attr).selectinload(Entity.prototype_links),
    )


def _prototype_descendants_cte(prototype_id: uuid.UUID, tenant_id: uuid.UUID) -> CTE:
    """Every entity that transitively depends on prototype_id (has it as a
    direct or indirect prototype) - see ADR 0073. Plain UNION, not UNION
    ALL: entity_prototype allows multiple inheritance, so the same
    descendant can be reached via more than one path, and UNION's own
    de-duplication is what makes "keep walking until nothing new appears"
    correct here - the exact technique entity_prototype's own BEFORE INSERT
    cycle-check trigger (ADR 0015, migration 8fd1b287598a) already uses for
    its ancestor walk, mirrored in the opposite direction. No path-array
    cycle guard the way entity_access.py's containment walk needs one -
    that graph can legitimately cycle (ADR 0016), this one cannot (the
    trigger already guarantees it), so plain UNION alone is sufficient and
    always terminates.
    """
    base = select(EntityPrototype.entity_id.label("descendant_id")).where(
        EntityPrototype.prototype_id == prototype_id, EntityPrototype.tenant_id == tenant_id
    )
    cte = base.cte("item_prototype_descendants", recursive=True)
    recursive_term = (
        select(EntityPrototype.entity_id.label("descendant_id"))
        .select_from(cte.join(EntityPrototype, EntityPrototype.prototype_id == cte.c.descendant_id))
        .where(EntityPrototype.tenant_id == tenant_id)
    )
    return cte.union(recursive_term)


def _prototype_ancestors_cte(entity_id: uuid.UUID, tenant_id: uuid.UUID) -> CTE:
    """Every one of entity_id's own transitive ancestors (direct and
    indirect prototypes) - the exact mirror of _prototype_descendants_cte's
    downward walk. See that function's own docstring for why plain UNION
    (no path-array guard) is correct here.
    """
    base = select(EntityPrototype.prototype_id.label("ancestor_id")).where(
        EntityPrototype.entity_id == entity_id, EntityPrototype.tenant_id == tenant_id
    )
    cte = base.cte("item_prototype_ancestors", recursive=True)
    recursive_term = (
        select(EntityPrototype.prototype_id.label("ancestor_id"))
        .select_from(cte.join(EntityPrototype, EntityPrototype.entity_id == cte.c.ancestor_id))
        .where(EntityPrototype.tenant_id == tenant_id)
    )
    return cte.union(recursive_term)


@router.get("")
async def list_items(
    tenant_id: uuid.UUID,
    request: Request,
    params: ParamsDep,
    session: SessionDep,
    user: CurrentUser,
    q: Annotated[
        str | None,
        Query(description="Case-insensitive substring match against the item's name."),
    ] = None,
    prototype_id: Annotated[
        uuid.UUID | None,
        Query(description="Only return items that have this entity as a prototype."),
    ] = None,
    recursive: Annotated[
        bool,
        Query(
            description=(
                "With prototype_id, also include items that inherit from it transitively, "
                "not just directly."
            )
        ),
    ] = False,
) -> Page[ItemOut]:
    """Every base item type for this tenant - see ADR 0019/0020. Explicit
    tenant_id filter as defense in depth alongside RLS, not a replacement
    for it (ADR 0002/0021).

    q (ADR 0047) matches against Entity.name, not VItem.title - title is a
    nullable, description-payload-sourced display field, name is the
    item's own stable, always-set identifier and the right search target.

    prototype_id/recursive (ADR 0073) - the reverse-lookup filter: "what's
    built on top of X." recursive defaults to false (direct prototypes
    only), the same default/opt-in shape GET /item-instances?container_id=
    already established for containment (ADR 0065); recursive without
    prototype_id is a no-op, not an error, matching that same route's own
    treatment of recursive without container_id.
    """
    stmt = (
        select(VItem)
        .join(Entity, Entity.id == VItem.entity_id)
        .where(VItem.tenant_id == tenant_id)
        .options(*eager_load_options(VItem.entity))
        .order_by(VItem.entity_id)
    )
    if q is not None:
        stmt = stmt.where(Entity.name.ilike(f"%{q}%"))
    if prototype_id is not None:
        # Validate up front, before anything else - a cross-tenant probe
        # must 404 exactly like an unknown id, the same treatment
        # container_id already gets on the item-instances list route.
        await get_entity_or_404(session, prototype_id, tenant_id)
        if recursive:
            descendants_cte = _prototype_descendants_cte(prototype_id, tenant_id)
            stmt = stmt.where(VItem.entity_id.in_(select(descendants_cte.c.descendant_id)))
        else:
            stmt = stmt.join(EntityPrototype, EntityPrototype.entity_id == VItem.entity_id).where(
                EntityPrototype.prototype_id == prototype_id,
                EntityPrototype.tenant_id == tenant_id,
            )
    # Resolved once per request, not once per row - reused by every item on
    # the page (ADR 0028's addendum).
    visibility = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)

    def _items_out(items: Sequence[VItem]) -> list[ItemOut]:
        return [ItemOut.from_v_item(item, request, visibility=visibility) for item in items]

    # apaginate is typed to return Any (fastapi_pagination's own signature) -
    # cast rather than suppress, the declared return type is otherwise
    # exact.
    return cast(Page[ItemOut], await apaginate(session, stmt, params, transformer=_items_out))


@router.get("/{entity_id}")
async def get_item(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> ItemOut:
    view = await _get_v_item_or_404(tenant_id, entity_id, session)
    visibility = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    response.headers["ETag"] = etag_for(view.entity.updated_at)
    return ItemOut.from_v_item(view, request, visibility=visibility)


async def _get_v_item_or_404(
    tenant_id: uuid.UUID, entity_id: uuid.UUID, session: SessionDep
) -> VItem:
    stmt = (
        select(VItem)
        .where(VItem.entity_id == entity_id, VItem.tenant_id == tenant_id)
        .options(*eager_load_options(VItem.entity))
    )
    view = (await session.execute(stmt)).scalar_one_or_none()
    if view is None:
        raise ItemNotFoundError(detail=f"No item with id {entity_id} in tenant {tenant_id}")
    return view


async def _get_item_entity_or_404(
    tenant_id: uuid.UUID, entity_id: uuid.UUID, session: SessionDep
) -> Entity:
    """Loads the writable Entity row (not the read-only VItem view) for a
    known item - PATCH/DELETE act on Entity/Item directly, mirroring
    get_item_instance's own view-for-reads/table-for-writes split.
    """
    stmt = (
        select(Entity)
        .join(Item, Item.entity_id == Entity.id)
        .where(Entity.id == entity_id, Entity.tenant_id == tenant_id)
    )
    entity = (await session.execute(stmt)).scalar_one_or_none()
    if entity is None:
        raise ItemNotFoundError(detail=f"No item with id {entity_id} in tenant {tenant_id}")
    return entity


async def _item_out(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    request: Request,
    response: Response | None,
    session: SessionDep,
    user: CurrentUser,
) -> ItemOut:
    """response is None only for the ADR 0073 bulk routes' per-item results
    - a batch response representing N resources has no single ETag of its
    own to set, mirroring routers/item_instances.py's identical
    _item_instance_out parameter.
    """
    view = await _get_v_item_or_404(tenant_id, entity_id, session)
    visibility = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    if response is not None:
        response.headers["ETag"] = etag_for(view.entity.updated_at)
    return ItemOut.from_v_item(view, request, visibility=visibility)


@router.post("", status_code=201)
async def create_item(
    tenant_id: uuid.UUID,
    body: ItemCreate,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> ItemOut:
    """Authoring the shared catalog vocabulary is a tenant-admin concern
    (get_tenant_context, unchanged, per ADR 0032/RFC 0005) - not
    self-or-managed, unlike item-instances below.
    """
    entity = Entity(tenant_id=tenant_id, name=body.name, created_by=user.id, updated_by=user.id)
    session.add(entity)
    await session.flush()
    session.add(Item(entity_id=entity.id, tenant_id=tenant_id))
    for prototype_id in body.prototype_ids:
        session.add(
            EntityPrototype(entity_id=entity.id, prototype_id=prototype_id, tenant_id=tenant_id)
        )
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="item.created",
        target_type="item",
        target_id=entity.id,
        detail=f"prototypes={len(body.prototype_ids)}",
    )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    response.headers["Location"] = str(
        request.url_for("get_item", tenant_id=tenant_id, entity_id=entity.id)
    )
    return await _item_out(tenant_id, entity.id, request, response, session, user)


@router.patch("/{entity_id}")
async def update_item(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    body: ItemUpdate,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> ItemOut:
    """A rename - deliberately not recorded in the activity log (ADR 0084:
    descriptive-content edits are excluded; `updated_by` already says who
    last touched it).
    """
    entity = await _get_item_entity_or_404(tenant_id, entity_id, session)
    check_if_match(if_match, updated_at=entity.updated_at)
    update = body.model_dump(exclude_unset=True)
    if "name" in update:
        entity.name = update["name"]
        entity.updated_by = user.id
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return await _item_out(tenant_id, entity_id, request, response, session, user)


@router.put("/{entity_id}/prototypes")
async def replace_item_prototypes(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    body: SetPrototypesRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> ItemOut:
    """Prototypes as a set sub-resource - PUT fully replaces entity_id's own
    direct EntityPrototype edges, the same "PUT replaces the relationship"
    convention ADR 0032/RFC 0005 already established for owner/container,
    just over a set rather than a single value. See ADR 0072.

    An empty list clears every prototype - there's no separate DELETE
    action, unlike owner/container: those are singular values with no
    "empty" representation of their own, so clearing needs a row delete; a
    set's own empty state is already expressible as an ordinary PUT body.

    Unlike owner/container, this does touch entity.updated_by/updated_at -
    a prototype set is part of what the item *is* (it changes the item's
    own resolved stats, ADR 0037/0039), not where it's placed.
    """
    entity = await _get_item_entity_or_404(tenant_id, entity_id, session)
    check_if_match(if_match, updated_at=entity.updated_at)

    prototype_ids = set(body.prototype_ids)
    if entity_id in prototype_ids:
        raise EntityPrototypeCycleError(detail=f"Item {entity_id} cannot be its own prototype")

    if prototype_ids:
        found_stmt = select(Entity.id).where(
            Entity.id.in_(prototype_ids), Entity.tenant_id == tenant_id
        )
        found_ids = set((await session.execute(found_stmt)).scalars().all())
        missing_ids = prototype_ids - found_ids
        if missing_ids:
            raise InvalidPrototypeError(
                detail=(
                    f"Prototype id(s) {sorted(str(i) for i in missing_ids)} do not exist "
                    f"in tenant {tenant_id}"
                )
            )

    await session.execute(
        delete(EntityPrototype).where(
            EntityPrototype.entity_id == entity_id, EntityPrototype.tenant_id == tenant_id
        )
    )
    for prototype_id in prototype_ids:
        session.add(
            EntityPrototype(entity_id=entity_id, prototype_id=prototype_id, tenant_id=tenant_id)
        )
    entity.updated_by = user.id

    try:
        await session.flush()
    except DBAPIError as exc:
        # entity_prototype's own BEFORE INSERT trigger (ADR 0015) - the
        # first write path able to actually reach it through client input,
        # since every prototype id up to now only ever appeared on a
        # brand-new entity (POST /items/POST /item-instances), which can't
        # yet be anyone's ancestor. Translated rather than left as a 500.
        raise EntityPrototypeCycleError(
            detail=f"Replacing item {entity_id}'s prototypes would create an inheritance cycle"
        ) from exc

    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="item.prototypes_replaced",
        target_type="item",
        target_id=entity_id,
        detail=f"prototypes={len(prototype_ids)}",
    )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return await _item_out(tenant_id, entity_id, request, response, session, user)


@router.get("/{entity_id}/prototypes/ancestry")
async def get_item_prototype_ancestry(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    session: SessionDep,
) -> list[PrototypeAncestorOut]:
    """Every transitive ancestor of entity_id (direct and indirect
    prototypes), not just the direct set ItemOut.prototype_ids already
    exposes. See ADR 0073. Not paginated - prototype graphs are shallow by
    construction (ADR 0015), the same "bounded, no pagination needed"
    reasoning OwnedByResponse already uses.
    """
    await _get_item_entity_or_404(tenant_id, entity_id, session)

    cte = _prototype_ancestors_cte(entity_id, tenant_id)
    ancestor_ids = (await session.execute(select(cte.c.ancestor_id))).scalars().all()
    if not ancestor_ids:
        return []

    stmt = (
        select(Entity)
        .where(Entity.id.in_(ancestor_ids), Entity.tenant_id == tenant_id)
        .options(selectinload(Entity.prototype_links))
        .order_by(Entity.name, Entity.id)
    )
    ancestors = (await session.execute(stmt)).scalars().all()
    return [
        PrototypeAncestorOut(
            entity_id=ancestor.id,
            name=ancestor.name,
            # Always a subset of the returned ancestor set itself (a direct
            # prototype of an ancestor is transitively an ancestor too), so
            # no filtering against ancestor_ids is needed here.
            prototype_ids=sorted((link.prototype_id for link in ancestor.prototype_links), key=str),
        )
        for ancestor in ancestors
    ]


@router.delete("/{entity_id}", status_code=204)
async def delete_item(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> None:
    """Guarded: 409 if any item_instance's entity directly prototypes this
    item - ADR 0018's blanket cascade would otherwise silently delete the
    entity_prototype edge (not the instance) the moment this item's Entity
    is deleted, leaving every instance that inherited from it quietly
    missing stats it used to resolve through. No ?force= escape hatch -
    the caller's real fix is to delete or re-parent the instances first.
    """
    entity = await _get_item_entity_or_404(tenant_id, entity_id, session)
    check_if_match(if_match, updated_at=entity.updated_at)

    in_use_stmt = (
        select(ItemInstance.entity_id)
        .join(EntityPrototype, EntityPrototype.entity_id == ItemInstance.entity_id)
        .where(EntityPrototype.prototype_id == entity_id, ItemInstance.tenant_id == tenant_id)
        .limit(1)
    )
    if (await session.execute(in_use_stmt)).first() is not None:
        raise ItemPrototypeInUseError(
            detail=f"Item {entity_id} is still a direct prototype of at least one item instance"
        )

    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="item.deleted",
        target_type="item",
        target_id=entity_id,
        detail=None,
    )
    await session.delete(entity)
    await session.commit()


async def _record_bulk_prototype_activity(
    session: SessionDep,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    action: str,
    target_id: uuid.UUID,
    results: Sequence[
        BulkReparentResultItem | BulkAddPrototypeResultItem | BulkRemovePrototypeResultItem
    ],
) -> None:
    """One entry per bulk call, counts only (ADR 0084); nothing is written
    when no item succeeded, since then nothing changed. `target_id` is the
    prototype being added/removed/re-parented to.
    """
    ok = sum(1 for result in results if result.status == "ok")
    if ok == 0:
        return
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=action,
        target_type="item",
        target_id=target_id,
        detail=f"{ok} ok, {len(results) - ok} failed",
    )


async def _validate_prototype_ids_exist(
    session: SessionDep, prototype_ids: set[uuid.UUID], tenant_id: uuid.UUID
) -> None:
    """Shared up-front existence check for the ADR 0073 bulk routes below -
    each validates the prototype id(s) its own body names once, before the
    per-item loop, the same "doesn't vary per item" reasoning ADR 0062/0065
    already established for their own shared destination checks.
    """
    found_ids = set(
        (
            await session.execute(
                select(Entity.id).where(Entity.id.in_(prototype_ids), Entity.tenant_id == tenant_id)
            )
        )
        .scalars()
        .all()
    )
    missing_ids = prototype_ids - found_ids
    if missing_ids:
        raise InvalidPrototypeError(
            detail=(
                f"Prototype id(s) {sorted(str(i) for i in missing_ids)} do not exist "
                f"in tenant {tenant_id}"
            )
        )


@router.post("/bulk-reparent-prototype")
async def bulk_reparent_item_prototype(
    tenant_id: uuid.UUID,
    body: BulkReparentPrototypeRequest,
    request: Request,
    session: SessionDep,
    user: CurrentUser,
) -> list[BulkReparentResultItem]:
    """Replaces from_prototype_id with to_prototype_id across many items in
    one call - ADR 0073's "push a prototype up the chain." item_ids omitted
    resolves to every Item currently having from_prototype_id as a direct
    prototype; given explicitly, an item that doesn't currently have it is
    a tolerated no-op, not an error.

    Never all-or-nothing, the same session.begin_nested()-per-item pattern
    as bulk_assign_item_instances/bulk_move_item_instances: a caught
    Problem becomes that item's own "error" entry, everything else already
    applied proceeds to the one shared commit.
    """
    await _validate_prototype_ids_exist(
        session, {body.from_prototype_id, body.to_prototype_id}, tenant_id
    )

    if body.item_ids is not None:
        entity_ids: Sequence[uuid.UUID] = body.item_ids
    else:
        stmt = (
            select(EntityPrototype.entity_id)
            .join(Item, Item.entity_id == EntityPrototype.entity_id)
            .where(
                EntityPrototype.prototype_id == body.from_prototype_id,
                EntityPrototype.tenant_id == tenant_id,
            )
        )
        entity_ids = (await session.execute(stmt)).scalars().all()

    results: list[BulkReparentResultItem] = []
    for entity_id in entity_ids:
        try:
            async with session.begin_nested():
                entity = await _get_item_entity_or_404(tenant_id, entity_id, session)
                existing_link = await session.get(
                    EntityPrototype, (entity_id, body.from_prototype_id)
                )
                if existing_link is not None:
                    if entity_id == body.to_prototype_id:
                        raise EntityPrototypeCycleError(
                            detail=f"Item {entity_id} cannot be its own prototype"
                        )
                    await session.delete(existing_link)
                    if (
                        await session.get(EntityPrototype, (entity_id, body.to_prototype_id))
                        is None
                    ):
                        session.add(
                            EntityPrototype(
                                entity_id=entity_id,
                                prototype_id=body.to_prototype_id,
                                tenant_id=tenant_id,
                            )
                        )
                    entity.updated_by = user.id
                    try:
                        await session.flush()
                    except DBAPIError as exc:
                        raise EntityPrototypeCycleError(
                            detail=(
                                f"Re-parenting item {entity_id} onto {body.to_prototype_id} "
                                "would create an inheritance cycle"
                            )
                        ) from exc
        except Problem as exc:
            results.append(
                BulkReparentResultItem(
                    entity_id=entity_id,
                    status="error",
                    item=None,
                    problem=ProblemOut(**exc.marshal()),
                )
            )
            continue
        item_out = await _item_out(tenant_id, entity_id, request, None, session, user)
        results.append(
            BulkReparentResultItem(entity_id=entity_id, status="ok", item=item_out, problem=None)
        )

    await _record_bulk_prototype_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="item.bulk_reparented",
        target_id=body.to_prototype_id,
        results=results,
    )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return results


@router.post("/bulk-add-prototype")
async def bulk_add_item_prototype(
    tenant_id: uuid.UUID,
    body: BulkAddPrototypeRequest,
    request: Request,
    session: SessionDep,
    user: CurrentUser,
) -> list[BulkAddPrototypeResultItem]:
    """Adds prototype_id to every listed item's direct prototype set - ADR
    0073. An item that already has it is a tolerated no-op; attribution
    (updated_by/updated_at) is only stamped when the edge actually changed,
    unlike PUT .../prototypes' own unconditional bump (ADR 0072) - this is
    an idempotent "ensure present" check-then-act, not a declarative
    replace.
    """
    await _validate_prototype_ids_exist(session, {body.prototype_id}, tenant_id)

    results: list[BulkAddPrototypeResultItem] = []
    for entity_id in body.item_ids:
        try:
            async with session.begin_nested():
                entity = await _get_item_entity_or_404(tenant_id, entity_id, session)
                if entity_id == body.prototype_id:
                    raise EntityPrototypeCycleError(
                        detail=f"Item {entity_id} cannot be its own prototype"
                    )
                if await session.get(EntityPrototype, (entity_id, body.prototype_id)) is None:
                    session.add(
                        EntityPrototype(
                            entity_id=entity_id,
                            prototype_id=body.prototype_id,
                            tenant_id=tenant_id,
                        )
                    )
                    entity.updated_by = user.id
                    try:
                        await session.flush()
                    except DBAPIError as exc:
                        raise EntityPrototypeCycleError(
                            detail=(
                                f"Adding prototype {body.prototype_id} to item {entity_id} "
                                "would create an inheritance cycle"
                            )
                        ) from exc
        except Problem as exc:
            results.append(
                BulkAddPrototypeResultItem(
                    entity_id=entity_id,
                    status="error",
                    item=None,
                    problem=ProblemOut(**exc.marshal()),
                )
            )
            continue
        item_out = await _item_out(tenant_id, entity_id, request, None, session, user)
        results.append(
            BulkAddPrototypeResultItem(
                entity_id=entity_id, status="ok", item=item_out, problem=None
            )
        )

    await _record_bulk_prototype_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="item.bulk_prototype_added",
        target_id=body.prototype_id,
        results=results,
    )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return results


@router.post("/bulk-remove-prototype")
async def bulk_remove_item_prototype(
    tenant_id: uuid.UUID,
    body: BulkRemovePrototypeRequest,
    request: Request,
    session: SessionDep,
    user: CurrentUser,
) -> list[BulkRemovePrototypeResultItem]:
    """Removes prototype_id from every listed item's direct prototype set -
    ADR 0073. An item that doesn't have it is a tolerated no-op. No cycle
    risk - removing an edge can never create one - so no DBAPIError
    translation is needed here, unlike bulk_add_item_prototype.
    """
    await _validate_prototype_ids_exist(session, {body.prototype_id}, tenant_id)

    results: list[BulkRemovePrototypeResultItem] = []
    for entity_id in body.item_ids:
        try:
            async with session.begin_nested():
                entity = await _get_item_entity_or_404(tenant_id, entity_id, session)
                existing = await session.get(EntityPrototype, (entity_id, body.prototype_id))
                if existing is not None:
                    await session.delete(existing)
                    entity.updated_by = user.id
                    await session.flush()
        except Problem as exc:
            results.append(
                BulkRemovePrototypeResultItem(
                    entity_id=entity_id,
                    status="error",
                    item=None,
                    problem=ProblemOut(**exc.marshal()),
                )
            )
            continue
        item_out = await _item_out(tenant_id, entity_id, request, None, session, user)
        results.append(
            BulkRemovePrototypeResultItem(
                entity_id=entity_id, status="ok", item=item_out, problem=None
            )
        )

    await _record_bulk_prototype_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="item.bulk_prototype_removed",
        target_id=body.prototype_id,
        results=results,
    )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return results
