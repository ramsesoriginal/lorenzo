"""Ordered payload writes within an information's existing audience (ADR 0306)."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from lorenzo_api.etag import check_if_match
from lorenzo_api.exceptions import (
    ClientIdUnavailableError,
    PayloadOrderListError,
    PayloadPreconditionRequiredError,
)
from lorenzo_api.models import Information, Payload


def require_bundle_version(information: Information, if_match: str | None) -> None:
    if if_match is None:
        raise PayloadPreconditionRequiredError(detail="Send the information ETag as If-Match.")
    check_if_match(if_match, updated_at=information.updated_at)


def touch_bundle(information: Information) -> None:
    information.updated_at = datetime.now(UTC)


async def payload_replay(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    information_id: uuid.UUID,
    payload_id: uuid.UUID | None,
) -> Payload | None:
    if payload_id is None:
        return None
    payload = await session.scalar(
        select(Payload)
        .where(Payload.id == payload_id, Payload.tenant_id == tenant_id)
        .options(
            selectinload(Payload.description),
            selectinload(Payload.number),
            selectinload(Payload.picture),
            selectinload(Payload.document),
        )
        .execution_options(populate_existing=True)
    )
    if payload is not None and payload.information_id != information_id:
        raise ClientIdUnavailableError(detail="That id is not available.")
    return payload


async def replace_payload_order(
    session: AsyncSession, *, information: Information, wanted: list[uuid.UUID]
) -> bool:
    rows = list(
        await session.scalars(
            select(Payload)
            .where(
                Payload.information_id == information.id, Payload.tenant_id == information.tenant_id
            )
            .order_by(Payload.order, Payload.id)
        )
    )
    if len(wanted) != len(set(wanted)) or set(wanted) != {row.id for row in rows}:
        raise PayloadOrderListError(detail="Keep every payload in the information, each once.")
    if wanted == [row.id for row in rows]:
        return False
    by_id = {row.id: row for row in rows}
    slots = [row.order for row in rows]
    offset = max(slots, default=0) - min(slots, default=0) + len(rows) + 1
    for row in rows:
        row.order += offset
    await session.flush()
    for slot, payload_id in zip(slots, wanted, strict=True):
        by_id[payload_id].order = slot
    touch_bundle(information)
    await session.flush()
    return True
