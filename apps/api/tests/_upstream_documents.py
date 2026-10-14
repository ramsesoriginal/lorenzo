"""What the release document tests do to the engines (ADR 0214, ADR 0286): make the repositories
named public, so the engines read their current release's document, and put them back. Their
`Content` is what `load_upstream` answers; every other tenant (the library) is read from the rows.
"""

import itertools
import uuid
from collections.abc import AsyncIterator, Iterable, Iterator
from contextlib import asynccontextmanager, contextmanager

from _admin_db import admin_session_factory
from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.models import RepositoryProfile


async def set_visibility(repositories: Iterable[uuid.UUID], visibility: str) -> None:
    """The repositories' visibility, written straight in the database: the API refuses `public`
    until the rest of RFC 0038 is built."""
    async with admin_session_factory() as session:
        await session.execute(
            update(RepositoryProfile)
            .where(RepositoryProfile.tenant_id.in_(list(repositories)))
            .values(visibility=visibility)
        )
        await session.commit()


@asynccontextmanager
async def read_as_public(repositories: Iterable[uuid.UUID]) -> AsyncIterator[None]:
    """`plan_copy` and `compute_updates` read each of the repositories through its current
    release's document, as they do for a public repository."""
    named = list(repositories)
    await set_visibility(named, "public")
    try:
        yield
    finally:
        await set_visibility(named, "private")


@contextmanager
def deterministic_ids() -> Iterator[None]:
    """Every new id the planner makes is the next number, so two plans are comparable."""
    counter = itertools.count(1)
    real = uuid.uuid4
    uuid.uuid4 = lambda: uuid.UUID(int=next(counter))  # type: ignore[assignment]
    try:
        yield
    finally:
        uuid.uuid4 = real


async def in_tenant(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    """The rest of the transaction runs as a member of this tenant (RLS, ADR 0002)."""
    await session.execute(
        text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)}
    )
