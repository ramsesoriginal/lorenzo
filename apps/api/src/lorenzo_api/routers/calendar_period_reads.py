"""Bulk reads and one bulk write over calendar periods (ADR 0324).

Each one answers what a client would otherwise ask for one period at a time: periods with their
calendar and coordinates (and by id), the notes and dated entries of every saved period in a year
or month, and the explicit creation of many periods at once. They apply the visibility gates of the
single reads they stand for (ADR 0309): a period needs its own outer audience and its calendar's,
Information rows need their own audience, and a hidden row never shows in a list, a count or a
page boundary.
"""

from __future__ import annotations

import uuid
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Path, Query
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from lorenzo_calendar import CalendarDate, CalendarDefinition, segment_for
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import aliased, selectinload

from lorenzo_api.activity_log import record_activity
from lorenzo_api.dependencies import (
    CurrentUser,
    ParamsDep,
    SessionDep,
    get_tenant_or_404,
    require_tenant_participant,
)
from lorenzo_api.entry_visibility import require_visible_entry, visible_entry_clause
from lorenzo_api.exceptions import InvalidCalendarDateError
from lorenzo_api.information_visibility import (
    InformationVisibility,
    resolve_information_visibility,
    visible_information_clause,
)
from lorenzo_api.models import (
    CalendarPeriod,
    Entity,
    EntityAudience,
    EntitySlug,
    EntryCalendarPeriod,
    Information,
    Payload,
)
from lorenzo_api.routers.calendar_periods import (
    DatedEntryOut,
    PeriodCreate,
    PeriodOut,
    period_out,
)
from lorenzo_api.routers.calendars import read_calendar
from lorenzo_api.routers.entities import authorize_entity_write

router = APIRouter(
    prefix="/tenants/{tenant_id}",
    tags=["calendar periods"],
    dependencies=[Depends(get_tenant_or_404)],
)

# How much of one note a summary carries, and how many notes and dated entries per period.
SUMMARY_TEXT_LIMIT = 600
SUMMARY_NOTES = 10
SUMMARY_ENTRIES = 10

SEGMENT_PATTERN = r"^[a-z][a-z0-9-]{0,63}$"


class PeriodDetailOut(PeriodOut):
    calendar_name: str


class NoteSummaryOut(BaseModel):
    information_id: uuid.UUID
    title: str
    # The source of the note's first description, cut at a word; None when it has none.
    text: str | None
    truncated: bool


class PeriodSummaryOut(PeriodOut):
    notes: list[NoteSummaryOut]
    entries: list[DatedEntryOut]
    # Every dated entry the caller can see at this period, of which `entries` shows the first few.
    entry_total: int


class PeriodBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    periods: list[PeriodCreate] = Field(min_length=1, max_length=1000)


