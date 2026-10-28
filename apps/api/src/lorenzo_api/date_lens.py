"""The date lens on the entry lists (ADR 0372, 0374): is an entry tied to a date, to other dates, or
to none, as the reader sees it.

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

from lorenzo_api.dependencies import CurrentUser, SessionDep
from lorenzo_api.entry_visibility import require_visible_entry, visible_entry_clause
from lorenzo_api.exceptions import EntityNotFoundError, InvalidDateError
from lorenzo_api.information_visibility import InformationVisibility
from lorenzo_api.models import Calendar, CalendarPeriod, Entity, EntryCalendarPeriod

_NO_CALENDAR = "No such Calendar in this library"


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
        raise InvalidDateError(detail="A date needs its year")
    try:
        return PeriodCoordinate(year=year, segment=segment, day=day)
    except ValidationError as error:
        first = error.errors()[0]
        raise InvalidDateError(detail=f"That is not a date: {first['msg']}") from None


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


async def lens_for_request(
    session: SessionDep,
    vis: InformationVisibility,
    user: CurrentUser,
    *,
    tenant_id: uuid.UUID,
    calendar_id: uuid.UUID | None,
    year: int | None,
    segment: str | None,
    day: int | None,
    exclude_other: bool,
) -> DateLens | None:
    """The lens a list was asked through, or None when it was not asked for one. The one place the
    Maps list and the Locations list validate a date, so they answer alike (ADR 0374)."""
    if calendar_id is None:
        if any(v is not None for v in (year, segment, day)) or exclude_other:
            raise InvalidDateError(detail="A date needs its Calendar")
        return None
    coordinate = coordinate_of(year, segment, day)
    try:
        await require_visible_entry(
            session, tenant_id=tenant_id, entity_id=calendar_id, user_id=user.id
        )
    except EntityNotFoundError:
        raise EntityNotFoundError(detail=_NO_CALENDAR) from None
    if await session.get(Calendar, calendar_id) is None:
        raise EntityNotFoundError(detail=_NO_CALENDAR)
    return date_lens(vis, tenant_id=tenant_id, calendar_id=calendar_id, coordinate=coordinate)
