"""A repository's grant to a library, and telling the people who run the libraries concerned.

Two doors lead to the same grant (ADR 0118, ADR 0220): the Owner of a repository naming a
library by its id (`PUT /tenants/{id}/subscribers/{library}`), and a library-access invite link
redeemed by the Owner of a library. Both call `grant_repository_access`, so what a grant
writes, logs and says is one thing. A third, `subscribe_to_public`, is the library giving itself
a grant to a public repository when it copies it (ADR 0287). No commit here: the routes commit.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.activity_log import record_activity
from lorenzo_api.dependencies import set_tenant_rls_context
from lorenzo_api.models import RepositorySubscription, Tenant
from lorenzo_api.notifications import create_tenant_admins_notification
from lorenzo_api.repository_access import reading_repository

__all__ = ["grant_repository_access", "notify_tenant_admins", "subscribe_to_public"]


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
            source="invited",
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


async def subscribe_to_public(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    repository_ids: Sequence[uuid.UUID],
    user_id: uuid.UUID,
) -> list[uuid.UUID]:
    """Gives the library `tenant_id` a grant of its own, `source = public`, to each of the
    public repositories (ADR 0287, RFC 0038 section 3): what copying a public repository does
    for it and for every repository it is built on, on the library's own authority. Each is
    written inside the gated read of that repository, which is where the database lets the
    library see that it is public; one that is not public and published is refused by the
    insert policy. The caller has checked that the library holds no grant to it yet (an
    invitation outranks this, and is left as it is), runs under the library's RLS context, and
    commits. Nothing is said to the repository's Owner here: what they see of a public copy is
    RFC 0038's section 6. Returns the ids written."""
    written: list[uuid.UUID] = []
    for repository_id in repository_ids:
        async with reading_repository(session, repository_id) as readable:
            if not readable:
                continue
            session.add(
                RepositorySubscription(
                    repository_tenant_id=repository_id,
                    subscriber_tenant_id=tenant_id,
                    created_by=user_id,
                    source="public",
                )
            )
            await session.flush()
        written.append(repository_id)
        await record_activity(
            session,
            tenant_id=tenant_id,
            actor_id=user_id,
            action="repository.subscribed",
            target_type="tenant",
            target_id=repository_id,
            detail="source=public",
        )
    return written
