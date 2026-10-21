"""Explicit lived-before support on existing participations; no inferred memory."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from lorenzo_api.activity_log import record_activity
from lorenzo_api.dependencies import (
    CurrentUser,
    SessionDep,
    get_tenant_or_404,
    require_tenant_participant,
    set_tenant_rls_context,
)
from lorenzo_api.entry_visibility import require_visible_entry, visible_entry_clause
from lorenzo_api.etag import check_if_match, etag_for
from lorenzo_api.event_order_lock import lock_event_order
from lorenzo_api.event_ordering import Edge, EventOrder
from lorenzo_api.exceptions import (
    EntityNotFoundError,
    EventOrderCycleError,
    EventOrderPreconditionRequiredError,
    InvalidKindRequestError,
)
from lorenzo_api.information_visibility import resolve_information_visibility
from lorenzo_api.models import Being, Entity, EventParticipant, LivedBefore
from lorenzo_api.routers.event_order import (
    RelationshipOut,
    graph,
    output,
    require_event_order_access,
)
from lorenzo_api.routers.story_sessions import touch

router = APIRouter(
    prefix="/tenants/{tenant_id}/beings/{being_id}/lived-order",
    tags=["Personal lived order"],
    dependencies=[Depends(get_tenant_or_404)],
)


class LivedParticipation(BaseModel):
    event_id: uuid.UUID
    name: str


class LivedOrderOut(BaseModel):
    being_id: uuid.UUID
    name: str
    can_manage: bool
    participations: list[LivedParticipation]
    assertions: list[RelationshipOut]


class LivedAssertion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_event_id: uuid.UUID
    to_event_id: uuid.UUID
    is_shared: bool = False


class LivedOrderWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assertions: list[LivedAssertion] = Field(min_length=1, max_length=200)


async def read_being(
    session: SessionDep, tenant: uuid.UUID, being: uuid.UUID, user: CurrentUser
) -> Entity:
    await require_tenant_participant(session, tenant_id=tenant, user=user)
    await require_visible_entry(session, tenant_id=tenant, entity_id=being, user_id=user.id)
    entry = await session.scalar(
        select(Entity)
        .join(Being, Being.entity_id == Entity.id)
        .where(Entity.tenant_id == tenant, Being.tenant_id == tenant, Entity.id == being)
        .execution_options(populate_existing=True)
    )
    if entry is None:
        raise EntityNotFoundError(detail="No such being")
    return entry


@router.get("")
async def read_lived_order(
    tenant_id: uuid.UUID,
    being_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> LivedOrderOut:
    entry = await read_being(session, tenant_id, being_id, user)
    vis = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    manager = vis.is_admin or vis.manages_events
    order, names = await graph(session, tenant_id, vis)
    rows = await session.execute(
        select(EventParticipant.event_entity_id, Entity.name)
        .join(Entity, Entity.id == EventParticipant.event_entity_id)
        .where(
            EventParticipant.tenant_id == tenant_id,
            Entity.tenant_id == tenant_id,
            EventParticipant.being_entity_id == being_id,
            visible_entry_clause(vis, EventParticipant.event_entity_id),
        )
        .order_by(Entity.name, Entity.id)
    )
    if manager:
        response.headers["ETag"] = etag_for(entry.updated_at)
    response.headers["Cache-Control"] = "private, no-store"
    return LivedOrderOut(
        being_id=being_id,
        name=entry.name,
        can_manage=manager,
        participations=[LivedParticipation(event_id=e, name=n) for e, n in rows],
        assertions=[output(e, names) for e in order.edges if e.being_id == being_id],
    )


async def mutate_lived(
    tenant: uuid.UUID,
    being: uuid.UUID,
    assertions: list[LivedAssertion],
    removing: bool,
    version: str | None,
    session: SessionDep,
    user: CurrentUser,
) -> None:
    await require_event_order_access(session, user, tenant)
    await lock_event_order(session, tenant)
    ids = {being} | {i for a in assertions for i in [a.from_event_id, a.to_event_id]}
    await session.execute(
        select(Entity.id)
        .where(Entity.tenant_id == tenant, Entity.id.in_(ids))
        .order_by(Entity.id)
        .with_for_update()
    )
    entry = await read_being(session, tenant, being, user)
    if version is None:
        raise EventOrderPreconditionRequiredError(
            detail="Read the being's lived order and send its ETag"
        )
    check_if_match(version, updated_at=entry.updated_at)
    pairs = [(a.from_event_id, a.to_event_id) for a in assertions]
    if len(set(pairs)) != len(pairs):
        raise InvalidKindRequestError(detail="Each assertion must be listed once")
    participants = set(
        await session.scalars(
            select(EventParticipant.event_entity_id).where(
                EventParticipant.tenant_id == tenant, EventParticipant.being_entity_id == being
            )
        )
    )
    if not {i for pair in pairs for i in pair} <= participants:
        raise EntityNotFoundError(detail="Both Events need this being's recorded participation")
    for event in {i for pair in pairs for i in pair}:
        await require_visible_entry(session, tenant_id=tenant, entity_id=event, user_id=user.id)
    order, _ = await graph(session, tenant)
    if not removing:
        edges = order.edges + [
            Edge(a.from_event_id, a.to_event_id, "order", being_id=being) for a in assertions
        ]
        try:
            EventOrder(set(order.positions), edges)
        except ValueError as error:
            raise EventOrderCycleError(
                detail="This conflicts with recorded Event order; correct the assertions first"
            ) from error
    changed = False
    for assertion in assertions:
        key = (being, assertion.from_event_id, assertion.to_event_id)
        old = await session.get(LivedBefore, key)
        if removing:
            if old is not None:
                await session.delete(old)
                changed = True
        elif old is None:
            session.add(
                LivedBefore(
                    tenant_id=tenant,
                    being_entity_id=being,
                    from_event_id=assertion.from_event_id,
                    to_event_id=assertion.to_event_id,
                    is_shared=assertion.is_shared,
                )
            )
            changed = True
        elif old.is_shared != assertion.is_shared:
            old.is_shared = assertion.is_shared
            changed = True
    if changed:
        for endpoint in await session.scalars(
            select(Entity).where(Entity.tenant_id == tenant, Entity.id.in_(ids))
        ):
            await touch(session, endpoint, user)
        await record_activity(
            session,
            tenant_id=tenant,
            actor_id=user.id,
            action="event.lived_before_removed" if removing else "event.lived_before_recorded",
            target_type="entity",
            target_id=being,
        )
    await session.commit()


@router.put("")
async def write_lived_order(
    tenant_id: uuid.UUID,
    being_id: uuid.UUID,
    body: LivedOrderWrite,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> LivedOrderOut:
    await mutate_lived(tenant_id, being_id, body.assertions, False, if_match, session, user)
    await set_tenant_rls_context(session, tenant_id)
    return await read_lived_order(tenant_id, being_id, response, session, user)


@router.delete("/{from_event_id}/{to_event_id}")
async def remove_lived_order(
    tenant_id: uuid.UUID,
    being_id: uuid.UUID,
    from_event_id: uuid.UUID,
    to_event_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> LivedOrderOut:
    await mutate_lived(
        tenant_id,
        being_id,
        [LivedAssertion(from_event_id=from_event_id, to_event_id=to_event_id)],
        True,
        if_match,
        session,
        user,
    )
    await set_tenant_rls_context(session, tenant_id)
    return await read_lived_order(tenant_id, being_id, response, session, user)
