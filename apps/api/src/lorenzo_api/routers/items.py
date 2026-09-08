from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute, selectinload
from sqlalchemy.orm.strategy_options import _AbstractLoad

from lorenzo_api.db import get_db_session
from lorenzo_api.dependencies import get_tenant_context
from lorenzo_api.models import Entity, EntityStat, Information, Payload, StatDefinition, VItem
from lorenzo_api.schemas.items import ItemOut

router = APIRouter(prefix="/tenants/{tenant_id}/items", tags=["items"])


def eager_load_options(
    view_entity_attr: InstrumentedAttribute[Entity],
) -> tuple[_AbstractLoad, _AbstractLoad, _AbstractLoad]:
    """The exact eager-load recipe proven in `tests/test_v_item.py`'s own
    `_eager_load_options` - required before touching any of
    `ItemViewMixin`'s seven properties (ADR 0019/0020), or they raise
    `MissingGreenlet` rather than lazily loading. Parameterized on the
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
        .selectinload(Entity.stats)
        .selectinload(EntityStat.stat_definition)
        .selectinload(StatDefinition.stat_group),
    )


@router.get("")
async def list_items(
    tenant_id: uuid.UUID,
    request: Request,
    params: Params = Depends(),
    session: AsyncSession = Depends(get_db_session),
    _tenant: uuid.UUID = Depends(get_tenant_context),
) -> Page[ItemOut]:
    """Every base item type for this tenant - see ADR 0019/0020. Explicit
    tenant_id filter (RLS isn't enforcing anything today - ADR 0002/0012).
    """
    stmt = (
        select(VItem)
        .where(VItem.tenant_id == tenant_id)
        .options(*eager_load_options(VItem.entity))
        .order_by(VItem.entity_id)
    )

    def _items_out(items: Sequence[VItem]) -> list[ItemOut]:
        return [ItemOut.from_v_item(item, request) for item in items]

    # apaginate is typed to return Any (fastapi_pagination's own signature) -
    # cast rather than suppress, the declared return type is otherwise
    # exact.
    return cast(Page[ItemOut], await apaginate(session, stmt, params, transformer=_items_out))


@router.get("/{entity_id}")
async def get_item(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    _tenant: uuid.UUID = Depends(get_tenant_context),
) -> ItemOut:
    stmt = (
        select(VItem)
        .where(VItem.entity_id == entity_id, VItem.tenant_id == tenant_id)
        .options(*eager_load_options(VItem.entity))
    )
    view = (await session.execute(stmt)).scalar_one_or_none()
    if view is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Item not found")
    return ItemOut.from_v_item(view, request)
