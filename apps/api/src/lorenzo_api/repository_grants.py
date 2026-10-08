"""A repository's grant to a library, and telling the people who run the libraries concerned.

Two doors lead to the same grant (ADR 0118, ADR 0211): the Owner of a repository naming a
library by its id (`PUT /tenants/{id}/subscribers/{library}`), and a library-access invite link
redeemed by the Owner of a library. Both call `grant_repository_access`, so what a grant
writes, logs and says is one thing. No commit here: the routes commit.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.activity_log import record_activity
from lorenzo_api.dependencies import set_tenant_rls_context
from lorenzo_api.models import RepositorySubscription, Tenant
from lorenzo_api.notifications import create_tenant_admins_notification

__all__ = ["grant_repository_access", "notify_tenant_admins"]


async def notify_tenant_admins(
    session: AsyncSession,
    *,
    recipient_tenant_ids: Sequence[uuid.UUID],
    current_tenant_id: uuid.UUID,
    type: str,
    title: str,
    body: str,
    created_by: uuid.UUID,
) -> None:
    """Tells each tenant's Owners and Organizers, reading each one's Membership under its
    own RLS context, then puts the current tenant's context back. Flushes
    first: anything still pending belongs to the current tenant, and would
    fail RLS if autoflush wrote it under another tenant's context.
    """
    await session.flush()
    for recipient in recipient_tenant_ids:
        await set_tenant_rls_context(session, recipient)
        await create_tenant_admins_notification(
            session,
            tenant_id=recipient,
            type=type,
            title=title,
            body=body,
            created_by=created_by,
        )
    await set_tenant_rls_context(session, current_tenant_id)


async def grant_repository_access(
    session: AsyncSession,
    *,
    repository: Tenant,
    subscriber: Tenant,
    granted_by: uuid.UUID,
    detail: str | None = None,
) -> None:
    """Writes the grant, logs it in the repository's activity log and tells the subscribing
    tenant's Owners and Organizers (ADR 0118). The caller has checked that the grant does not
    exist yet and that the subscriber is not the repository, and runs under the repository's
    RLS context, which is where a grant is created.
    """
    session.add(
        RepositorySubscription(
            repository_tenant_id=repository.id,
            subscriber_tenant_id=subscriber.id,
            created_by=granted_by,
        )
    )
    await record_activity(
        session,
        tenant_id=repository.id,
        actor_id=granted_by,
        action="repository.granted",
        target_type="tenant",
        target_id=subscriber.id,
        detail=detail,
    )
    await notify_tenant_admins(
        session,
        recipient_tenant_ids=[subscriber.id],
        current_tenant_id=repository.id,
        type="repository_granted",
        title=f"{repository.name} is available to {subscriber.name}",
        body=(
            "You can browse it and copy it into your tenant."
            if repository.published_at is not None
            else "It isn't published yet. You'll be told when it is."
        ),
        created_by=granted_by,
    )
