from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import select
from sqlalchemy.orm import InstrumentedAttribute, selectinload
from sqlalchemy.orm.interfaces import ORMOption

from lorenzo_api.dependencies import (
    CurrentUser,
    ParamsDep,
    SessionDep,
    get_tenant_context,
    set_tenant_rls_context,
)
from lorenzo_api.etag import check_if_match, etag_for
from lorenzo_api.exceptions import ItemNotFoundError, ItemPrototypeInUseError
from lorenzo_api.information_visibility import resolve_information_visibility
from lorenzo_api.models import (
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
from lorenzo_api.schemas.items import ItemCreate, ItemOut, ItemUpdate

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
) -> tuple[ORMOption, ORMOption, ORMOption, ORMOption, ORMOption]:
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
    contain something" fallback, the identical `lazy="raise_on_sql"` trap
    every other relationship here already has to be eager-loaded around.
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
        selectinload(view_entity_attr).selectinload(Entity.contained_links),
    )


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
) -> Page[ItemOut]:
    """Every base item type for this tenant - see ADR 0019/0020. Explicit
    tenant_id filter as defense in depth alongside RLS, not a replacement
    for it (ADR 0002/0021).

    q (ADR 0047) matches against Entity.name, not VItem.title - title is a
    nullable, description-payload-sourced display field, name is the
    item's own stable, always-set identifier and the right search target.
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
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> ItemOut:
    view = await _get_v_item_or_404(tenant_id, entity_id, session)
    visibility = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
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
    entity = await _get_item_entity_or_404(tenant_id, entity_id, session)
    check_if_match(if_match, updated_at=entity.updated_at)
    update = body.model_dump(exclude_unset=True)
    if "name" in update:
        entity.name = update["name"]
        entity.updated_by = user.id
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return await _item_out(tenant_id, entity_id, request, response, session, user)


@router.delete("/{entity_id}", status_code=204)
async def delete_item(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    session: SessionDep,
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

    await session.delete(entity)
    await session.commit()
