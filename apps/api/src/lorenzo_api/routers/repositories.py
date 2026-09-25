"""Repositories - RFC 0024, ADR 0118 onward.

A repository is a tenant of kind `repository`: a reusable setting other
tenants are granted access to and copy from. This router holds what's
repository-specific; authoring a repository's content goes through the
same routes as any other tenant's.
"""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends

from lorenzo_api.activity_log import record_activity
from lorenzo_api.campaign_access import is_tenant_owner
from lorenzo_api.dependencies import (
    CurrentUser,
    SessionDep,
    get_tenant_context,
    set_tenant_rls_context,
)
from lorenzo_api.exceptions import NotARepositoryError, RepositoryManagementForbiddenError
from lorenzo_api.models import Tenant, TenantKind
from lorenzo_api.schemas.tenants import TenantOut

router = APIRouter(prefix="/tenants/{tenant_id}", tags=["repositories"])


async def _require_owner(session: SessionDep, *, tenant_id: uuid.UUID, user: CurrentUser) -> None:
    if not await is_tenant_owner(session, tenant_id=tenant_id, user_id=user.id):
        raise RepositoryManagementForbiddenError(
            detail=f"Only an owner of tenant {tenant_id} can do this"
        )


async def _require_repository(session: SessionDep, tenant_id: uuid.UUID) -> Tenant:
    tenant = await session.get_one(Tenant, tenant_id)
    if tenant.kind is not TenantKind.REPOSITORY:
        raise NotARepositoryError(detail=f"Tenant {tenant_id} is for play, not a repository")
    return tenant


@router.put("/published")
async def publish_repository(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    session: SessionDep,
    user: CurrentUser,
) -> TenantOut:
    """Publishes a repository, or announces an update to one already
    published: either way `published_at` becomes now (ADR 0118). Until the
    first publish, no subscriber can see anything of it.
    """
    await _require_owner(session, tenant_id=tenant_id, user=user)
    tenant = await _require_repository(session, tenant_id)
    tenant.published_at = datetime.now(UTC)
    tenant.updated_by = user.id
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="repository.published",
        target_type="tenant",
        target_id=tenant_id,
    )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return TenantOut.model_validate(await session.get_one(Tenant, tenant_id))


@router.delete("/published")
async def unpublish_repository(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    session: SessionDep,
    user: CurrentUser,
) -> TenantOut:
    """Back to draft: subscribers can no longer browse, copy, or check
    for updates. What they already copied is theirs and stays (RFC 0024
    §6)."""
    await _require_owner(session, tenant_id=tenant_id, user=user)
    tenant = await _require_repository(session, tenant_id)
    if tenant.published_at is not None:
        tenant.published_at = None
        tenant.updated_by = user.id
        await record_activity(
            session,
            tenant_id=tenant_id,
            actor_id=user.id,
            action="repository.unpublished",
            target_type="tenant",
            target_id=tenant_id,
        )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return TenantOut.model_validate(await session.get_one(Tenant, tenant_id))
