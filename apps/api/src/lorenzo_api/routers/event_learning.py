"""Explicit staff-only Event learning provenance (ADR 0314)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Header, Response
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import aliased

from lorenzo_api.activity_log import record_activity
from lorenzo_api.dependencies import (
    CurrentUser,
    ParamsDep,
    SessionDep,
    get_tenant_or_404,
    set_tenant_rls_context,
)
from lorenzo_api.entry_visibility import visible_entry_clause
from lorenzo_api.etag import check_if_match, etag_for
from lorenzo_api.exceptions import EntityNotFoundError, EventOrderPreconditionRequiredError
from lorenzo_api.information_visibility import (
    resolve_information_visibility,
    visible_information_clause,
)
from lorenzo_api.models import Entity, EventLearning, EventParticipant, Information
from lorenzo_api.routers.event_order import read_event, require_event_order_access

router = APIRouter(
    prefix="/tenants/{tenant_id}",
    tags=["Event learning"],
    dependencies=[Depends(get_tenant_or_404)],
)


class LearningOut(BaseModel):
    event_entity_id: uuid.UUID
    event_name: str
    being_entity_id: uuid.UUID
    being_name: str
    information_id: uuid.UUID
    information_title: str | None
    information_entity_id: uuid.UUID
    information_entity_name: str


@router.get("/event-learning")
async def list_learning(
    tenant_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    params: ParamsDep,
    event_id: uuid.UUID | None = None,
    being_id: uuid.UUID | None = None,
    information_id: uuid.UUID | None = None,
) -> Page[LearningOut]:
    await require_event_order_access(session, user, tenant_id)
    vis = await resolve_information_visibility(session, tenant_id=tenant_id, user_id=user.id)
    event, being, source = aliased(Entity), aliased(Entity), aliased(Entity)
    query = (
        select(
            EventLearning.event_entity_id,
            event.name.label("event_name"),
            EventLearning.being_entity_id,
            being.name.label("being_name"),
            EventLearning.information_id,
            Information.title.label("information_title"),
            Information.entity_id.label("information_entity_id"),
            source.name.label("information_entity_name"),
        )
        .join(event, event.id == EventLearning.event_entity_id)
        .join(being, being.id == EventLearning.being_entity_id)
        .join(Information, Information.id == EventLearning.information_id)
        .join(source, source.id == Information.entity_id)
        .where(
            EventLearning.tenant_id == tenant_id,
            event.tenant_id == tenant_id,
            being.tenant_id == tenant_id,
            Information.tenant_id == tenant_id,
            source.tenant_id == tenant_id,
            visible_entry_clause(vis, being.id),
            visible_information_clause(vis),
        )
        .order_by(
            EventLearning.event_entity_id,
            EventLearning.being_entity_id,
            EventLearning.information_id,
        )
    )
    for value, column in [
        (event_id, EventLearning.event_entity_id),
        (being_id, EventLearning.being_entity_id),
        (information_id, EventLearning.information_id),
    ]:
        if value is not None:
            query = query.where(column == value)
    page = await apaginate(
        session,
        query,
        params,
        transformer=lambda rows: [LearningOut(**row._mapping) for row in rows],
    )
    return cast(Page[LearningOut], page)


@router.get("/events/{event_id}/learning-version")
async def learning_version(
    tenant_id: uuid.UUID,
    event_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> None:
    await require_event_order_access(session, user, tenant_id)
    # The Event is the revision owner, shared with participation edits.
    await session.execute(
        select(Entity.id)
        .where(Entity.tenant_id == tenant_id, Entity.id == event_id)
        .with_for_update()
    )
    event = await read_event(session, tenant_id, event_id)
    response.headers["ETag"] = etag_for(event.updated_at)


async def change_learning(
    tenant_id: uuid.UUID,
    event_id: uuid.UUID,
    being_id: uuid.UUID,
    information_id: uuid.UUID,
    removing: bool,
    if_match: str | None,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> None:
    await require_event_order_access(session, user, tenant_id)
    source_id = await session.scalar(
        select(Information.entity_id).where(
            Information.tenant_id == tenant_id, Information.id == information_id
        )
    )
    if source_id is None:
        raise EntityNotFoundError(detail="No such Information in this library")
    entries = {
        e.id: e
        for e in await session.scalars(
            select(Entity)
            .where(Entity.tenant_id == tenant_id, Entity.id.in_([event_id, being_id, source_id]))
            .order_by(Entity.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    }
    event = await read_event(session, tenant_id, event_id)
    info = await session.scalar(
        select(Information)
        .where(Information.tenant_id == tenant_id, Information.id == information_id)
        .with_for_update()
    )
    if info is None or source_id not in entries or being_id not in entries:
        raise EntityNotFoundError(detail="No such learning endpoints in this library")
    vis = await resolve_information_visibility(session, tenant_id=tenant_id, user_id=user.id)
    visible_source = await session.scalar(
        select(Information.id).where(
            Information.id == information_id,
            Information.tenant_id == tenant_id,
            visible_information_clause(vis),
        )
    )
    if visible_source is None or not vis.can_see_entry(being_id):
        raise EntityNotFoundError(detail="No such learning endpoints in this library")
    participant = await session.get(EventParticipant, (event_id, being_id))
    if participant is None or participant.tenant_id != tenant_id:
        raise EntityNotFoundError(detail="Choose a participating being from this Event")
    if if_match is None:
        raise EventOrderPreconditionRequiredError(
            detail="Refresh the Event learning version and send its ETag in If-Match."
        )
    check_if_match(if_match, updated_at=event.updated_at)
    key = (event_id, being_id, information_id)
    present = await session.get(EventLearning, key)
    if (present is not None) == removing:
        if removing:
            await session.execute(
                delete(EventLearning).where(
                    EventLearning.tenant_id == tenant_id,
                    EventLearning.event_entity_id == event_id,
                    EventLearning.being_entity_id == being_id,
                    EventLearning.information_id == information_id,
                )
            )
        else:
            session.add(
                EventLearning(
                    tenant_id=tenant_id,
                    event_entity_id=event_id,
                    being_entity_id=being_id,
                    information_id=information_id,
                )
            )
        event.updated_at = datetime.now(UTC)
        event.updated_by = user.id
        await record_activity(
            session,
            tenant_id=tenant_id,
            actor_id=user.id,
            action="event.learning_removed" if removing else "event.learning_recorded",
            target_type="entity",
            target_id=event_id,
        )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    response.headers["ETag"] = etag_for(event.updated_at)


@router.put("/events/{event_id}/learning/{being_id}/{information_id}")
async def record_learning(
    tenant_id: uuid.UUID,
    event_id: uuid.UUID,
    being_id: uuid.UUID,
    information_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> None:
    await change_learning(
        tenant_id, event_id, being_id, information_id, False, if_match, response, session, user
    )


@router.delete("/events/{event_id}/learning/{being_id}/{information_id}")
async def remove_learning(
    tenant_id: uuid.UUID,
    event_id: uuid.UUID,
    being_id: uuid.UUID,
    information_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> None:
    await change_learning(
        tenant_id, event_id, being_id, information_id, True, if_match, response, session, user
    )
