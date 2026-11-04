"""How many libraries still hold a copy of a row of this repository - ADR 0386.

The links that say who copied what are rows of the copying library, under its own policy. The
repository reads them through `repository_owner_count`, which is open only while `app.library_count`
is `on`; `count_libraries` is the one place that sets it, for the one query, and selects `count(*)`
and nothing else, so no name or id of a library is ever read.
"""

import uuid
from typing import Any, Literal

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.models import (
    RepositoryCopyLinkEntity,
    RepositoryCopyLinkStatDefinition,
    RepositoryCopyLinkStatGroup,
    Tenant,
    TenantKind,
)

__all__ = ["LibraryKind", "count_libraries", "libraries_note"]

LibraryKind = Literal["entity", "stat_group", "stat_definition"]

# Each kind's link table and the column that is null once the library deleted its copy.
_LINKS: dict[str, tuple[Any, Any]] = {
    "entity": (RepositoryCopyLinkEntity, RepositoryCopyLinkEntity.entity_id),
    "stat_group": (RepositoryCopyLinkStatGroup, RepositoryCopyLinkStatGroup.stat_group_id),
    "stat_definition": (
        RepositoryCopyLinkStatDefinition,
        RepositoryCopyLinkStatDefinition.stat_definition_id,
    ),
}


async def count_libraries(
    session: AsyncSession, tenant_id: uuid.UUID, kind: LibraryKind, source_id: uuid.UUID
) -> int:
    """The tenants that hold a copy of the row `source_id` of the repository `tenant_id`: the
    links to it whose copy still exists, `merged` ones included. A tenant that is not a
    repository has nothing copied from it, so it is 0 without a query."""
    tenant = await session.get(Tenant, tenant_id)
    if tenant is None or tenant.kind is not TenantKind.REPOSITORY:
        return 0
    link, local = _LINKS[kind]
    await session.execute(text("SELECT set_config('app.library_count', 'on', true)"))
    try:
        count = await session.scalar(
            select(func.count())
            .select_from(link)
            .where(
                link.source_tenant_id == tenant_id,
                link.source_id == source_id,
                local.is_not(None),
            )
        )
    finally:
        await session.execute(text("SELECT set_config('app.library_count', '', true)"))
    return count or 0


def libraries_note(count: int) -> str:
    """The words a delete adds to its activity entry: quiet for the common case of none."""
    return f", libraries={count}" if count else ""
