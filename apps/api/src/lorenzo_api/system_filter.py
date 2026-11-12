"""The `system` filter of the stat reads - ADR 0450, RFC 0052.

A library that holds the stats of several game systems answers an entry's stats whole, as ever.
`?system=<slug>` narrows the answer to what a table of that system uses: the stats that belong to
no system, and that system's. It is a view, not a resolution: every value is still resolved over
the whole prototype graph and every formula evaluated, so a stat reads the same with the filter
as without it.
"""

import uuid
from collections.abc import Sequence
from typing import Annotated, Protocol

from fastapi import Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.exceptions import SystemNotFoundError
from lorenzo_api.models import System

__all__ = ["SystemFilter", "only_system", "require_system_slug"]

SystemFilter = Annotated[
    str | None,
    Query(
        max_length=64,
        description=(
            "The slug of a game system of the library: only the stats that belong to no system "
            "and that system's. Left out, every stat. An unknown slug is a 404."
        ),
    ),
]


class _HasSystem(Protocol):
    @property
    def system(self) -> str | None: ...


async def require_system_slug(
    session: AsyncSession, tenant_id: uuid.UUID, slug: str | None
) -> None:
    """404 for a slug that is not a system of the library; nothing for no filter."""
    if slug is None:
        return
    found = await session.scalar(
        select(System.id).where(System.tenant_id == tenant_id, System.slug == slug)
    )
    if found is None:
        raise SystemNotFoundError(detail=f"No system with slug {slug!r} in tenant {tenant_id}")


def only_system[T: _HasSystem](stats: Sequence[T], slug: str | None) -> list[T]:
    """The stats of no system and of `slug`, in their order; all of them without a filter."""
    if slug is None:
        return list(stats)
    return [stat for stat in stats if stat.system is None or stat.system == slug]
