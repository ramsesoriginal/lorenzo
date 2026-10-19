"""The constraints of calendar-period identities, not a history service."""

from __future__ import annotations

import uuid

from lorenzo_calendar import CalendarDate, CalendarDefinition, segment_for
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.exceptions import CalendarDefinitionInUseError
from lorenzo_api.models import CalendarPeriod


async def validate_materialized_periods(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    calendar_id: uuid.UUID,
    definition: CalendarDefinition,
) -> None:
    periods = (
        await session.scalars(
            select(CalendarPeriod).where(
                CalendarPeriod.tenant_id == tenant_id,
                CalendarPeriod.calendar_entity_id == calendar_id,
            )
        )
    ).all()
    for period in periods:
        if period.segment is not None:
            try:
                segment_for(
                    definition,
                    CalendarDate(year=period.year, segment=period.segment, day=period.day or 1),
                )
            except ValueError:
                raise CalendarDefinitionInUseError(
                    detail="This definition would invalidate a recorded calendar period. "
                    "Resolve its references first."
                ) from None
