"""The constraints of calendar-period identities, not a history service."""

from __future__ import annotations

import uuid

from lorenzo_calendar import (
    CalendarDate,
    CalendarDefinition,
    RecurrenceRule,
    segment_for,
    validate_recurrence,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.exceptions import CalendarDefinitionInUseError
from lorenzo_api.models import CalendarObservance, CalendarPeriod


async def validate_materialized_periods(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    calendar_id: uuid.UUID,
    definition: CalendarDefinition,
) -> None:
    from lorenzo_api.models import Calendar, CalendarReckoning

    def mapping(value: CalendarDefinition) -> list[tuple[object, ...]]:
        return [(s.key, s.days, s.when.model_dump() if s.when else None) for s in value.segments]

    old = await session.scalar(
        select(Calendar.definition).where(
            Calendar.entity_id == calendar_id, Calendar.tenant_id == tenant_id
        )
    )
    if (
        old is not None
        and mapping(CalendarDefinition.model_validate(old)) != mapping(definition)
        and await session.scalar(
            select(CalendarReckoning.calendar_entity_id)
            .where(
                CalendarReckoning.tenant_id == tenant_id,
                CalendarReckoning.calendar_entity_id == calendar_id,
            )
            .limit(1)
        )
    ):
        raise CalendarDefinitionInUseError(
            detail="Review and remove reckonings before changing this calendar's day mapping"
        )
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

    rules = (
        await session.scalars(
            select(CalendarObservance).where(
                CalendarObservance.tenant_id == tenant_id,
                CalendarObservance.calendar_entity_id == calendar_id,
            )
        )
    ).all()
    for observance in rules:
        try:
            validate_recurrence(definition, RecurrenceRule.model_validate(observance.rule))
        except ValueError:
            raise CalendarDefinitionInUseError(
                detail="This definition would invalidate a recurring observance. "
                "Resolve its rule first."
            ) from None
