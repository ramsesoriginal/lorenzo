"""Period materialization and entry-date associations (ADR 0309)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal, Self

from fastapi import APIRouter, Depends, Header, Query, Response
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from lorenzo_calendar import CalendarDate, CalendarDefinition, segment_for
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import delete, select

from lorenzo_api.activity_log import record_activity
from lorenzo_api.dependencies import (
    CurrentUser,
    ParamsDep,
    SessionDep,
    get_tenant_or_404,
    require_tenant_participant,
    set_tenant_rls_context,
)
from lorenzo_api.entry_visibility import require_visible_entry, visible_entry_clause
from lorenzo_api.etag import check_if_match, etag_for
from lorenzo_api.exceptions import (
    AudiencePreconditionRequiredError,
    EntityNotFoundError,
    InvalidCalendarDateError,
)
from lorenzo_api.information_visibility import resolve_information_visibility
from lorenzo_api.models import CalendarPeriod, Entity, EntityAudience, EntryCalendarPeriod
from lorenzo_api.routers.calendars import read_calendar
from lorenzo_api.routers.entities import authorize_entity_write

router = APIRouter(
    prefix="/tenants/{tenant_id}",
    tags=["calendar periods"],
    dependencies=[Depends(get_tenant_or_404)],
)


class PeriodCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    year: int = Field(strict=True, ge=-1000000, le=1000000)
    segment: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9-]{0,63}$")
    day: int | None = Field(default=None, strict=True, ge=1, le=1000)
    is_public: bool = False

    @model_validator(mode="after")
    def shape(self) -> Self:
        if self.day is not None and self.segment is None:
            raise ValueError("A day needs its segment")
        return self


class PeriodOut(BaseModel):
    entity_id: uuid.UUID
    calendar_entity_id: uuid.UUID
    name: str
    granularity: Literal["year", "month", "day"]
    year: int
    segment: str | None
    day: int | None
    parent_entity_id: uuid.UUID | None


class PeriodSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    period_ids: list[uuid.UUID] = Field(max_length=1000)


class DatedEntryOut(BaseModel):
    entity_id: uuid.UUID
    name: str


def period_out(period: CalendarPeriod, entity: Entity) -> PeriodOut:
    return PeriodOut(
        entity_id=period.entity_id,
        calendar_entity_id=period.calendar_entity_id,
        name=entity.name,
        year=period.year,
        segment=period.segment,
        day=period.day,
        granularity="day"
        if period.day is not None
        else "month"
        if period.segment is not None
        else "year",
        parent_entity_id=period.parent_entity_id,
    )


async def materialize(
    session: SessionDep,
    user: CurrentUser,
    tenant_id: uuid.UUID,
    calendar_id: uuid.UUID,
    body: PeriodCreate,
) -> tuple[CalendarPeriod, Entity]:
    calendar, calendar_entry = await read_calendar(session, user, tenant_id, calendar_id, lock=True)
    await authorize_entity_write(session, entity_id=calendar_id, tenant_id=tenant_id, user=user)
    definition = CalendarDefinition.model_validate(calendar.definition)
    if body.segment is not None:
        try:
            segment = segment_for(
                definition, CalendarDate(year=body.year, segment=body.segment, day=body.day or 1)
            )
        except ValueError:
            raise InvalidCalendarDateError(
                detail="This date does not exist in the calendar"
            ) from None
    coordinates: list[tuple[str | None, int | None]] = [(None, None)]
    if body.segment is not None:
        coordinates.append((body.segment, None))
    if body.day is not None:
        coordinates.append((body.segment, body.day))
    parent = None
    for segment_key, day in coordinates:
        query = (
            select(CalendarPeriod, Entity)
            .join(Entity, Entity.id == CalendarPeriod.entity_id)
            .where(
                CalendarPeriod.calendar_entity_id == calendar_id,
                CalendarPeriod.tenant_id == tenant_id,
                CalendarPeriod.year == body.year,
                CalendarPeriod.segment.is_not_distinct_from(segment_key),
                CalendarPeriod.day.is_not_distinct_from(day),
            )
        )
        row = (await session.execute(query)).first()
        if row is not None:
            period, entry = row
            await require_visible_entry(
                session, entity_id=entry.id, tenant_id=tenant_id, user_id=user.id
            )
        else:
            label = (
                f"{calendar_entry.name} {body.year}"
                if segment_key is None
                else f"{segment.name} {body.year}"
                if day is None
                else f"{day} {segment.name} {body.year}"
            )
            entry = Entity(tenant_id=tenant_id, name=label, created_by=user.id, updated_by=user.id)
            session.add(entry)
            await session.flush()
            period = CalendarPeriod(
                entity_id=entry.id,
                tenant_id=tenant_id,
                calendar_entity_id=calendar_id,
                year=body.year,
                segment=segment_key,
                day=day,
                parent_entity_id=parent,
            )
            session.add_all(
                [
                    period,
                    EntityAudience(
                        entity_id=entry.id, tenant_id=tenant_id, is_public=body.is_public
                    ),
                ]
            )
            await session.flush()
            await record_activity(
                session,
                tenant_id=tenant_id,
                actor_id=user.id,
                action="calendar.period_materialized",
                target_type="entity",
                target_id=entry.id,
            )
        parent = entry.id
    return period, entry


@router.post("/calendars/{calendar_id}/periods")
async def materialize_period(
    tenant_id: uuid.UUID,
    calendar_id: uuid.UUID,
    body: PeriodCreate,
    session: SessionDep,
    user: CurrentUser,
    response: Response,
) -> PeriodOut:
    period, entry = await materialize(session, user, tenant_id, calendar_id, body)
    result = period_out(period, entry)
    await session.commit()
    return result


@router.get("/calendars/{calendar_id}/periods")
async def list_periods(
    tenant_id: uuid.UUID,
    calendar_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    params: ParamsDep,
    year: Annotated[int | None, Query(ge=-1000000, le=1000000)] = None,
) -> Page[PeriodOut]:
    from typing import cast

    await read_calendar(session, user, tenant_id, calendar_id)
    vis = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    query = (
        select(CalendarPeriod, Entity)
        .join(Entity, Entity.id == CalendarPeriod.entity_id)
        .where(
            CalendarPeriod.calendar_entity_id == calendar_id,
            CalendarPeriod.tenant_id == tenant_id,
            visible_entry_clause(vis, CalendarPeriod.entity_id),
        )
        .order_by(CalendarPeriod.year, CalendarPeriod.segment, CalendarPeriod.day)
    )
    if year is not None:
        query = query.where(CalendarPeriod.year == year)
    result = await apaginate(
        session, query, params, transformer=lambda rows: [period_out(p, e) for p, e in rows]
    )
    return cast(Page[PeriodOut], result)


@router.get("/entities/{entity_id}/dates")
async def list_entry_dates(
    tenant_id: uuid.UUID, entity_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> list[PeriodOut]:
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    await require_visible_entry(session, entity_id=entity_id, tenant_id=tenant_id, user_id=user.id)
    if (
        await session.scalar(
            select(Entity.id).where(Entity.id == entity_id, Entity.tenant_id == tenant_id)
        )
        is None
    ):
        raise EntityNotFoundError(detail="No entry with that id in this library")
    vis = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    rows = await session.execute(
        select(CalendarPeriod, Entity)
        .join(Entity, Entity.id == CalendarPeriod.entity_id)
        .join(EntryCalendarPeriod, EntryCalendarPeriod.period_entity_id == CalendarPeriod.entity_id)
        .where(
            EntryCalendarPeriod.entity_id == entity_id,
            EntryCalendarPeriod.tenant_id == tenant_id,
            visible_entry_clause(vis, CalendarPeriod.entity_id),
        )
        .order_by(
            CalendarPeriod.calendar_entity_id,
            CalendarPeriod.year,
            CalendarPeriod.segment,
            CalendarPeriod.day,
        )
    )
    return [period_out(p, e) for p, e in rows]


@router.put("/entities/{entity_id}/dates")
async def replace_entry_dates(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    body: PeriodSelection,
    session: SessionDep,
    user: CurrentUser,
    response: Response,
    if_match: Annotated[str | None, Header()] = None,
) -> list[PeriodOut]:
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    await require_visible_entry(session, entity_id=entity_id, tenant_id=tenant_id, user_id=user.id)
    await authorize_entity_write(session, entity_id=entity_id, tenant_id=tenant_id, user=user)
    wanted = set(body.period_ids)
    periods = (
        await session.scalars(
            select(CalendarPeriod).where(
                CalendarPeriod.entity_id.in_(wanted), CalendarPeriod.tenant_id == tenant_id
            )
        )
    ).all()
    existing_periods = (
        await session.scalars(
            select(CalendarPeriod)
            .join(
                EntryCalendarPeriod,
                EntryCalendarPeriod.period_entity_id == CalendarPeriod.entity_id,
            )
            .where(
                EntryCalendarPeriod.entity_id == entity_id,
                EntryCalendarPeriod.tenant_id == tenant_id,
            )
        )
    ).all()
    lock_ids = (
        {entity_id}
        | {p.calendar_entity_id for p in [*periods, *existing_periods]}
        | {p.entity_id for p in [*periods, *existing_periods]}
    )
    await session.execute(
        select(Entity.id)
        .where(Entity.tenant_id == tenant_id, Entity.id.in_(lock_ids))
        .order_by(Entity.id)
        .with_for_update()
    )
    entry = await session.scalar(
        select(Entity)
        .where(Entity.id == entity_id, Entity.tenant_id == tenant_id)
        .execution_options(populate_existing=True)
    )
    if entry is None:
        raise EntityNotFoundError(detail="No entry with that id in this library")
    if if_match is None:
        raise AudiencePreconditionRequiredError(detail="Read the entry and send its ETag")
    check_if_match(if_match, updated_at=entry.updated_at)
    wanted = set(body.period_ids)
    periods = (
        await session.scalars(
            select(CalendarPeriod).where(
                CalendarPeriod.entity_id.in_(wanted), CalendarPeriod.tenant_id == tenant_id
            )
        )
    ).all()
    if len(periods) != len(wanted):
        raise InvalidCalendarDateError(detail="Choose dates from this library")
    for calendar_id in sorted({p.calendar_entity_id for p in periods}, key=str):
        await read_calendar(session, user, tenant_id, calendar_id, lock=True)
    for period in periods:
        await require_visible_entry(
            session, entity_id=period.entity_id, tenant_id=tenant_id, user_id=user.id
        )
    existing = set(
        await session.scalars(
            select(EntryCalendarPeriod.period_entity_id).where(
                EntryCalendarPeriod.entity_id == entity_id,
                EntryCalendarPeriod.tenant_id == tenant_id,
            )
        )
    )
    # A replacement cannot silently delete dates the editor is unable to inspect.
    for period_id in existing:
        await require_visible_entry(
            session, entity_id=period_id, tenant_id=tenant_id, user_id=user.id
        )
    if wanted != existing:
        await session.execute(
            delete(EntryCalendarPeriod).where(
                EntryCalendarPeriod.entity_id == entity_id,
                EntryCalendarPeriod.tenant_id == tenant_id,
            )
        )
        session.add_all(
            [
                EntryCalendarPeriod(entity_id=entity_id, period_entity_id=p, tenant_id=tenant_id)
                for p in wanted
            ]
        )
        entry.updated_at = datetime.now(UTC)
        entry.updated_by = user.id
        await record_activity(
            session,
            tenant_id=tenant_id,
            actor_id=user.id,
            action="entry.dates_changed",
            target_type="entity",
            target_id=entity_id,
        )
        await session.commit()
        await set_tenant_rls_context(session, tenant_id)
        await session.refresh(entry)
    response.headers["ETag"] = etag_for(entry.updated_at)
    return await list_entry_dates(tenant_id, entity_id, session, user)


@router.get("/calendar-periods/{period_id}/entries")
async def entries_at_period(
    tenant_id: uuid.UUID,
    period_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    params: ParamsDep,
) -> Page[DatedEntryOut]:
    from typing import cast

    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    await require_visible_entry(session, entity_id=period_id, tenant_id=tenant_id, user_id=user.id)
    if (
        await session.scalar(
            select(CalendarPeriod.entity_id).where(
                CalendarPeriod.entity_id == period_id, CalendarPeriod.tenant_id == tenant_id
            )
        )
        is None
    ):
        raise EntityNotFoundError(detail="No period with that id in this library")
    vis = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    query = (
        select(Entity.id, Entity.name)
        .join(EntryCalendarPeriod, EntryCalendarPeriod.entity_id == Entity.id)
        .where(
            EntryCalendarPeriod.period_entity_id == period_id,
            EntryCalendarPeriod.tenant_id == tenant_id,
            visible_entry_clause(vis, Entity.id),
        )
        .order_by(Entity.name, Entity.id)
    )
    result = await apaginate(
        session,
        query,
        params,
        transformer=lambda rows: [DatedEntryOut(entity_id=r.id, name=r.name) for r in rows],
    )
    return cast(Page[DatedEntryOut], result)
