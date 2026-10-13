"""The gated repository read - ADR 0118, RFC 0024 amendment A1.

A tenant granted a published repository can read its content, but only
inside `reading_repository`. That sets the transaction-local
`app.repository_tenant_id`, which the `repository_read` policy on every
table in REPOSITORY_CONTENT_TABLES checks through the database function
`repository_read_tenant_id()`. Nothing else ever sets it: an ordinary
request, and every query that relies on RLS alone to scope itself, never
sees a repository's rows.
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.copyable_tables import CONTENT_TABLES, EXCLUDED_TABLES

__all__ = [
    "REPOSITORY_CONTENT_TABLES",
    "REPOSITORY_EXCLUDED_TABLES",
    "reading_repository",
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
    session: AsyncSession, repository_tenant_id: uuid.UUID
) -> AsyncIterator[bool]:
    """Reads `repository_tenant_id`'s content for the rest of the block,
    alongside the current tenant's own. Yields whether the read is
    actually allowed - a grant to the current tenant, and published - so
    a route can answer 404 rather than show an empty repository.

    Cleared again on the way out. If the block raises, the transaction is
    failing anyway, and the setting ends with it (it's transaction-local).
    Every query inside still filters on `tenant_id` explicitly, as
    everywhere (ADR 0002): the policy decides what's visible, the filter
    decides what's asked for.
    """
    await session.execute(
        text("SELECT set_config('app.repository_tenant_id', :r, true)"),
        {"r": str(repository_tenant_id)},
    )
    allowed = (await session.execute(text("SELECT repository_read_tenant_id()"))).scalar()
    yield allowed == repository_tenant_id
    await session.execute(text("SELECT set_config('app.repository_tenant_id', '', true)"))
