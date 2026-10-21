"""Full-visibility Event assertions and derived comparisons (ADR 0312)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, Header, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Boolean, String, Uuid, delete, literal, select, union_all

from lorenzo_api.activity_log import record_activity
from lorenzo_api.dependencies import (
    CurrentUser,
    SessionDep,
    get_tenant_admin_context,
    get_tenant_or_404,
    require_tenant_participant,
    set_tenant_rls_context,
)
from lorenzo_api.entry_visibility import visible_entry_clause
from lorenzo_api.etag import check_if_match, etag_for
from lorenzo_api.event_order_lock import lock_event_order
from lorenzo_api.event_ordering import Edge, EventOrder, Kind
from lorenzo_api.exceptions import (
    EntityNotFoundError,
    EventOrderCycleError,
    EventOrderForbiddenError,
    EventOrderPreconditionRequiredError,
)
from lorenzo_api.information_visibility import InformationVisibility, resolve_information_visibility
from lorenzo_api.models import Entity, EventRelationship, StoryEvent

router = APIRouter(
    prefix="/tenants/{tenant_id}/events",
    tags=["Event order"],
    dependencies=[Depends(get_tenant_or_404)],
)


class RelationshipOut(BaseModel):
    from_event_id: uuid.UUID
    to_event_id: uuid.UUID
    from_name: str
    to_name: str
    kind: Kind
    is_shared: bool = False


class RelationshipWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Kind
    direction: Literal["incoming", "outgoing"] = "outgoing"


class RelationshipSharingWrite(RelationshipWrite):
    is_shared: bool


class EventPair(BaseModel):
    model_config = ConfigDict(extra="forbid")
    left: uuid.UUID
    right: uuid.UUID


class ComparisonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pairs: list[EventPair] = Field(min_length=1, max_length=100)


class EventComparison(EventPair):
    relation: Literal["before", "after", "same"]
    basis: Literal["causal", "ruled", "linearized", "identity"]
    path: list[RelationshipOut]


async def require_event_order_access(
    session: SessionDep, user: CurrentUser, tenant_id: uuid.UUID
) -> None:
    vis = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    if not vis.is_admin:
        raise EventOrderForbiddenError(
            detail="Event ordering requires an Owner or Organizer using full visibility."
        )


async def read_event(session: SessionDep, tenant_id: uuid.UUID, event_id: uuid.UUID) -> Entity:
    entry = await session.scalar(
        select(Entity)
        .join(StoryEvent, StoryEvent.entity_id == Entity.id)
        .where(
            Entity.tenant_id == tenant_id, StoryEvent.tenant_id == tenant_id, Entity.id == event_id
        )
        .execution_options(populate_existing=True)
    )
    if entry is None:
        raise EntityNotFoundError(detail="No such Event in this library")
    return entry


async def graph(
    session: SessionDep, tenant_id: uuid.UUID, visibility: InformationVisibility | None = None
) -> tuple[EventOrder, dict[uuid.UUID, str]]:
    # One statement = one MVCC snapshot of both nodes and assertions.
    # RLS plus fresh tenant statistics can make a normal join repeatedly scan
    # every entry for every Event. Keep the name lookup correlated and indexed;
    # OFFSET 0 prevents flattening it back into that quadratic plan (4,000-Event test).
    name = (
        select(Entity.name)
        .where(Entity.id == StoryEvent.entity_id, Entity.tenant_id == tenant_id)
        .correlate(StoryEvent)
        .offset(0)
        .scalar_subquery()
    )
    nodes = select(
        StoryEvent.entity_id,
        name,
        literal(None, type_=Uuid),
        literal(None, type_=String),
        literal(False, type_=Boolean),
    ).where(StoryEvent.tenant_id == tenant_id)
    edges = select(
        EventRelationship.from_event_id,
        literal(None, type_=String),
        EventRelationship.to_event_id,
        EventRelationship.kind,
        EventRelationship.is_shared,
    ).where(EventRelationship.tenant_id == tenant_id)
    if visibility is not None and not visibility.is_admin:
        nodes = nodes.where(visible_entry_clause(visibility, StoryEvent.entity_id))
        edges = edges.where(
            EventRelationship.is_shared.is_(True),
            visible_entry_clause(visibility, EventRelationship.from_event_id),
            visible_entry_clause(visibility, EventRelationship.to_event_id),
        )
    names: dict[uuid.UUID, str] = {}
    assertions = []
    for source, name, target, kind, shared in await session.execute(union_all(nodes, edges)):
        if target is None:
            names[source] = name
        else:
            assertions.append(Edge(source, target, cast(Kind, kind), is_shared=shared))
    return EventOrder(set(names), assertions), names


def output(edge: Edge, names: dict[uuid.UUID, str]) -> RelationshipOut:
    return RelationshipOut(
        from_event_id=edge.source,
        to_event_id=edge.target,
        from_name=names[edge.source],
        to_name=names[edge.target],
        kind=edge.kind,
        is_shared=edge.is_shared,
    )


@router.post("/compare")
async def compare_events(
    tenant_id: uuid.UUID, body: ComparisonRequest, session: SessionDep, user: CurrentUser
) -> list[EventComparison]:
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    visibility = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    order, names = await graph(session, tenant_id, visibility)
    results = []
    for pair in body.pairs:
        if pair.left not in names or pair.right not in names:
            raise EntityNotFoundError(detail="No such Event in this library")
        relation, basis, path = order.compare(pair.left, pair.right)
        results.append(
            EventComparison(
                left=pair.left,
                right=pair.right,
                relation=relation,
                basis=basis,
                path=[output(e, names) for e in path],
            )
        )
    return results


@router.get("/{event_id}/relationships")
async def list_event_relationships(
    tenant_id: uuid.UUID,
    event_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> list[RelationshipOut]:
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    visibility = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    if visibility.is_admin:
        # The staff ETag guards mutation; readers receive no private revision.
        await lock_event_order(session, tenant_id)
        entry = await read_event(session, tenant_id, event_id)
        response.headers["ETag"] = etag_for(entry.updated_at)
    order, names = await graph(session, tenant_id, visibility)
    if event_id not in names:
        raise EntityNotFoundError(detail="No such Event in this library")
    return [output(e, names) for e in order.edges if event_id in (e.source, e.target)]


async def change_relationship(
    tenant_id: uuid.UUID,
    event_id: uuid.UUID,
    other_event_id: uuid.UUID,
    body: RelationshipWrite,
    if_match: str | None,
    removing: bool,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    sharing: bool | None = None,
) -> list[RelationshipOut]:
    await require_event_order_access(session, user, tenant_id)
    await lock_event_order(session, tenant_id)
    # Same lock order for both endpoints; generic entry edits may hold either row.
    await session.execute(
        select(Entity.id)
        .where(Entity.tenant_id == tenant_id, Entity.id.in_([event_id, other_event_id]))
        .order_by(Entity.id)
        .with_for_update()
    )
    entry = await read_event(session, tenant_id, event_id)
    other = await read_event(session, tenant_id, other_event_id)
    if if_match is None:
        raise EventOrderPreconditionRequiredError(
            detail="Read this Event's relationships and send their ETag in If-Match."
        )
    check_if_match(if_match, updated_at=entry.updated_at)
    source, target = (
        (event_id, other_event_id) if body.direction == "outgoing" else (other_event_id, event_id)
    )
    order, _ = await graph(session, tenant_id)
    edge = Edge(source, target, body.kind)
    present = edge in order.edges
    if (
        not removing
        and not present
        and (source == target or order.path(target, source, causes_only=False))
    ):
        raise EventOrderCycleError(
            detail="This assertion would create a cycle in the recorded Event order."
        )
    changed = False
    if sharing is not None:
        row = await session.get(EventRelationship, (source, target, body.kind))
        if row is None:
            raise EntityNotFoundError(detail="No such Event relationship in this library")
        changed = row.is_shared != sharing
        row.is_shared = sharing
    elif present == removing:
        changed = True
        if removing:
            await session.execute(
                delete(EventRelationship).where(
                    EventRelationship.tenant_id == tenant_id,
                    EventRelationship.from_event_id == source,
                    EventRelationship.to_event_id == target,
                    EventRelationship.kind == body.kind,
                )
            )
        else:
            session.add(
                EventRelationship(
                    tenant_id=tenant_id, from_event_id=source, to_event_id=target, kind=body.kind
                )
            )
    if changed:
        now = datetime.now(UTC)
        for endpoint in (entry, other):
            endpoint.updated_at = now
            endpoint.updated_by = user.id
        await record_activity(
            session,
            tenant_id=tenant_id,
            actor_id=user.id,
            action=(
                "event.relationship_sharing_changed"
                if sharing is not None
                else "event.relationship_removed"
                if removing
                else "event.relationship_added"
            ),
            target_type="entity",
            target_id=event_id,
        )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return await list_event_relationships(tenant_id, event_id, response, session, user)


@router.put(
    "/{event_id}/relationships/{other_event_id}", dependencies=[Depends(get_tenant_admin_context)]
)
async def put_event_relationship(
    tenant_id: uuid.UUID,
    event_id: uuid.UUID,
    other_event_id: uuid.UUID,
    body: RelationshipWrite,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> list[RelationshipOut]:
    return await change_relationship(
        tenant_id, event_id, other_event_id, body, if_match, False, response, session, user
    )


@router.delete(
    "/{event_id}/relationships/{other_event_id}", dependencies=[Depends(get_tenant_admin_context)]
)
async def delete_event_relationship(
    tenant_id: uuid.UUID,
    event_id: uuid.UUID,
    other_event_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    kind: Annotated[Kind, Query()],
    direction: Annotated[Literal["incoming", "outgoing"], Query()] = "outgoing",
    if_match: Annotated[str | None, Header()] = None,
) -> list[RelationshipOut]:
    return await change_relationship(
        tenant_id,
        event_id,
        other_event_id,
        RelationshipWrite(kind=kind, direction=direction),
        if_match,
        True,
        response,
        session,
        user,
    )


@router.put(
    "/{event_id}/relationships/{other_event_id}/sharing",
    dependencies=[Depends(get_tenant_admin_context)],
)
async def share_event_relationship(
    tenant_id: uuid.UUID,
    event_id: uuid.UUID,
    other_event_id: uuid.UUID,
    body: RelationshipSharingWrite,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> list[RelationshipOut]:
    return await change_relationship(
        tenant_id,
        event_id,
        other_event_id,
        body,
        if_match,
        False,
        response,
        session,
        user,
        sharing=body.is_shared,
    )
