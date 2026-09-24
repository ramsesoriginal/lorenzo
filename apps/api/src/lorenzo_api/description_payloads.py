"""The single write path for description text - see ADR 0101.

Every creation or change of a `payload_description` row goes through
`write_description`: `create_information` (routers/entities.py) and
`PATCH .../payloads/{id}` (routers/payloads.py) both call it, and nothing
else writes that table. RFC 0027 stage 7 hooks its reference extractor in
here, so a new caller must not write PayloadDescription directly.

`content` is stored exactly as given. LorenzoScript (RFC 0027) is a
client-side convention; the server doesn't parse or validate it.
"""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.models import Payload, PayloadDescription


async def write_description(
    session: AsyncSession,
    *,
    payload: Payload,
    content: str | None,
    locale: str | None,
) -> PayloadDescription:
    """Creates `payload`'s description row, or updates the existing one.

    `payload.description` must already be loaded, or `payload` must be
    new and not yet flushed (a pending object reads it as None without a
    query). On create both `content` and `locale` are required. On update
    a `None` argument leaves that field unchanged, so a PATCH only passes
    what was sent.

    Bumps `payload.updated_at` on update. A change to `payload_description`
    alone never touches the parent row, and the payload's ETag (ADR 0042)
    derives from the parent's `updated_at`.
    """
    description = payload.description
    if description is None:
        if content is None or locale is None:
            raise ValueError("a new description needs both content and locale")
        # Attached through the relationship, so the flush fills in
        # payload_id once the payload itself has one.
        description = PayloadDescription(
            tenant_id=payload.tenant_id, locale=locale, content=content
        )
        payload.description = description
        session.add(payload)
        return description

    changed = False
    if content is not None and content != description.content:
        description.content = content
        changed = True
    if locale is not None and locale != description.locale:
        description.locale = locale
        changed = True
    if changed:
        payload.updated_at = func.now()
    return description
