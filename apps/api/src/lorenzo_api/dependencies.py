import uuid
from typing import Annotated

from fastapi import Depends
from fastapi_pagination import Params
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.db import get_db_session
from lorenzo_api.exceptions import EntityNotFoundError, TenantNotFoundError
from lorenzo_api.models import Entity, Tenant

__all__ = [
    "ParamsDep",
    "SessionDep",
    "TenantId",
    "get_entity_or_404",
    "get_tenant_context",
]

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
ParamsDep = Annotated[Params, Depends()]


async def get_tenant_context(tenant_id: uuid.UUID, session: SessionDep) -> uuid.UUID:
    """Validates tenant_id is real, then sets app.tenant_id on this same
    request-scoped session for RLS forward-compatibility - see ADR 0020.
    Every route must still filter its own queries by tenant_id explicitly;
    this does not enforce isolation by itself while the app's DB role
    remains a superuser (ADR 0002/0012).
    """
    if await session.get(Tenant, tenant_id) is None:
        raise TenantNotFoundError(detail=f"No tenant with id {tenant_id}")
    await session.execute(
        text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)}
    )
    return tenant_id


TenantId = Annotated[uuid.UUID, Depends(get_tenant_context)]


async def get_entity_or_404(
    session: AsyncSession, entity_id: uuid.UUID, tenant_id: uuid.UUID
) -> Entity:
    entity = await session.get(Entity, entity_id)
    if entity is None or entity.tenant_id != tenant_id:
        raise EntityNotFoundError(detail=f"No entity with id {entity_id} in tenant {tenant_id}")
    return entity
