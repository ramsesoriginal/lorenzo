import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.db import get_db_session
from lorenzo_api.models import Entity, Tenant

__all__ = ["get_entity_or_404", "get_tenant_context"]


async def get_tenant_context(
    tenant_id: uuid.UUID, session: AsyncSession = Depends(get_db_session)
) -> uuid.UUID:
    """Validates tenant_id is real, then sets app.tenant_id on this same
    request-scoped session for RLS forward-compatibility - see ADR 0020.
    Every route must still filter its own queries by tenant_id explicitly;
    this does not enforce isolation by itself while the app's DB role
    remains a superuser (ADR 0002/0012).
    """
    if await session.get(Tenant, tenant_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    await session.execute(
        text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)}
    )
    return tenant_id


async def get_entity_or_404(
    session: AsyncSession, entity_id: uuid.UUID, tenant_id: uuid.UUID
) -> Entity:
    entity = await session.get(Entity, entity_id)
    if entity is None or entity.tenant_id != tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Entity not found")
    return entity
