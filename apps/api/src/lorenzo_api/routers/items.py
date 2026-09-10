from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import cast

from fastapi import APIRouter, Depends, Request
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import select
from sqlalchemy.orm import InstrumentedAttribute, selectinload
from sqlalchemy.orm.interfaces import ORMOption

from lorenzo_api.dependencies import CurrentUser, ParamsDep, SessionDep, get_tenant_context
from lorenzo_api.exceptions import ItemNotFoundError
from lorenzo_api.information_visibility import resolve_information_visibility
from lorenzo_api.models import Entity, EntityStat, Information, Payload, StatDefinition, VItem
from lorenzo_api.schemas.items import ItemOut

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
) -> tuple[ORMOption, ORMOption, ORMOption, ORMOption]:
    """The exact eager-load recipe proven in `tests/test_v_item.py`'s own
    `_eager_load_options` - required before touching any of
    `ItemViewMixin`'s six properties/methods (ADR 0019/0020), or they
    raise `MissingGreenlet` rather than lazily loading. Parameterized on the
    view's own `entity` relationship attribute (`VItem.entity` here,
    `VItemInstance.entity` in `routers/item_instances.py`, which imports
    this same helper) since each view's join condition differs.
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
        .selectinload(Entity.stats)
        .selectinload(EntityStat.stat_definition)
        .selectinload(StatDefinition.stat_group),
    )


@router.get("")
async def list_items(
    tenant_id: uuid.UUID,
    request: Request,
    params: ParamsDep,
    session: SessionDep,
    user: CurrentUser,
) -> Page[ItemOut]:
    """Every base item type for this tenant - see ADR 0019/0020. Explicit
    tenant_id filter as defense in depth alongside RLS, not a replacement
    for it (ADR 0002/0021).
    """
    stmt = (
        select(VItem)
        .where(VItem.tenant_id == tenant_id)
        .options(*eager_load_options(VItem.entity))
        .order_by(VItem.entity_id)
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
    session: SessionDep,
    user: CurrentUser,
) -> ItemOut:
    stmt = (
        select(VItem)
        .where(VItem.entity_id == entity_id, VItem.tenant_id == tenant_id)
        .options(*eager_load_options(VItem.entity))
    )
    view = (await session.execute(stmt)).scalar_one_or_none()
    if view is None:
        raise ItemNotFoundError(detail=f"No item with id {entity_id} in tenant {tenant_id}")
    visibility = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    return ItemOut.from_v_item(view, request, visibility=visibility)
