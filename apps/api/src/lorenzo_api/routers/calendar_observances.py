"""Recurring observances, without materialized occurrences (ADR 0310)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Header, Path, Query, Response
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from lorenzo_calendar import (
    CalendarDate,
    CalendarDefinition,
    RecurrenceRule,
    occurrence,
    validate_recurrence,
)
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from lorenzo_api.activity_log import record_activity
from lorenzo_api.author_guards import author_may_use_kinds
from lorenzo_api.dependencies import (
    CurrentUser,
    ParamsDep,
    SessionDep,
    get_tenant_context,
    get_tenant_or_404,
    set_tenant_rls_context,
)
from lorenzo_api.entity_kinds import create_entry
from lorenzo_api.entry_visibility import require_visible_entry, visible_entry_clause
from lorenzo_api.etag import check_if_match, etag_for
from lorenzo_api.exceptions import (
    AudiencePreconditionRequiredError,
    EntityNotFoundError,
    InformationManagementForbiddenError,
    InvalidCalendarDateError,
)
from lorenzo_api.information_visibility import resolve_information_visibility
from lorenzo_api.models import CalendarObservance, Entity, EntityAudience
from lorenzo_api.routers.calendars import read_calendar
from lorenzo_api.routers.entities import authorize_entity_write
from lorenzo_api.schemas.common import Slug

router = APIRouter(
    prefix="/tenants/{tenant_id}",
    tags=["calendar observances"],
    dependencies=[Depends(get_tenant_or_404)],
)


class ObservanceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    slug: Slug | None = None
    rule: RecurrenceRule
    is_public: bool = False


class ObservanceOut(BaseModel):
    entity_id: uuid.UUID
    calendar_entity_id: uuid.UUID
    name: str
    rule: RecurrenceRule
    updated_at: datetime


class OccurrenceOut(BaseModel):
    entity_id: uuid.UUID
    name: str
    date: CalendarDate


def output(observance: CalendarObservance, entry: Entity) -> ObservanceOut:
    return ObservanceOut(
        entity_id=entry.id,
        calendar_entity_id=observance.calendar_entity_id,
        name=entry.name,
        rule=RecurrenceRule.model_validate(observance.rule),
        updated_at=entry.updated_at,
    )


async def read_observance(
    session: SessionDep, user: CurrentUser, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> tuple[CalendarObservance, Entity]:
    await require_visible_entry(session, entity_id=entity_id, tenant_id=tenant_id, user_id=user.id)
    row = (
        await session.execute(
            select(CalendarObservance, Entity)
            .join(Entity, Entity.id == CalendarObservance.entity_id)
            .where(
                CalendarObservance.entity_id == entity_id, CalendarObservance.tenant_id == tenant_id
            )
        )
    ).first()
    if row is None:
        raise EntityNotFoundError(detail="No observance with that id in this library")
    await read_calendar(session, user, tenant_id, row[0].calendar_entity_id)
    return row[0], row[1]


@router.post(
    "/calendars/{calendar_id}/observances",
    status_code=201,
    dependencies=[Depends(get_tenant_context)],
)
async def create_observance(
    tenant_id: uuid.UUID,
    calendar_id: uuid.UUID,
    body: ObservanceCreate,
    session: SessionDep,
    user: CurrentUser,
    response: Response,
) -> ObservanceOut:
    calendar, _ = await read_calendar(session, user, tenant_id, calendar_id, lock=True)
    await authorize_entity_write(session, entity_id=calendar_id, tenant_id=tenant_id, user=user)
    await author_may_use_kinds(session, tenant_id=tenant_id, user_id=user.id, kinds=["observance"])
    try:
        validate_recurrence(CalendarDefinition.model_validate(calendar.definition), body.rule)
    except ValueError:
        raise InvalidCalendarDateError(detail="Choose a segment and day in this calendar") from None
    entry = await create_entry(
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
    observance = CalendarObservance(
        entity_id=entry.id,
        tenant_id=tenant_id,
        calendar_entity_id=calendar_id,
        rule=body.rule.model_dump(mode="json"),
    )
    session.add_all(
        [
            observance,
            EntityAudience(entity_id=entry.id, tenant_id=tenant_id, is_public=body.is_public),
        ]
    )
    await session.flush()
    session.info.pop("visible_entry_checks", None)
    try:
        await require_visible_entry(
            session, entity_id=entry.id, tenant_id=tenant_id, user_id=user.id
        )
    except EntityNotFoundError:
        raise InformationManagementForbiddenError(
            detail="Your current roles cannot read this restricted observance"
        ) from None
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="calendar.observance_created",
        target_type="entity",
        target_id=entry.id,
    )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    await session.refresh(entry)
    await session.refresh(observance)
    response.headers["ETag"] = etag_for(entry.updated_at)
    response.headers["Location"] = f"/tenants/{tenant_id}/observances/{entry.id}"
    return output(observance, entry)


@router.get("/observances/{entity_id}")
async def get_observance(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    response: Response,
) -> ObservanceOut:
    observance, entry = await read_observance(session, user, tenant_id, entity_id)
    response.headers["ETag"] = etag_for(entry.updated_at)
    return output(observance, entry)


@router.put("/observances/{entity_id}/rule")
async def replace_rule(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    rule: RecurrenceRule,
    session: SessionDep,
    user: CurrentUser,
    response: Response,
    if_match: Annotated[str | None, Header()] = None,
) -> ObservanceOut:
    observance, _ = await read_observance(session, user, tenant_id, entity_id)
    await authorize_entity_write(session, entity_id=entity_id, tenant_id=tenant_id, user=user)
    await session.execute(
        select(Entity.id)
        .where(
            Entity.tenant_id == tenant_id, Entity.id.in_([entity_id, observance.calendar_entity_id])
        )
        .order_by(Entity.id)
        .with_for_update()
    )
    calendar, _ = await read_calendar(
        session, user, tenant_id, observance.calendar_entity_id, lock=True
    )
    entry = await session.scalar(
        select(Entity).where(Entity.id == entity_id).execution_options(populate_existing=True)
    )
    assert entry is not None
    if if_match is None:
        raise AudiencePreconditionRequiredError(detail="Read the observance and send its ETag")
    check_if_match(if_match, updated_at=entry.updated_at)
    try:
        validate_recurrence(CalendarDefinition.model_validate(calendar.definition), rule)
    except ValueError:
        raise InvalidCalendarDateError(detail="Choose a segment and day in this calendar") from None
    # Refresh after the lock, so a waiting edit cannot use a stale rule.
    await session.refresh(observance)
    value = rule.model_dump(mode="json")
    if value != observance.rule:
        observance.rule = value
        entry.updated_at = datetime.now(UTC)
        entry.updated_by = user.id
        await record_activity(
            session,
            tenant_id=tenant_id,
            actor_id=user.id,
            action="calendar.observance_changed",
            target_type="entity",
            target_id=entity_id,
        )
        await session.commit()
        await set_tenant_rls_context(session, tenant_id)
        await session.refresh(entry)
        await session.refresh(observance)
    response.headers["ETag"] = etag_for(entry.updated_at)
    return output(observance, entry)


@router.get("/calendars/{calendar_id}/observances")
async def list_observances(
    tenant_id: uuid.UUID,
    calendar_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    params: ParamsDep,
) -> Page[ObservanceOut]:
    await read_calendar(session, user, tenant_id, calendar_id)
    vis = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    query = (
        select(CalendarObservance, Entity)
        .join(Entity, Entity.id == CalendarObservance.entity_id)
        .where(
            CalendarObservance.calendar_entity_id == calendar_id,
            CalendarObservance.tenant_id == tenant_id,
            visible_entry_clause(vis, Entity.id),
        )
        .order_by(Entity.name, Entity.id)
    )
    return cast(
        Page[ObservanceOut],
        await apaginate(
            session, query, params, transformer=lambda rows: [output(o, e) for o, e in rows]
        ),
    )


@router.get("/calendars/{calendar_id}/years/{year}/observances")
async def year_observances(
    tenant_id: uuid.UUID,
    calendar_id: uuid.UUID,
    year: Annotated[int, Path(ge=-1000000, le=1000000)],
    session: SessionDep,
    user: CurrentUser,
    params: ParamsDep,
    segment: Annotated[str | None, Query()] = None,
) -> Page[OccurrenceOut]:
    calendar, _ = await read_calendar(session, user, tenant_id, calendar_id)
    definition = CalendarDefinition.model_validate(calendar.definition)
    if segment is not None and not any(s.key == segment for s in definition.segments):
        raise InvalidCalendarDateError(detail="Choose a segment in this calendar")
    vis = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    rows = await session.execute(
        select(CalendarObservance, Entity.name)
        .join(Entity, Entity.id == CalendarObservance.entity_id)
        .where(
            CalendarObservance.tenant_id == tenant_id,
            CalendarObservance.calendar_entity_id == calendar_id,
            visible_entry_clause(vis, CalendarObservance.entity_id),
        )
    )
    positions = {s.key: i for i, s in enumerate(definition.segments)}
    results = []
    for observance, name in rows:
        date = occurrence(definition, RecurrenceRule.model_validate(observance.rule), year)
        if date is not None and (segment is None or date.segment == segment):
            results.append(OccurrenceOut(entity_id=observance.entity_id, name=name, date=date))
    results.sort(key=lambda o: (positions[o.date.segment], o.date.day, o.name, o.entity_id))
    raw = params.to_raw_params()
    assert raw.offset is not None and raw.limit is not None
    return Page[OccurrenceOut].create(
        results[raw.offset : raw.offset + raw.limit], total=len(results), params=params
    )
