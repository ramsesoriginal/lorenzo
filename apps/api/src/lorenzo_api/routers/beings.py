from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from lorenzo_api.campaign_access import is_tenant_admin, is_tenant_gm
from lorenzo_api.dependencies import (
    CurrentUser,
    ParamsDep,
    SessionDep,
    get_tenant_or_404,
)
from lorenzo_api.exceptions import TenantNotFoundError
from lorenzo_api.information_visibility import resolve_information_visibility
from lorenzo_api.models import Being, Entity
from lorenzo_api.schemas.beings import BeingSummaryOut

# No router-level gate: who may list, and which beings, is decided in the
# route (ADR 0078's original tier, as amended by ADR 0173). The tenant must
# exist (get_tenant_or_404, existence only), and then the caller is a tenant
# administrator (every being), a GM (the beings in their reach), or neither.
router = APIRouter(prefix="/tenants/{tenant_id}/beings", tags=["beings"])


@router.get("")
async def list_beings(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_or_404)],
    session: SessionDep,
    user: CurrentUser,
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

    Who asks decides which (ADR 0173, amending ADR 0078's membership-only
    gate): a tenant administrator (OWNER or ORGA) lists every being, as
    before; a GM with no membership lists the beings in their reach
    (`gm_reachable_entity_ids`, ADR 0035/0046/0124/0152: their campaigns'
    characters, the scenes those stand in, and the beings in no campaign the
    tenant's `npcs_shared_with_gms` setting gives them), so another table's
    player characters stay private; anyone else - a player, a participant with
    no GM role - gets the same 404 a non-member always did.
    """
    reach: frozenset[uuid.UUID] | None = None
    if not await is_tenant_admin(session, tenant_id=tenant_id, user_id=user.id):
        if not await is_tenant_gm(session, tenant_id=tenant_id, user_id=user.id):
            raise TenantNotFoundError(detail=f"No tenant with id {tenant_id}")
        reach = (
            await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
        ).gm_reachable_entity_ids

    stmt = (
        select(Being)
        .join(Entity, Entity.id == Being.entity_id)
        .where(Being.tenant_id == tenant_id)
        .options(selectinload(Being.entity), selectinload(Being.character))
        .order_by(Being.entity_id)
    )
    if reach is not None:
        stmt = stmt.where(Being.entity_id.in_(reach))
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
