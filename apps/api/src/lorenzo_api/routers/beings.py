from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from lorenzo_api.dependencies import ParamsDep, SessionDep, get_tenant_context
from lorenzo_api.models import Being, Entity
from lorenzo_api.schemas.beings import BeingSummaryOut

# get_tenant_context, not get_tenant_or_404 (ADR 0078) - the same
# tenant-wide-Membership tier GET /tenants/{id}/characters already uses,
# deliberately not loosened even though this is a superset of it: this
# endpoint additionally reveals bare-being NPC stubs that characters never
# surfaces at all, so it stays at least as strict, not looser.
router = APIRouter(
    prefix="/tenants/{tenant_id}/beings",
    tags=["beings"],
    dependencies=[Depends(get_tenant_context)],
)


@router.get("")
async def list_beings(
    tenant_id: uuid.UUID,
    session: SessionDep,
    params: ParamsDep,
    q: Annotated[
        str | None,
        Query(description="Case-insensitive substring match against the being's name."),
    ] = None,
) -> Page[BeingSummaryOut]:
    """Every Being in this tenant - PCs, NPCs, and bare beings with no
    Character row at all (ADR 0031's "a bare being with no character row
    remains perfectly valid" case, invisible to GET .../characters) - see
    ADR 0078/issue #94. Item-instance ownership (ADR 0019/RFC 0005)
    already targets any entity generically; this is the missing "pick a
    being" discovery step for a GM assigning loot to an NPC that was never
    promoted into a tracked Character.
    """
    stmt = (
        select(Being)
        .join(Entity, Entity.id == Being.entity_id)
        .where(Being.tenant_id == tenant_id)
        .options(selectinload(Being.entity), selectinload(Being.character))
        .order_by(Being.entity_id)
    )
    if q is not None:
        stmt = stmt.where(Entity.name.ilike(f"%{q}%"))

    def _beings_out(beings: Sequence[Being]) -> list[BeingSummaryOut]:
        return [BeingSummaryOut.from_being(b) for b in beings]

    # apaginate is typed to return Any (fastapi_pagination's own signature) -
    # cast rather than suppress, the declared return type is otherwise
    # exact.
    return cast(
        Page[BeingSummaryOut],
        await apaginate(session, stmt, params, transformer=_beings_out),
    )
