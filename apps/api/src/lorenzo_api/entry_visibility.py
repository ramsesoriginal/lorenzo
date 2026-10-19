"""The existence/name gate, separate from an information audience (ADR 0305)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ColumnElement, exists, or_, select, text, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from lorenzo_api.entity_access import entity_id_among
from lorenzo_api.models import CalendarPeriod, EntityAudience, EntityKnowledge

if TYPE_CHECKING:
    from lorenzo_api.information_visibility import InformationVisibility


def _own_visible_entry_clause(
    vis: InformationVisibility,
    entity_id: ColumnElement[uuid.UUID] | InstrumentedAttribute[uuid.UUID],
) -> ColumnElement[bool]:
    if vis.is_admin or vis.author_sees_all:
        return true()
    recipients = []
    if vis.player_ids:
        recipients.append(entity_id_among(EntityKnowledge.knower_player_id, vis.player_ids))
    if vis.knower_entity_ids:
        recipients.append(entity_id_among(EntityKnowledge.knower_entity_id, vis.knower_entity_ids))
    allowed: list[ColumnElement[bool]] = [EntityAudience.is_public.is_(True)]
    if vis.gm_reachable_entity_ids:
        allowed.append(entity_id_among(EntityAudience.entity_id, vis.gm_reachable_entity_ids))
    if vis.author_entry_ids:
        allowed.append(entity_id_among(EntityAudience.entity_id, vis.author_entry_ids))
    if recipients:
        allowed.append(
            exists().where(EntityKnowledge.entity_id == EntityAudience.entity_id, or_(*recipients))
        )
    return ~exists().where(EntityAudience.entity_id == entity_id, ~or_(*allowed))


def visible_entry_clause(
    vis: InformationVisibility,
    entity_id: ColumnElement[uuid.UUID] | InstrumentedAttribute[uuid.UUID],
) -> ColumnElement[bool]:
    own = _own_visible_entry_clause(vis, entity_id)
    return own & ~exists().where(
        CalendarPeriod.entity_id == entity_id,
        ~_own_visible_entry_clause(vis, CalendarPeriod.calendar_entity_id),
    )


async def require_visible_entry(
    session: AsyncSession,
    *,
    entity_id: uuid.UUID,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> None:
    # Internal copy/planning reads have no caller and retain the repository read contract.
    if user_id is not None:
        session.info["entry_reader_user_id"] = user_id
    user_id = user_id or session.info.get("entry_reader_user_id")
    checked = session.info.setdefault("visible_entry_checks", set())
    key = (tenant_id, entity_id, user_id)
    if key in checked:
        return
    gate = await session.scalar(
        select(EntityAudience.entity_id).where(
            EntityAudience.entity_id == entity_id,
            EntityAudience.tenant_id == tenant_id,
            or_(
                EntityAudience.is_public.is_(False),
                exists().where(CalendarPeriod.entity_id == entity_id),
            ),
        )
    )
    if gate is None:
        checked.add(key)
        return
    if user_id is None:
        raw = await session.scalar(text("SELECT current_setting('app.user_id', true)"))
        if not raw:
            return
        user_id = uuid.UUID(raw)
    from lorenzo_api.exceptions import EntityNotFoundError
    from lorenzo_api.information_visibility import resolve_information_visibility

    vis = await resolve_information_visibility(session, user_id=user_id, tenant_id=tenant_id)
    if entity_id in vis.hidden_entry_ids:
        raise EntityNotFoundError(detail=f"No entity with id {entity_id} in tenant {tenant_id}")
    checked.add(key)
