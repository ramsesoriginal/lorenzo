"""What the SocialWeb routes share: the closed lists and the limits (ADR 0406)."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.exceptions import InvalidSocialWebError
from lorenzo_api.models import SocialWebEntry, SocialWebType

#: The layouts a web may name: a closed list (ADR 0407). The engines live in the renderer package.
Layout = Literal["circle", "radial", "stress", "forceatlas2", "manual", "layered"]
LAYOUTS: tuple[str, ...] = ("circle", "radial", "stress", "forceatlas2", "manual", "layered")

#: A web shows at most this many entries and limits itself to at most this many types
#: (*proposed defaults*).
MAX_MEMBERS = 500
MAX_TYPES = 50
#: One bulk write takes at most this many rows.
MAX_BULK_ROWS = 100
#: A graph read returns at most this many edges, and says so when it stopped.
MAX_EDGES = 5_000
#: The saved visual switches stay small.
MAX_VIEW_BYTES = 4_096


def holds_no_entry_id(value: Any) -> bool:
    """Whether a JSON value has no string that reads as an id: `view` is visual only and never
    holds an entry id or anything the server reads (ADR 0406)."""
    if isinstance(value, dict):
        return all(holds_no_entry_id(k) and holds_no_entry_id(v) for k, v in value.items())
    if isinstance(value, list):
        return all(holds_no_entry_id(v) for v in value)
    if isinstance(value, str):
        try:
            uuid.UUID(value)
        except ValueError:
            return True
        return False
    return True


async def require_member_room(
    session: AsyncSession, *, web_id: uuid.UUID, tenant_id: uuid.UUID, adding: int
) -> None:
    """Refuses members beyond the cap: `adding` more than the web holds now."""
    count = await session.scalar(
        select(func.count())
        .select_from(SocialWebEntry)
        .where(SocialWebEntry.tenant_id == tenant_id, SocialWebEntry.web_entity_id == web_id)
    )
    if (count or 0) + adding > MAX_MEMBERS:
        raise InvalidSocialWebError(detail=f"A web shows at most {MAX_MEMBERS} entries.")


async def type_count(session: AsyncSession, *, web_id: uuid.UUID, tenant_id: uuid.UUID) -> int:
    return (
        await session.scalar(
            select(func.count())
            .select_from(SocialWebType)
            .where(SocialWebType.tenant_id == tenant_id, SocialWebType.web_entity_id == web_id)
        )
        or 0
    )
