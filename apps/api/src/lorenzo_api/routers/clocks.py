"""Explicit clock authoring and readings (ADR 0320)."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from fractions import Fraction
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response
from lorenzo_calendar import CalendarDate, CalendarDefinition, from_day, to_day
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, text

from lorenzo_api.clock_values import Rational, ReadingRange
from lorenzo_api.dependencies import (
    CurrentUser,
    SessionDep,
    get_tenant_or_404,
    require_tenant_participant,
    set_tenant_rls_context,
)
from lorenzo_api.entity_kinds import create_entry
from lorenzo_api.entry_visibility import require_visible_entry, visible_entry_clause
from lorenzo_api.etag import check_if_match, etag_for
from lorenzo_api.exceptions import (
    AudiencePreconditionRequiredError,
    EntityKindInUseError,
    EntityNotFoundError,
    InvalidKindRequestError,
    PreconditionFailedError,
)
from lorenzo_api.information_visibility import resolve_information_visibility
from lorenzo_api.models import (
    Calendar,
    CalendarReckoning,
    Clock,
    Entity,
    EntityAudience,
    EntitySlug,
    EventClockReading,
    StoryEvent,
)
from lorenzo_api.routers.event_order import require_event_order_access
from lorenzo_api.schemas.common import Slug

router = APIRouter(
    prefix="/tenants/{tenant_id}", tags=["clocks"], dependencies=[Depends(get_tenant_or_404)]
)


class ClockCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    slug: Slug | None = None
    ticking: bool = True
    is_public: bool = False


class ClockOut(BaseModel):
    entity_id: uuid.UUID
    name: str
    slug: str | None = None
    ticking: bool
    updated_at: datetime


class ClockEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticking: bool


class ReadingIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reading: ReadingRange
    is_shared: bool = False


class ReadingOut(ReadingIn):
    clock_entity_id: uuid.UUID
    clock_name: str


class ReadingsOut(BaseModel):
    items: list[ReadingOut]
    can_manage: bool


class ReckoningIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date: CalendarDate
    reading: Rational
    is_shared: bool = False


class ReckoningOut(ReckoningIn):
    calendar_entity_id: uuid.UUID
    calendar_name: str


class ReckoningsOut(BaseModel):
    items: list[ReckoningOut]
    can_manage: bool


class ClockDateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    calendar_entity_id: uuid.UUID
    date: CalendarDate


class ClockDateOut(BaseModel):
    reading: ReadingRange


class ClockDateReadingIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    calendar_entity_id: uuid.UUID
    reading: ReadingRange


class ClockDateReadingOut(BaseModel):
    first_date: CalendarDate
    last_date: CalendarDate
    reading: ReadingRange


async def mutation_lock(session: SessionDep, tenant: uuid.UUID) -> None:
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended('lorenzo:clocks:' || :tenant, 0))"),
        {"tenant": str(tenant)},
    )


async def lock_clock_entries(
    session: SessionDep, tenant: uuid.UUID, identities: list[uuid.UUID]
) -> None:
    await session.execute(
        select(Entity.id)
        .where(Entity.tenant_id == tenant, Entity.id.in_(identities))
        .order_by(Entity.id)
        .with_for_update()
    )


async def manager(session: SessionDep, user: CurrentUser, tenant: uuid.UUID) -> bool:
    vis = await resolve_information_visibility(session, tenant_id=tenant, user_id=user.id)
    return vis.is_admin or vis.manages_events


async def endpoint(
    session: SessionDep,
    user: CurrentUser,
    tenant: uuid.UUID,
    identity: uuid.UUID,
    model: type[Clock] | type[Calendar] | type[StoryEvent],
) -> Entity:
    await require_tenant_participant(session, tenant_id=tenant, user=user)
    await require_visible_entry(session, tenant_id=tenant, entity_id=identity, user_id=user.id)
    entity = await session.scalar(
        select(Entity)
        .join(model, model.entity_id == Entity.id)
        .where(Entity.tenant_id == tenant, Entity.id == identity)
    )
    if entity is None:
        raise EntityNotFoundError(detail="No such entry in this library")
    return entity


async def ticking_clock(
    session: SessionDep, user: CurrentUser, tenant: uuid.UUID, identity: uuid.UUID
) -> Clock:
    await endpoint(session, user, tenant, identity, Clock)
    clock = await session.get(Clock, identity)
    assert clock is not None
    if not clock.ticking:
        raise InvalidKindRequestError(detail="A timeless clock has no readings or reckonings")
    return clock


def revision(rows: list[object]) -> str:
    return (
        '"'
        + hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()
        + '"'
    )


def conditional(if_match: str | None, version: str) -> None:
    if if_match is None:
        raise AudiencePreconditionRequiredError(
            detail="Read the saved records and send their ETag as If-Match"
        )
    if if_match != version:
        raise PreconditionFailedError(detail="Saved clock data changed. Review it before retrying")


async def commit(session: SessionDep, tenant: uuid.UUID) -> None:
    await session.commit()
    await set_tenant_rls_context(session, tenant)


@router.get("/clocks")
async def clocks(tenant_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> list[ClockOut]:
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    vis = await resolve_information_visibility(session, tenant_id=tenant_id, user_id=user.id)
    rows = await session.execute(
        select(Clock, Entity.name, EntitySlug.slug)
        .join(Entity, Entity.id == Clock.entity_id)
        .outerjoin(EntitySlug, EntitySlug.entity_id == Clock.entity_id)
        .where(Clock.tenant_id == tenant_id, visible_entry_clause(vis, Clock.entity_id))
        .order_by(Entity.name, Clock.entity_id)
        .limit(201)
    )
    result = [
        ClockOut(entity_id=c.entity_id, name=n, slug=s, ticking=c.ticking, updated_at=c.updated_at)
        for c, n, s in rows
    ]
    if len(result) > 200:
        raise InvalidKindRequestError(detail="Clock list limit reached")
    return result


@router.post("/clocks", status_code=201)
async def create_clock(
    tenant_id: uuid.UUID,
    body: ClockCreate,
    session: SessionDep,
    user: CurrentUser,
    response: Response,
) -> ClockOut:
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    await require_event_order_access(session, user, tenant_id)
    entity = await create_entry(
        session,
        tenant_id=tenant_id,
        user_id=user.id,
        name=body.name,
        slug=body.slug,
        kinds=[],
        parents=[],
        in_public_catalog=False,
        entity_id=body.id,
    )
    clock = Clock(entity_id=entity.id, tenant_id=tenant_id, ticking=body.ticking)
    session.add_all(
        [clock, EntityAudience(entity_id=entity.id, tenant_id=tenant_id, is_public=body.is_public)]
    )
    await commit(session, tenant_id)
    return await get_clock(tenant_id, entity.id, session, user, response)


@router.get("/clocks/{clock_id}")
async def get_clock(
    tenant_id: uuid.UUID,
    clock_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    response: Response,
) -> ClockOut:
    entity = await endpoint(session, user, tenant_id, clock_id, Clock)
    clock = await session.get(Clock, clock_id)
    assert clock is not None
    slug = await session.scalar(select(EntitySlug.slug).where(EntitySlug.entity_id == clock_id))
    response.headers["ETag"] = etag_for(clock.updated_at)
    return ClockOut(
        entity_id=clock_id,
        name=entity.name,
        slug=slug,
        ticking=clock.ticking,
        updated_at=clock.updated_at,
    )


@router.put("/clocks/{clock_id}")
async def edit_clock(
    tenant_id: uuid.UUID,
    clock_id: uuid.UUID,
    body: ClockEdit,
    session: SessionDep,
    user: CurrentUser,
    response: Response,
    if_match: Annotated[str | None, Header()] = None,
) -> ClockOut:
    await require_event_order_access(session, user, tenant_id)
    await mutation_lock(session, tenant_id)
    await lock_clock_entries(session, tenant_id, [clock_id])
    await endpoint(session, user, tenant_id, clock_id, Clock)
    clock = await session.scalar(select(Clock).where(Clock.entity_id == clock_id).with_for_update())
    assert clock is not None
    if if_match is None:
        raise AudiencePreconditionRequiredError(detail="Read the clock and send its ETag")
    check_if_match(if_match, updated_at=clock.updated_at)
    if clock.ticking != body.ticking:
        if not body.ticking and (
            await session.scalar(
                select(EventClockReading.clock_entity_id)
                .where(EventClockReading.clock_entity_id == clock_id)
                .limit(1)
            )
            or await session.scalar(
                select(CalendarReckoning.clock_entity_id)
                .where(CalendarReckoning.clock_entity_id == clock_id)
                .limit(1)
            )
        ):
            raise EntityKindInUseError(
                detail="Resolve dependent clock records before changing this clock"
            )
        clock.ticking = body.ticking
        clock.updated_at = datetime.now(UTC)
        await commit(session, tenant_id)
    return await get_clock(tenant_id, clock_id, session, user, response)


async def reading_rows(
    session: SessionDep, user: CurrentUser, tenant: uuid.UUID, event: uuid.UUID
) -> tuple[list[EventClockReading], bool]:
    await endpoint(session, user, tenant, event, StoryEvent)
    vis = await resolve_information_visibility(session, tenant_id=tenant, user_id=user.id)
    manage = vis.is_admin or vis.manages_events
    query = (
        select(EventClockReading)
        .where(
            EventClockReading.tenant_id == tenant,
            EventClockReading.event_entity_id == event,
            visible_entry_clause(vis, EventClockReading.clock_entity_id),
        )
        .order_by(EventClockReading.clock_entity_id)
    )
    if not manage:
        query = query.where(EventClockReading.is_shared.is_(True))
    return list(await session.scalars(query)), manage


def reading_revision(rows: list[EventClockReading]) -> str:
    return revision([(r.clock_entity_id, r.data, r.is_shared, r.updated_at) for r in rows])


@router.get("/events/{event_id}/clock-readings")
async def readings(
    tenant_id: uuid.UUID,
    event_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    response: Response,
) -> ReadingsOut:
    rows, manage = await reading_rows(session, user, tenant_id, event_id)
    names = {
        identity: name
        for identity, name in await session.execute(
            select(Entity.id, Entity.name).where(Entity.id.in_([r.clock_entity_id for r in rows]))
        )
    }
    response.headers["ETag"] = reading_revision(rows)
    return ReadingsOut(
        can_manage=manage,
        items=[
            ReadingOut(
                clock_entity_id=r.clock_entity_id,
                clock_name=names[r.clock_entity_id],
                reading=ReadingRange.model_validate(r.data),
                is_shared=r.is_shared,
            )
            for r in rows
        ],
    )


@router.put("/events/{event_id}/clock-readings/{clock_id}")
async def save_reading(
    tenant_id: uuid.UUID,
    event_id: uuid.UUID,
    clock_id: uuid.UUID,
    body: ReadingIn,
    session: SessionDep,
    user: CurrentUser,
    response: Response,
    if_match: Annotated[str | None, Header()] = None,
) -> ReadingsOut:
    await require_event_order_access(session, user, tenant_id)
    await mutation_lock(session, tenant_id)
    await lock_clock_entries(session, tenant_id, [event_id, clock_id])
    rows, _ = await reading_rows(session, user, tenant_id, event_id)
    conditional(if_match, reading_revision(rows))
    await ticking_clock(session, user, tenant_id, clock_id)
    row = await session.get(EventClockReading, (event_id, clock_id))
    if row is None:
        row = EventClockReading(
            event_entity_id=event_id, clock_entity_id=clock_id, tenant_id=tenant_id
        )
        session.add(row)
    row.data = body.reading.model_dump()
    row.is_shared = body.is_shared
    row.updated_at = datetime.now(UTC)
    await commit(session, tenant_id)
    return await readings(tenant_id, event_id, session, user, response)


@router.delete("/events/{event_id}/clock-readings/{clock_id}")
async def remove_reading(
    tenant_id: uuid.UUID,
    event_id: uuid.UUID,
    clock_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    response: Response,
    if_match: Annotated[str | None, Header()] = None,
) -> ReadingsOut:
    await require_event_order_access(session, user, tenant_id)
    await mutation_lock(session, tenant_id)
    await lock_clock_entries(session, tenant_id, [event_id, clock_id])
    rows, _ = await reading_rows(session, user, tenant_id, event_id)
    conditional(if_match, reading_revision(rows))
    await endpoint(session, user, tenant_id, clock_id, Clock)
    row = next((r for r in rows if r.clock_entity_id == clock_id), None)
    if row is not None:
        await session.delete(row)
        await commit(session, tenant_id)
    return await readings(tenant_id, event_id, session, user, response)


async def reckoning_rows(
    session: SessionDep, user: CurrentUser, tenant: uuid.UUID, clock: uuid.UUID
) -> tuple[list[CalendarReckoning], bool]:
    await endpoint(session, user, tenant, clock, Clock)
    vis = await resolve_information_visibility(session, tenant_id=tenant, user_id=user.id)
    manage = vis.is_admin or vis.manages_events
    query = (
        select(CalendarReckoning)
        .where(
            CalendarReckoning.tenant_id == tenant,
            CalendarReckoning.clock_entity_id == clock,
            visible_entry_clause(vis, CalendarReckoning.calendar_entity_id),
        )
        .order_by(CalendarReckoning.calendar_entity_id)
    )
    if not manage:
        query = query.where(CalendarReckoning.is_shared.is_(True))
    return list(await session.scalars(query)), manage


def reckoning_revision(rows: list[CalendarReckoning]) -> str:
    return revision([(r.calendar_entity_id, r.data, r.is_shared, r.updated_at) for r in rows])


@router.get("/clocks/{clock_id}/reckonings")
async def reckonings(
    tenant_id: uuid.UUID,
    clock_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    response: Response,
) -> ReckoningsOut:
    rows, manage = await reckoning_rows(session, user, tenant_id, clock_id)
    names = {
        identity: name
        for identity, name in await session.execute(
            select(Entity.id, Entity.name).where(
                Entity.id.in_([r.calendar_entity_id for r in rows])
            )
        )
    }
    response.headers["ETag"] = reckoning_revision(rows)
    return ReckoningsOut(
        can_manage=manage,
        items=[
            ReckoningOut(
                calendar_entity_id=r.calendar_entity_id,
                calendar_name=names[r.calendar_entity_id],
                **r.data,
                is_shared=r.is_shared,
            )
            for r in rows
        ],
    )


@router.put("/clocks/{clock_id}/reckonings/{calendar_id}")
async def save_reckoning(
    tenant_id: uuid.UUID,
    clock_id: uuid.UUID,
    calendar_id: uuid.UUID,
    body: ReckoningIn,
    session: SessionDep,
    user: CurrentUser,
    response: Response,
    if_match: Annotated[str | None, Header()] = None,
) -> ReckoningsOut:
    await require_event_order_access(session, user, tenant_id)
    await mutation_lock(session, tenant_id)
    await lock_clock_entries(session, tenant_id, [clock_id, calendar_id])
    rows, _ = await reckoning_rows(session, user, tenant_id, clock_id)
    conditional(if_match, reckoning_revision(rows))
    await ticking_clock(session, user, tenant_id, clock_id)
    await endpoint(session, user, tenant_id, calendar_id, Calendar)
    calendar = await session.scalar(
        select(Calendar).where(Calendar.entity_id == calendar_id).with_for_update()
    )
    assert calendar is not None
    try:
        to_day(CalendarDefinition.model_validate(calendar.definition), body.date)
    except ValueError as error:
        raise InvalidKindRequestError(detail=str(error)) from error
    row = await session.get(CalendarReckoning, (calendar_id, clock_id))
    if row is None:
        row = CalendarReckoning(
            calendar_entity_id=calendar_id, clock_entity_id=clock_id, tenant_id=tenant_id
        )
        session.add(row)
    row.data = body.model_dump(mode="json", exclude={"is_shared"})
    row.is_shared = body.is_shared
    row.updated_at = datetime.now(UTC)
    await commit(session, tenant_id)
    return await reckonings(tenant_id, clock_id, session, user, response)


@router.delete("/clocks/{clock_id}/reckonings/{calendar_id}")
async def remove_reckoning(
    tenant_id: uuid.UUID,
    clock_id: uuid.UUID,
    calendar_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    response: Response,
    if_match: Annotated[str | None, Header()] = None,
) -> ReckoningsOut:
    await require_event_order_access(session, user, tenant_id)
    await mutation_lock(session, tenant_id)
    await lock_clock_entries(session, tenant_id, [clock_id, calendar_id])
    rows, _ = await reckoning_rows(session, user, tenant_id, clock_id)
    conditional(if_match, reckoning_revision(rows))
    await endpoint(session, user, tenant_id, calendar_id, Calendar)
    row = next((r for r in rows if r.calendar_entity_id == calendar_id), None)
    if row is not None:
        await session.delete(row)
        await commit(session, tenant_id)
    return await reckonings(tenant_id, clock_id, session, user, response)


async def date_mapping(
    session: SessionDep, user: CurrentUser, tenant: uuid.UUID, clock: uuid.UUID, calendar: uuid.UUID
) -> tuple[CalendarDefinition, Fraction]:
    rows, _ = await reckoning_rows(session, user, tenant, clock)
    row = next((r for r in rows if r.calendar_entity_id == calendar), None)
    if row is None:
        raise EntityNotFoundError(detail="No permitted calendar reckoning")
    definition = await session.scalar(
        select(Calendar.definition).where(
            Calendar.entity_id == calendar, Calendar.tenant_id == tenant
        )
    )
    parsed = CalendarDefinition.model_validate(definition)
    return parsed, Fraction(row.data["reading"]) - to_day(
        parsed, CalendarDate.model_validate(row.data["date"])
    )


@router.post("/clocks/{clock_id}/date-reading")
async def date_reading(
    tenant_id: uuid.UUID,
    clock_id: uuid.UUID,
    body: ClockDateIn,
    session: SessionDep,
    user: CurrentUser,
) -> ClockDateOut:
    definition, offset = await date_mapping(
        session, user, tenant_id, clock_id, body.calendar_entity_id
    )
    try:
        day = to_day(definition, body.date)
        return ClockDateOut(
            reading=ReadingRange(lo=str(day), hi=str(day + 1), hi_inclusive=False).shift(offset)
        )
    except ValueError as error:
        raise InvalidKindRequestError(detail=str(error)) from error


@router.post("/clocks/{clock_id}/reading-dates")
async def reading_dates(
    tenant_id: uuid.UUID,
    clock_id: uuid.UUID,
    body: ClockDateReadingIn,
    session: SessionDep,
    user: CurrentUser,
) -> ClockDateReadingOut:
    definition, offset = await date_mapping(
        session, user, tenant_id, clock_id, body.calendar_entity_id
    )
    lo, hi = Fraction(body.reading.lo) - offset, Fraction(body.reading.hi) - offset
    last = hi.__floor__() - (not body.reading.hi_inclusive and hi.denominator == 1)
    try:
        return ClockDateReadingOut(
            first_date=from_day(definition, lo.__floor__()),
            last_date=from_day(definition, last),
            reading=body.reading,
        )
    except ValueError as error:
        raise InvalidKindRequestError(detail=str(error)) from error
