"""Authored calendar definitions and calculation; dates are not clocks (ADR 0308)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Header, Path, Query, Response
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from lorenzo_calendar import CalendarDefinition, YearPreview, preview_year
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
    require_tenant_participant,
    set_tenant_rls_context,
)
from lorenzo_api.entity_kinds import create_entry
from lorenzo_api.entry_visibility import require_visible_entry, visible_entry_clause
from lorenzo_api.etag import check_if_match, etag_for
from lorenzo_api.exceptions import (
    AudiencePreconditionRequiredError,
    EntityNotFoundError,
    InformationManagementForbiddenError,
)
from lorenzo_api.information_visibility import resolve_information_visibility
from lorenzo_api.models import Calendar, Entity, EntityAudience
from lorenzo_api.routers.entities import authorize_entity_write
from lorenzo_api.schemas.common import Slug

router = APIRouter(
    prefix="/tenants/{tenant_id}/calendars",
    tags=["calendars"],
    dependencies=[Depends(get_tenant_or_404)],
)


class CalendarCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    slug: Slug | None = None
    definition: CalendarDefinition
    is_public: bool = False


class CalendarOut(BaseModel):
    entity_id: uuid.UUID
    name: str
    definition: CalendarDefinition
    updated_at: datetime


class CalendarSummary(BaseModel):
    entity_id: uuid.UUID
    name: str
    updated_at: datetime


async def read_calendar(
    session: SessionDep,
    user: CurrentUser,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    *,
    lock: bool = False,
) -> tuple[Calendar, Entity]:
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    await require_visible_entry(session, entity_id=entity_id, tenant_id=tenant_id, user_id=user.id)
    statement = (
        select(Calendar, Entity)
        .join(Entity, Calendar.entity_id == Entity.id)
        .where(Calendar.entity_id == entity_id, Calendar.tenant_id == tenant_id)
    )
    if lock:
        await session.execute(
            select(Entity.id)
            .where(Entity.id == entity_id, Entity.tenant_id == tenant_id)
            .with_for_update()
        )
        statement = statement.with_for_update(of=Calendar).execution_options(populate_existing=True)
    row = (await session.execute(statement)).first()
    if row is None:
        raise EntityNotFoundError(detail="No calendar with that id in this library")
    return row[0], row[1]


def output(calendar: Calendar, entity: Entity, response: Response) -> CalendarOut:
    response.headers["ETag"] = etag_for(calendar.updated_at)
    return CalendarOut(
        entity_id=entity.id,
        name=entity.name,
        definition=CalendarDefinition.model_validate(calendar.definition),
        updated_at=calendar.updated_at,
    )


@router.get("")
async def list_calendars(
    tenant_id: uuid.UUID, session: SessionDep, user: CurrentUser, params: ParamsDep
) -> Page[CalendarSummary]:
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    vis = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    statement = (
        select(Calendar.entity_id, Entity.name, Calendar.updated_at)
        .join(Entity, Entity.id == Calendar.entity_id)
        .where(Calendar.tenant_id == tenant_id, visible_entry_clause(vis, Calendar.entity_id))
        .order_by(Entity.name, Calendar.entity_id)
    )
    result = await apaginate(
        session,
        statement,
        params,
        transformer=lambda rows: [
            CalendarSummary(entity_id=r.entity_id, name=r.name, updated_at=r.updated_at)
            for r in rows
        ],
    )

    return cast(Page[CalendarSummary], result)


@router.post("/preview")
async def preview_definition(
    tenant_id: uuid.UUID,
    definition: CalendarDefinition,
    session: SessionDep,
    user: CurrentUser,
    year: Annotated[int, Query(ge=-1000000, le=1000000)],
) -> YearPreview:
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    return preview_year(definition, year)


@router.post("", status_code=201, dependencies=[Depends(get_tenant_context)])
async def create_calendar(
    tenant_id: uuid.UUID,
    body: CalendarCreate,
    session: SessionDep,
    user: CurrentUser,
    response: Response,
) -> CalendarOut:
    await author_may_use_kinds(session, tenant_id=tenant_id, user_id=user.id, kinds=["calendar"])
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
    calendar = Calendar(
        entity_id=entity.id, tenant_id=tenant_id, definition=body.definition.model_dump(mode="json")
    )
    session.add_all(
        [
            calendar,
            EntityAudience(entity_id=entity.id, tenant_id=tenant_id, is_public=body.is_public),
        ]
    )
    await session.flush()
    session.info.pop("visible_entry_checks", None)
    try:
        await require_visible_entry(
            session, entity_id=entity.id, tenant_id=tenant_id, user_id=user.id
        )
    except EntityNotFoundError:
        raise InformationManagementForbiddenError(
            detail="Your current roles cannot read this restricted calendar"
        ) from None
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="calendar.created",
        target_type="entity",
        target_id=entity.id,
    )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    await session.refresh(calendar)
    await session.refresh(entity)
    response.headers["Location"] = f"/tenants/{tenant_id}/calendars/{entity.id}"
    return output(calendar, entity, response)


@router.get("/{entity_id}")
async def get_calendar(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    response: Response,
) -> CalendarOut:
    calendar, entity = await read_calendar(session, user, tenant_id, entity_id)
    return output(calendar, entity, response)


@router.put("/{entity_id}/definition")
async def replace_definition(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    definition: CalendarDefinition,
    session: SessionDep,
    user: CurrentUser,
    response: Response,
    if_match: Annotated[str | None, Header()] = None,
) -> CalendarOut:
    calendar, entity = await read_calendar(session, user, tenant_id, entity_id, lock=True)
    await authorize_entity_write(session, entity_id=entity_id, tenant_id=tenant_id, user=user)
    if if_match is None:
        raise AudiencePreconditionRequiredError(
            detail="Read the calendar and send its ETag as If-Match."
        )
    check_if_match(if_match, updated_at=calendar.updated_at)
    from lorenzo_api.calendar_periods import validate_materialized_periods

    await validate_materialized_periods(session, tenant_id, entity_id, definition)
    value = definition.model_dump(mode="json")
    if calendar.definition != value:
        calendar.definition = value
        calendar.updated_at = datetime.now(UTC)
        entity.updated_at = calendar.updated_at
        entity.updated_by = user.id
        await session.commit()
        await set_tenant_rls_context(session, tenant_id)
        await session.refresh(calendar)
        await session.refresh(entity)
    return output(calendar, entity, response)


@router.get("/{entity_id}/years/{year}")
async def get_calendar_year(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    year: Annotated[int, Path(ge=-1000000, le=1000000)],
    session: SessionDep,
    user: CurrentUser,
) -> YearPreview:
    calendar, _ = await read_calendar(session, user, tenant_id, entity_id)
    return preview_year(CalendarDefinition.model_validate(calendar.definition), year)
