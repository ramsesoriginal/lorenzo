"""One transaction lock for all mutations of a tenant's Event assertions (ADR 0312)."""

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def lock_event_order(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    # The database trigger uses this exact namespace too. Acquire before opening
    # the INSERT statement's READ COMMITTED snapshot, not just inside its trigger.
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended('lorenzo:event-order:' || :t, 0))"),
        {"t": str(tenant_id)},
    )
