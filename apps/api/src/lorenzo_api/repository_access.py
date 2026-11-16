"""The gated repository read - ADR 0118, RFC 0024 amendment A1.

A tenant granted a published repository can read its content, but only
inside `reading_repository`. That sets the transaction-local
`app.repository_tenant_id`, which the `repository_read` policy on every
table in REPOSITORY_CONTENT_TABLES checks through the database function
`repository_read_tenant_id()`. Nothing else ever sets it: an ordinary
request, and every query that relies on RLS alone to scope itself, never
sees a repository's rows.

A protected repository (ADR 0434) is read a second way, and only through the repository whose copy
the reader is making or holds: `reading_repository(..., via=...)` also sets
`app.repository_via`, and the database function `repository_reached_through_another()` says
whether that repository, a public one whose current release lists this one, lets the reader in.
`reading_repository_held` is the form for a reader that holds the repository already: it goes
through each of the repositories it holds that could, until one does.
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.copyable_tables import CONTENT_TABLES, EXCLUDED_TABLES
from lorenzo_api.models import RepositoryCopy, RepositorySubscription, Tenant

__all__ = [
    "REPOSITORY_CONTENT_TABLES",
    "REPOSITORY_EXCLUDED_TABLES",
    "reaching_repositories",
    "reading_repository",
    "reading_repository_held",
]

# Every tenant table that can hold a repository's own content, and so carries the repository_read
# policy (RFC 0024 section 4, amendment A3), and every other one: relative to a player, a campaign
# or tenant administration, none of which a repository has, or the copying tenant's own
# bookkeeping. Both come from the registry of copyable tables (ADR 0218), which a test holds to the
# database: a tenant table in neither set, or a policy on the wrong one, fails it.
REPOSITORY_CONTENT_TABLES = CONTENT_TABLES
REPOSITORY_EXCLUDED_TABLES = EXCLUDED_TABLES


@asynccontextmanager
async def reading_repository(
    session: AsyncSession, repository_tenant_id: uuid.UUID, *, via: uuid.UUID | None = None
) -> AsyncIterator[bool]:
    """Reads `repository_tenant_id`'s content for the rest of the block,
    alongside the current tenant's own. Yields whether the read is
    actually allowed - a grant to the current tenant, and published - so
    a route can answer 404 rather than show an empty repository.

    `via` is the repository the reader is going through to reach a protected one (ADR 0434): the
    public repository whose copy it is making or holds. It lets in nothing else: a repository that
    is not protected is read as it always was, and a protected one only when `via` is a public,
    published repository whose current release lists it.

    Cleared again on the way out. If the block raises, the transaction is
    failing anyway, and the setting ends with it (it's transaction-local).
    Every query inside still filters on `tenant_id` explicitly, as
    everywhere (ADR 0002): the policy decides what's visible, the filter
    decides what's asked for.
    """
    await session.execute(
        text(
            "SELECT set_config('app.repository_tenant_id', :r, true), "
            "set_config('app.repository_via', :v, true)"
        ),
        {"r": str(repository_tenant_id), "v": str(via) if via else ""},
    )
    allowed = (await session.execute(text("SELECT repository_read_tenant_id()"))).scalar()
    yield allowed == repository_tenant_id
    await session.execute(
        text(
            "SELECT set_config('app.repository_tenant_id', '', true), "
            "set_config('app.repository_via', '', true)"
        )
    )


async def reaching_repositories(
    session: AsyncSession, repository_tenant_id: uuid.UUID
) -> list[uuid.UUID]:
    """The repositories the current tenant holds a grant to whose current release lists
    `repository_tenant_id`, public ones, by id: the ones it can go through to read it if it is
    protected (ADR 0434). The database is asked again before anything is read."""
    tenant = (
        await session.execute(
            text("SELECT NULLIF(current_setting('app.tenant_id', true), '')::uuid")
        )
    ).scalar()
    if tenant is None:
        return []
    held = or_(
        Tenant.id.in_(
            select(RepositorySubscription.repository_tenant_id).where(
                RepositorySubscription.subscriber_tenant_id == tenant
            )
        ),
        Tenant.id.in_(
            select(RepositoryCopy.repository_tenant_id).where(RepositoryCopy.tenant_id == tenant)
        ),
    )
    return list(
        await session.scalars(
            select(Tenant.id)
            .where(
                Tenant.released_public.is_(True),
                Tenant.released_over.contains([repository_tenant_id]),
                held,
            )
            .order_by(Tenant.id)
        )
    )


@asynccontextmanager
async def reading_repository_held(
    session: AsyncSession, repository_tenant_id: uuid.UUID
) -> AsyncIterator[bool]:
    """`reading_repository` for a reader that holds the repository (or is built on it): through
    the grant it has to it, if it has one, and otherwise through each public repository it holds
    whose current release lists it, until the database lets it in (ADR 0434). Yields whether it
    was allowed. What a protected repository is to a library that never reads it any other way:
    its updates, the skew gate and the list of what it holds."""
    async with reading_repository(session, repository_tenant_id) as allowed:
        if allowed:
            yield True
            return
    # Only a reader the grant does not let in asks which repositories it could go through.
    for via in await reaching_repositories(session, repository_tenant_id):
        async with reading_repository(session, repository_tenant_id, via=via) as allowed:
            if allowed:
                yield True
                return
    yield False
