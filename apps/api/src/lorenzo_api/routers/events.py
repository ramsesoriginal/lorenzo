"""Event discovery and explicit participating beings (ADR 0313)."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi_pagination import Page, create_page
from fastapi_pagination.ext.sqlalchemy import apaginate
from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from lorenzo_api.activity_log import record_activity
from lorenzo_api.client_ids import existing_in_tenant, insert_with_client_id
from lorenzo_api.dependencies import (
    CurrentUser,
    ParamsDep,
    SessionDep,
    get_tenant_or_404,
    require_tenant_participant,
    set_tenant_rls_context,
)
from lorenzo_api.entry_visibility import visible_entry_clause
from lorenzo_api.etag import check_if_match, etag_for
from lorenzo_api.event_fact_access import edits_event_fact
from lorenzo_api.exceptions import (
    ClientIdUnavailableError,
    EntityNotFoundError,
    EventOrderPreconditionRequiredError,
)
from lorenzo_api.information_visibility import resolve_information_visibility
from lorenzo_api.learning import require_no_learning
from lorenzo_api.models import (
    Being,
    Entity,
    EntitySlug,
    EventGroupCreation,
    EventParticipant,
    GroupMember,
    StoryEvent,
)
from lorenzo_api.routers.event_order import graph, read_event, require_event_order_access
from lorenzo_api.schemas.common import EntitySummary

router = APIRouter(
    prefix="/tenants/{tenant_id}/events", tags=["Events"], dependencies=[Depends(get_tenant_or_404)]
)


class EventSummary(BaseModel):
    entity_id: uuid.UUID
    name: str
    slug: str | None = None
    order_basis: Literal["causal", "ruled", "linearized"] | None = None


class ParticipantOut(BaseModel):
    being_entity_id: uuid.UUID
    name: str
    slug: str | None = None


class EventAccess(BaseModel):
    can_order: bool
    can_read_order: bool
    can_retain_private: bool


@router.get("/access")
async def event_access(tenant_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> EventAccess:
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    visibility = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    return EventAccess(
        can_order=visibility.is_admin or visibility.manages_events,
        can_read_order=True,
        can_retain_private=visibility.is_admin,
    )


@router.get("")
async def browse_events(
    tenant_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    params: ParamsDep,
    q: Annotated[str, Query(max_length=200)] = "",
    being_id: uuid.UUID | None = None,
    causal_event_id: uuid.UUID | None = None,
    direction: Literal["ancestors", "descendants", "both"] = "both",
    sort: Literal["name", "order"] = "name",
) -> Page[EventSummary]:
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    structured = being_id is not None or causal_event_id is not None or sort == "order"
    if being_id is not None:
        await require_event_order_access(session, user, tenant_id)
    vis = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    if not structured:
        # Indexed correlated metadata avoids the fresh-tenant RLS join plan
        # profiled in ADR 0312's 4,000-Event fixture.
        name = (
            select(Entity.name)
            .where(Entity.id == StoryEvent.entity_id, Entity.tenant_id == tenant_id)
            .correlate(StoryEvent)
            .offset(0)
            .scalar_subquery()
        )
        slug = (
            select(EntitySlug.slug)
            .where(EntitySlug.entity_id == StoryEvent.entity_id, EntitySlug.tenant_id == tenant_id)
            .correlate(StoryEvent)
            .offset(0)
            .scalar_subquery()
        )
        query = (
            select(StoryEvent.entity_id, name, slug)
            .where(
                StoryEvent.tenant_id == tenant_id, visible_entry_clause(vis, StoryEvent.entity_id)
            )
            .order_by(name, StoryEvent.entity_id)
        )
        if q:
            query = query.where(name.ilike("%" + q + "%"))
        page = await apaginate(
            session,
            query,
            params,
            transformer=lambda rows: [
                EventSummary(entity_id=e, name=n, slug=s) for e, n, s in rows
            ],
        )
        return cast(Page[EventSummary], page)
    order, names = await graph(session, tenant_id, vis)
    selected = set(names)
    if being_id is not None:
        if not await session.scalar(
            select(Being.entity_id).where(Being.entity_id == being_id, Being.tenant_id == tenant_id)
        ):
            raise EntityNotFoundError(detail="No such being in this library")
        selected &= set(
            await session.scalars(
                select(EventParticipant.event_entity_id).where(
                    EventParticipant.tenant_id == tenant_id,
                    EventParticipant.being_entity_id == being_id,
                )
            )
        )
    if causal_event_id is not None:
        if causal_event_id not in names:
            raise EntityNotFoundError(detail="No such Event in this library")
        forward: dict[uuid.UUID, set[uuid.UUID]] = {}
        reverse: dict[uuid.UUID, set[uuid.UUID]] = {}
        for edge in order.edges:
            if edge.kind == "causes":
                forward.setdefault(edge.source, set()).add(edge.target)
                reverse.setdefault(edge.target, set()).add(edge.source)

        def reachable(edges: dict[uuid.UUID, set[uuid.UUID]]) -> set[uuid.UUID]:
            found = {causal_event_id}
            pending = [causal_event_id]
            while pending:
                for target in edges.get(pending.pop(), set()):
                    if target not in found:
                        found.add(target)
                        pending.append(target)
            return found

        related = {causal_event_id}
        if direction != "ancestors":
            related |= reachable(forward)
        if direction != "descendants":
            related |= reachable(reverse)
        selected &= related
    ids = [e for e in selected if q.casefold() in names[e].casefold()]
    ids.sort(key=lambda e: order.positions[e] if sort == "order" else (names[e], e))
    start = (params.page - 1) * params.size
    page_ids = ids[start : start + params.size]
    slugs = dict(
        (
            await session.execute(
                select(EntitySlug.entity_id, EntitySlug.slug).where(
                    EntitySlug.tenant_id == tenant_id, EntitySlug.entity_id.in_(page_ids)
                )
            )
        )
        .tuples()
        .all()
    )
    summaries = []
    for offset, e in enumerate(page_ids, start):
        basis = order.compare(ids[offset - 1], e)[1] if sort == "order" and offset else None
        summaries.append(
            EventSummary(entity_id=e, name=names[e], slug=slugs.get(e), order_basis=basis)
        )
    return cast(Page[EventSummary], create_page(summaries, total=len(ids), params=params))


@router.get("/{event_id}/participants", dependencies=[Depends(get_tenant_or_404)])
async def list_event_participants(
    tenant_id: uuid.UUID,
    event_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> list[ParticipantOut]:
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    if not await edits_event_fact(
        session, tenant_id=tenant_id, user_id=user.id, entity_id=event_id
    ):
        await require_event_order_access(session, user, tenant_id)
    await session.execute(
        select(Entity.id)
        .where(Entity.tenant_id == tenant_id, Entity.id == event_id)
        .with_for_update()
    )
    entry = await read_event(session, tenant_id, event_id)
    rows = await session.execute(
        select(EventParticipant.being_entity_id, Entity.name, EntitySlug.slug)
        .join(Entity, Entity.id == EventParticipant.being_entity_id)
        .outerjoin(EntitySlug, EntitySlug.entity_id == Entity.id)
        .where(
            EventParticipant.tenant_id == tenant_id,
            Entity.tenant_id == tenant_id,
            EventParticipant.event_entity_id == event_id,
        )
        .order_by(Entity.name, Entity.id)
    )
    response.headers["ETag"] = etag_for(entry.updated_at)
    return [ParticipantOut(being_entity_id=e, name=n, slug=s) for e, n, s in rows]


async def change_participation(
    tenant_id: uuid.UUID,
    event_id: uuid.UUID,
    being_id: uuid.UUID,
    removing: bool,
    if_match: str | None,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> list[ParticipantOut]:
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    if not await edits_event_fact(
        session, tenant_id=tenant_id, user_id=user.id, entity_id=event_id
    ):
        await require_event_order_access(session, user, tenant_id)
    # Both endpoints are locked before existence/version checks; deletion uses the same rows.
    entries = {
        e.id: e
        for e in await session.scalars(
            select(Entity)
            .where(Entity.tenant_id == tenant_id, Entity.id.in_([event_id, being_id]))
            .order_by(Entity.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    }
    entry = await read_event(session, tenant_id, event_id)
    being = await session.scalar(
        select(Being).where(Being.tenant_id == tenant_id, Being.entity_id == being_id)
    )
    if being is None or being_id not in entries:
        raise EntityNotFoundError(detail="No such being in this library")
    if if_match is None:
        raise EventOrderPreconditionRequiredError(
            detail="Read the Event participants and send their ETag in If-Match."
        )
    check_if_match(if_match, updated_at=entry.updated_at)
    key = (event_id, being_id)
    present = await session.get(EventParticipant, key)
    if (present is not None) == removing:
        if removing:
            await require_no_learning(session, tenant_id, event_id=event_id, being_id=being_id)
            await session.execute(
                delete(EventParticipant).where(
                    EventParticipant.tenant_id == tenant_id,
                    EventParticipant.event_entity_id == event_id,
                    EventParticipant.being_entity_id == being_id,
                )
            )
        else:
            session.add(
                EventParticipant(
                    tenant_id=tenant_id, event_entity_id=event_id, being_entity_id=being_id
                )
            )
        for endpoint in (entry, entries[being_id]):
            endpoint.updated_at = datetime.now(UTC)
            endpoint.updated_by = user.id
        await record_activity(
            session,
            tenant_id=tenant_id,
            actor_id=user.id,
            action="event.participant_removed" if removing else "event.participant_added",
            target_type="entity",
            target_id=event_id,
        )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return await list_event_participants(tenant_id, event_id, response, session, user)


@router.put("/{event_id}/participants/{being_id}", dependencies=[Depends(get_tenant_or_404)])
async def add_event_participant(
    tenant_id: uuid.UUID,
    event_id: uuid.UUID,
    being_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> list[ParticipantOut]:
    return await change_participation(
        tenant_id, event_id, being_id, False, if_match, response, session, user
    )


@router.delete("/{event_id}/participants/{being_id}", dependencies=[Depends(get_tenant_or_404)])
async def remove_event_participant(
    tenant_id: uuid.UUID,
    event_id: uuid.UUID,
    being_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> list[ParticipantOut]:
    return await change_participation(
        tenant_id, event_id, being_id, True, if_match, response, session, user
    )


class ParticipantGroupCreate(BaseModel):
    id: uuid.UUID
    name: str = Field(min_length=1, max_length=300)


@router.post("/{event_id}/participant-groups", status_code=201)
async def group_from_participants(
    tenant_id: uuid.UUID,
    event_id: uuid.UUID,
    body: ParticipantGroupCreate,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> EntitySummary:
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    await require_event_order_access(session, user, tenant_id)
    if if_match is None:
        raise EventOrderPreconditionRequiredError(
            detail="Preview the Event participants and send their ETag in If-Match"
        )
    await session.execute(
        select(Entity.id)
        .where(Entity.tenant_id == tenant_id, Entity.id == event_id)
        .with_for_update()
    )
    event = await read_event(session, tenant_id, event_id)
    fingerprint = hashlib.sha256(
        json.dumps([str(event_id), body.name, if_match], ensure_ascii=False).encode()
    ).hexdigest()
    receipt = await session.get(EventGroupCreation, body.id)
    if receipt is not None:
        if (
            receipt.tenant_id != tenant_id
            or receipt.created_by != user.id
            or receipt.request_hash != fingerprint
        ):
            raise ClientIdUnavailableError(detail="That id is not available for this creation")
        group = await session.get(Entity, body.id)
        assert group is not None
        response.status_code = 200
        return EntitySummary.from_entity(group)
    if await existing_in_tenant(session, Entity, body.id, tenant_id) is not None:
        raise ClientIdUnavailableError(detail="That id is not available for this creation")
    check_if_match(if_match, updated_at=event.updated_at)
    member_ids = list(
        await session.scalars(
            select(EventParticipant.being_entity_id)
            .where(
                EventParticipant.tenant_id == tenant_id,
                EventParticipant.event_entity_id == event_id,
            )
            .order_by(EventParticipant.being_entity_id)
        )
    )
    group = Entity(
        id=body.id, tenant_id=tenant_id, name=body.name, created_by=user.id, updated_by=user.id
    )
    await insert_with_client_id(session, group)
    for member_id in member_ids:
        session.add(
            GroupMember(
                tenant_id=tenant_id, group_entity_id=group.id, character_entity_id=member_id
            )
        )
    session.add(
        EventGroupCreation(
            group_entity_id=group.id,
            tenant_id=tenant_id,
            created_by=user.id,
            request_hash=fingerprint,
        )
    )
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="group.created",
        target_type="group",
        target_id=group.id,
    )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    response.headers["Location"] = str(
        request.url_for("get_group", tenant_id=tenant_id, group_entity_id=group.id)
    )
    response.headers["ETag"] = etag_for(group.updated_at)
    return EntitySummary.from_entity(group)
