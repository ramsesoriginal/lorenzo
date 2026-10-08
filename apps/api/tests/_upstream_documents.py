"""What the release document tests do to the engines (ADR 0214): answer `load_content` from a
document where the engines read a repository, and compare what they say with what they say
from the rows. R6 makes the switch in the code; until then it is made here.
"""

import copy
import itertools
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import lorenzo_api.repository_copying as copying
import lorenzo_api.repository_updates as updating
from lorenzo_api.repository_content import Content


@contextmanager
def upstream_from(documents: dict[uuid.UUID, Content]) -> Iterator[None]:
    """`plan_copy` and `compute_updates` each read a repository through `load_content`; for the
    repositories named, it answers with a copy of the document's content, for every other
    tenant (the library) from the rows."""
    real = copying.load_content

    async def load(session: AsyncSession, tenant_id: uuid.UUID) -> Content:
        if tenant_id in documents:
            return copy.deepcopy(documents[tenant_id])
        return await real(session, tenant_id)

    copying.load_content = load  # type: ignore[assignment]
    updating.load_content = load  # type: ignore[assignment]
    try:
        yield
    finally:
        copying.load_content = real
        updating.load_content = real


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
