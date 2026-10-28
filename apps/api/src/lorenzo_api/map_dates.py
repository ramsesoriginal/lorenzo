"""The date lens on the Maps list (ADR 0372): is a Map tied to a date, to other dates, or to none,
as the reader sees it.

Read only, over the existing `entry_calendar_period`. An association counts when the reader sees its
period and its calendar; matching goes through the periods that contain the date (ADR 0371), never
through numbers between. Two `EXISTS` tests in the list's own statement, no recursion.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from lorenzo_calendar import PeriodCoordinate, containing_periods
from pydantic import ValidationError
from sqlalchemy import ColumnElement, and_, case, exists, literal, or_, select

from lorenzo_api.entry_visibility import visible_entry_clause
from lorenzo_api.exceptions import InvalidMapError
from lorenzo_api.information_visibility import InformationVisibility
from lorenzo_api.models import CalendarPeriod, Entity, EntryCalendarPeriod


@dataclass(frozen=True)
class DateLens:
    """The two tests and what the list orders by."""

    tied: ColumnElement[bool]
    associated: ColumnElement[bool]

    @property
    def label(self) -> Any:
        return case((self.tied, "tied"), (self.associated, "other"), else_="untied")

    @property
    def order(self) -> Any:
        return case((self.tied, 0), (self.associated, 2), else_=1)

    @property
    def other_only(self) -> ColumnElement[bool]:
        return self.associated & ~self.tied


def coordinate_of(year: int | None, segment: str | None, day: int | None) -> PeriodCoordinate:
    """The date asked for, or a refusal in words."""
    if year is None:
        raise InvalidMapError(detail="A date needs its year")
    try:
        return PeriodCoordinate(year=year, segment=segment, day=day)
    except ValidationError as error:
        first = error.errors()[0]
        raise InvalidMapError(detail=f"That is not a date: {first['msg']}") from None


def date_lens(
    vis: InformationVisibility,
    *,
    tenant_id: uuid.UUID,
    calendar_id: uuid.UUID,
    coordinate: PeriodCoordinate,
) -> DateLens:
    def exists_for(*extra: ColumnElement[bool]) -> ColumnElement[bool]:
        return exists(
            select(literal(1))
            .select_from(EntryCalendarPeriod)
            .join(CalendarPeriod, CalendarPeriod.entity_id == EntryCalendarPeriod.period_entity_id)
            .where(
                EntryCalendarPeriod.entity_id == Entity.id,
                EntryCalendarPeriod.tenant_id == tenant_id,
                visible_entry_clause(vis, CalendarPeriod.entity_id),
                visible_entry_clause(vis, CalendarPeriod.calendar_entity_id),
                *extra,
            )
        )

    contained = [
        and_(
            CalendarPeriod.year == period.year,
            CalendarPeriod.segment.is_(None)
            if period.segment is None
            else CalendarPeriod.segment == period.segment,
            CalendarPeriod.day.is_(None)
            if period.day is None
            else CalendarPeriod.day == period.day,
        )
        for period in containing_periods(coordinate)
    ]
    return DateLens(
        tied=exists_for(CalendarPeriod.calendar_entity_id == calendar_id, or_(*contained)),
        associated=exists_for(),
    )
