"""The single write path for description text - see ADR 0101.

Every creation or change of a `payload_description` row goes through
`write_description`: `create_information` (routers/entities.py) and
`PATCH .../payloads/{id}` (routers/payloads.py) both call it, and nothing
else writes that table. It also keeps the payload's `content_reference`
rows in step with the text (ADR 0110), so a new caller must not write
PayloadDescription directly.

`content` is stored exactly as given. The server reads it as LorenzoScript
(RFC 0027) only to record its references; it never rejects or changes it.
"""

from __future__ import annotations

from sqlalchemy import delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.lorenzoscript import references
from lorenzo_api.models import ContentReference, Payload, PayloadDescription

# No slug is longer (ADR 0107), so a longer target could never resolve, and
# isn't kept (ADR 0110).
_MAX_SLUG = 100


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
        session.add_all(_references(payload, content))
        return description

    changed = False
    if content is not None and content != description.content:
        description.content = content
        await session.execute(
            delete(ContentReference).where(ContentReference.payload_id == payload.id)
        )
        session.add_all(_references(payload, content))
        changed = True
    if locale is not None and locale != description.locale:
        description.locale = locale
        changed = True
    if changed:
        payload.updated_at = func.now()
    return description


def _references(payload: Payload, content: str) -> list[ContentReference]:
    """`content`'s references as rows, in order of first use. Attached through
    the relationship, like the description, so a new payload works too."""
    rows: list[ContentReference] = []
    for ref in references(content):
        if ref["kind"] in ("entity", "image"):
            hint, target = ref["hint"], ref["slug"]
            if len(target) > _MAX_SLUG:
                continue
        else:
            hint, target = "", ref.get("date") or ref["expression"]
        rows.append(
            ContentReference(
                payload=payload,
                position=len(rows),
                tenant_id=payload.tenant_id,
                kind=ref["kind"],
                hint=hint,
                target=target,
            )
        )
    return rows