def cut(text: str) -> tuple[str, bool]:
    """`text` as it is, or cut at a word boundary within the summary limit."""
    if len(text) <= SUMMARY_TEXT_LIMIT:
        return text, False
    head = text[:SUMMARY_TEXT_LIMIT]
    boundary = head.rfind(" ")
    return (head[:boundary] if boundary > SUMMARY_TEXT_LIMIT // 2 else head).rstrip(), True


@router.get("/calendar-periods")
async def list_calendar_periods(
    tenant_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    params: ParamsDep,
    calendar_id: Annotated[uuid.UUID | None, Query()] = None,
    year: Annotated[int | None, Query(ge=-1000000, le=1000000)] = None,
    segment: Annotated[str | None, Query(pattern=SEGMENT_PATTERN)] = None,
    id: Annotated[list[uuid.UUID] | None, Query(max_length=100)] = None,
) -> Page[PeriodDetailOut]:
    """The periods the caller can see, in every calendar or in one, with their calendar's name."""
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    vis = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    calendar = aliased(Entity)
    query = (
        select(CalendarPeriod, Entity, EntitySlug.slug, calendar.name)
        .join(Entity, Entity.id == CalendarPeriod.entity_id)
        .join(calendar, calendar.id == CalendarPeriod.calendar_entity_id)
        .outerjoin(EntitySlug, EntitySlug.entity_id == CalendarPeriod.entity_id)
        .where(
            CalendarPeriod.tenant_id == tenant_id,
            visible_entry_clause(vis, CalendarPeriod.entity_id),
            visible_entry_clause(vis, CalendarPeriod.calendar_entity_id),
        )
        .order_by(
            calendar.name,
            CalendarPeriod.calendar_entity_id,
            CalendarPeriod.year,
            CalendarPeriod.segment,
            CalendarPeriod.day,
            CalendarPeriod.entity_id,
        )
    )
    if calendar_id is not None:
        query = query.where(CalendarPeriod.calendar_entity_id == calendar_id)
    if year is not None:
        query = query.where(CalendarPeriod.year == year)
    if segment is not None:
        query = query.where(CalendarPeriod.segment == segment)
    if id:
        query = query.where(CalendarPeriod.entity_id.in_(id))
    result = await apaginate(
        session,
        query,
        params,
        transformer=lambda rows: [
            PeriodDetailOut(**period_out(p, e, slug).model_dump(), calendar_name=name)
            for p, e, slug, name in rows
        ],
    )
    return cast(Page[PeriodDetailOut], result)


async def _notes_by_period(
    session: SessionDep,
    tenant_id: uuid.UUID,
    vis: InformationVisibility,
    period_ids: list[uuid.UUID],
) -> dict[uuid.UUID, list[NoteSummaryOut]]:
    information = (
        await session.scalars(
            select(Information)
            .where(
                Information.entity_id.in_(period_ids),
                Information.tenant_id == tenant_id,
                visible_information_clause(vis),
            )
            .options(selectinload(Information.payloads).joinedload(Payload.description))
            .order_by(Information.entity_id, Information.order, Information.id)
        )
    ).all()
    notes: dict[uuid.UUID, list[NoteSummaryOut]] = {}
    for row in information:
        bucket = notes.setdefault(row.entity_id, [])
        if len(bucket) >= SUMMARY_NOTES:
            continue
        description = next((p.description for p in row.payloads if p.description is not None), None)
        text, truncated = cut(description.content) if description is not None else (None, False)
        bucket.append(
            NoteSummaryOut(information_id=row.id, title=row.title, text=text, truncated=truncated)
        )
    return notes


async def _entries_by_period(
    session: SessionDep,
    tenant_id: uuid.UUID,
    vis: InformationVisibility,
    period_ids: list[uuid.UUID],
) -> tuple[dict[uuid.UUID, list[DatedEntryOut]], dict[uuid.UUID, int]]:
    ranked = (
        select(
            EntryCalendarPeriod.period_entity_id.label("period_id"),
            Entity.id.label("entity_id"),
            Entity.name.label("name"),
            EntitySlug.slug.label("slug"),
            func.row_number()
            .over(
                partition_by=EntryCalendarPeriod.period_entity_id,
                order_by=(Entity.name, Entity.id),
            )
            .label("position"),
            func.count().over(partition_by=EntryCalendarPeriod.period_entity_id).label("total"),
        )
        .join(Entity, Entity.id == EntryCalendarPeriod.entity_id)
        .outerjoin(EntitySlug, EntitySlug.entity_id == Entity.id)
        .where(
            EntryCalendarPeriod.period_entity_id.in_(period_ids),
            EntryCalendarPeriod.tenant_id == tenant_id,
            visible_entry_clause(vis, Entity.id),
        )
        .subquery()
    )
    rows = await session.execute(
        select(ranked)
        .where(ranked.c.position <= SUMMARY_ENTRIES)
        .order_by(ranked.c.period_id, ranked.c.position)
    )
    entries: dict[uuid.UUID, list[DatedEntryOut]] = {}
    totals: dict[uuid.UUID, int] = {}
    for row in rows:
        entries.setdefault(row.period_id, []).append(
            DatedEntryOut(entity_id=row.entity_id, name=row.name, slug=row.slug)
        )
        totals[row.period_id] = row.total
    return entries, totals


@router.get("/calendars/{calendar_id}/years/{year}/period-summaries")
async def period_summaries(
    tenant_id: uuid.UUID,
    calendar_id: uuid.UUID,
    year: Annotated[int, Path(ge=-1000000, le=1000000)],
    session: SessionDep,
    user: CurrentUser,
    params: ParamsDep,
    segment: Annotated[str | None, Query(pattern=SEGMENT_PATTERN)] = None,
) -> Page[PeriodSummaryOut]:
    """The saved periods of a year (or of one month or festival of it) with their notes and dated
    entries: what a month view needs in one request instead of two per period. Nothing is created.
    """
    await read_calendar(session, user, tenant_id, calendar_id)
    vis = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    query = (
        select(CalendarPeriod, Entity, EntitySlug.slug)
        .join(Entity, Entity.id == CalendarPeriod.entity_id)
        .outerjoin(EntitySlug, EntitySlug.entity_id == CalendarPeriod.entity_id)
        .where(
            CalendarPeriod.calendar_entity_id == calendar_id,
            CalendarPeriod.tenant_id == tenant_id,
            CalendarPeriod.year == year,
            visible_entry_clause(vis, CalendarPeriod.entity_id),
        )
        .order_by(CalendarPeriod.segment, CalendarPeriod.day)
    )
    if segment is not None:
        query = query.where(CalendarPeriod.segment == segment)
    page = cast(
        Page[PeriodSummaryOut],
        await apaginate(
            session,
            query,
            params,
            transformer=lambda rows: [
                PeriodSummaryOut(
                    **period_out(p, e, slug).model_dump(), notes=[], entries=[], entry_total=0
                )
                for p, e, slug in rows
            ],
        ),
    )
    ids = [item.entity_id for item in page.items]
    if ids:
        notes = await _notes_by_period(session, tenant_id, vis, ids)
        entries, totals = await _entries_by_period(session, tenant_id, vis, ids)
        for item in page.items:
            item.notes = notes.get(item.entity_id, [])
            item.entries = entries.get(item.entity_id, [])
            item.entry_total = totals.get(item.entity_id, 0)
    return page


@router.post("/calendars/{calendar_id}/periods/batch")
async def materialize_periods(
    tenant_id: uuid.UUID,
    calendar_id: uuid.UUID,
    body: PeriodBatch,
    session: SessionDep,
    user: CurrentUser,
) -> list[PeriodOut]:
    """Creates the listed periods and their year and month parents in one transaction, and
    returns them in request order. Periods that exist are reused; one invalid date fails all.
    It needs the standing the single write needs (ADR 0309) and locks the calendar once.
    """
    calendar, calendar_entry = await read_calendar(session, user, tenant_id, calendar_id, lock=True)
    await authorize_entity_write(session, entity_id=calendar_id, tenant_id=tenant_id, user=user)
    definition = CalendarDefinition.model_validate(calendar.definition)

    segment_names: dict[tuple[int, str], str] = {}
    for item in body.periods:
        if item.segment is None:
            continue
        try:
            segment = segment_for(
                definition, CalendarDate(year=item.year, segment=item.segment, day=item.day or 1)
            )
        except ValueError:
            raise InvalidCalendarDateError(
                detail="This date does not exist in the calendar"
            ) from None
        segment_names[(item.year, item.segment)] = segment.name

    Key = tuple[int, str | None, int | None]
    known: dict[Key, tuple[CalendarPeriod, Entity]] = {}
    rows = await session.execute(
        select(CalendarPeriod, Entity)
        .join(Entity, Entity.id == CalendarPeriod.entity_id)
        .where(
            CalendarPeriod.calendar_entity_id == calendar_id,
            CalendarPeriod.tenant_id == tenant_id,
            CalendarPeriod.year.in_({item.year for item in body.periods}),
        )
    )
    for period, entry in rows:
        known[(period.year, period.segment, period.day)] = (period, entry)

    # A period that exists must be one the caller may see, as with the single write.
    vis = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    if known:
        visible = set(
            await session.scalars(
                select(CalendarPeriod.entity_id).where(
                    CalendarPeriod.entity_id.in_([p.entity_id for p, _ in known.values()]),
                    visible_entry_clause(vis, CalendarPeriod.entity_id),
                )
            )
        )
        for period, _ in known.values():
            if period.entity_id not in visible:
                await require_visible_entry(
                    session, entity_id=period.entity_id, tenant_id=tenant_id, user_id=user.id
                )

    result: list[tuple[CalendarPeriod, Entity]] = []
    for item in body.periods:
        parent: uuid.UUID | None = None
        chain: list[Key] = [(item.year, None, None)]
        if item.segment is not None:
            chain.append((item.year, item.segment, None))
        if item.day is not None:
            chain.append((item.year, item.segment, item.day))
        for key in chain:
            _, segment_key, day = key
            if key not in known:
                name = segment_names.get((item.year, segment_key or ""), "")
                label = (
                    f"{calendar_entry.name} {item.year}"
                    if segment_key is None
                    else f"{name} {item.year}"
                    if day is None
                    else f"{day} {name} {item.year}"
                )
                entry = Entity(
                    tenant_id=tenant_id, name=label, created_by=user.id, updated_by=user.id
                )
                session.add(entry)
                await session.flush()
                period = CalendarPeriod(
                    entity_id=entry.id,
                    tenant_id=tenant_id,
                    calendar_entity_id=calendar_id,
                    year=item.year,
                    segment=segment_key,
                    day=day,
                    parent_entity_id=parent,
                )
                session.add_all(
                    [
                        period,
                        EntityAudience(
                            entity_id=entry.id, tenant_id=tenant_id, is_public=item.is_public
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
                known[key] = (period, entry)
            parent = known[key][1].id
        result.append(known[chain[-1]])

    out: list[PeriodOut] = [period_out(p, e) for p, e in result]
    await session.commit()
    return out
