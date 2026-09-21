import uuid
from collections.abc import Sequence
from typing import Any, cast

from fastapi import APIRouter, Depends
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import select

from lorenzo_api.dependencies import ParamsDep, SessionDep, get_tenant_context
from lorenzo_api.models import Information, Knowledge
from lorenzo_api.schemas.knowledge import KnowledgeEntryOut

# get_tenant_context: a tenant-wide Membership row is required, and every
# MembershipRole is administrative (OWNER/ORGA) - tests/
# test_activity_log_access.py's tripwire fails if a non-administrative role
# is ever added, at which point this must become an explicit
# is_tenant_admin check (ADR 0084/0085). GMs and players without a
# Membership get a 404, so this never widens who can learn who knows what.
router = APIRouter(
    prefix="/tenants/{tenant_id}/knowledge",
    tags=["knowledge"],
    dependencies=[Depends(get_tenant_context)],
)


@router.get("")
async def list_knowledge(
    tenant_id: uuid.UUID, session: SessionDep, params: ParamsDep
) -> Page[KnowledgeEntryOut]:
    """Every knowledge grant in the tenant - see ADR 0085. The one read
    that shows the `knowledge` table itself: everywhere else it's only a
    filtering effect on what an information read returns, so an export
    (or an owner auditing "who was told this?") had no way to see it.
    Ids only, oldest first so a re-run appends rather than reshuffles.
    """
    stmt = (
        select(
            Knowledge.id,
            Knowledge.information_id,
            Information.entity_id,
            Knowledge.knower_entity_id,
            Knowledge.knower_player_id,
            Knowledge.created_at,
        )
        .join(Information, Information.id == Knowledge.information_id)
        .where(Knowledge.tenant_id == tenant_id, Information.tenant_id == tenant_id)
        .order_by(Knowledge.created_at, Knowledge.id)
    )

    def _entries(rows: Sequence[Any]) -> list[KnowledgeEntryOut]:
        return [KnowledgeEntryOut(**row._mapping) for row in rows]

    return cast(
        Page[KnowledgeEntryOut], await apaginate(session, stmt, params, transformer=_entries)
    )
