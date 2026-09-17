"""Shared activity-log recording - see ADR 0063.

Core mechanics only - no auth, no commit (matching lorenzo_api.
notifications' own shape) - each mutation route calls `record_activity`
before its own commit, while `app.tenant_id` is still the value
`dependencies.get_tenant_context` set at dependency-resolution time (see
`AuditLog`'s own docstring for why that ordering matters: this table's RLS
is a plain `tenant_id = app.tenant_id` policy, with no self-access clause
the way `notification` needed one).
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.models import AuditLog


async def record_activity(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    action: str,
    target_type: str,
    target_id: uuid.UUID | None,
    detail: str | None = None,
) -> None:
    session.add(
        AuditLog(
            tenant_id=tenant_id,
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
        )
    )
