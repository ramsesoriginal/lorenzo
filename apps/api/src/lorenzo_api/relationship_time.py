"""Reading relationships as of an Event, and what deleting a bounding Event leaves (ADR 0405).

A relationship may name two Events, where it starts and where it ends. Whether it holds as of
another Event is answered only from what the reader's own authorised graph records: a path of
`causal` or `ruled` assertions. A `linearized` position is a display order and decides nothing."""

from __future__ import annotations

import uuid
from collections import deque
from typing import Literal

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.description_payloads import write_description
from lorenzo_api.event_ordering import EventOrder
from lorenzo_api.models import Entity, Information, Payload, Relationship

State = Literal["holds", "not_yet", "ended", "unknown"]
STATES: tuple[State, ...] = ("holds", "not_yet", "ended", "unknown")

#: The reachability sets of an Event are bounded in code (*proposed default*); past it the
#: answer is `limit_reached` and no row is classed.
MAX_REACH_EVENTS = 2_000


class ReachLimitReachedError(Exception):
    """An Event reaches more Events than the bound allows."""


def reach(order: EventOrder, event: uuid.UUID) -> tuple[set[uuid.UUID], set[uuid.UUID]]:
    """The Events recorded before `event` and those recorded after it, over the graph given.
    Raises `ReachLimitReachedError` past the bound."""
    after: set[uuid.UUID] = set()
    queue = deque([event])
    while queue:
        for edge in order.outgoing[queue.popleft()]:
            if edge.target not in after and edge.target != event:
                after.add(edge.target)
                if len(after) > MAX_REACH_EVENTS:
                    raise ReachLimitReachedError
                queue.append(edge.target)
    incoming: dict[uuid.UUID, set[uuid.UUID]] = {}
    for edges in order.outgoing.values():
        for edge in edges:
            incoming.setdefault(edge.target, set()).add(edge.source)
    before: set[uuid.UUID] = set()
    queue = deque([event])
    while queue:
        for source in incoming.get(queue.popleft(), ()):
            if source not in before and source != event:
                before.add(source)
                if len(before) > MAX_REACH_EVENTS:
                    raise ReachLimitReachedError
                queue.append(source)
    return before, after


def classify(
    starts_at: uuid.UUID | None,
    ends_at: uuid.UUID | None,
    event: uuid.UUID,
    before: set[uuid.UUID],
    after: set[uuid.UUID],
) -> State:
    """Whether a relationship holds as of `event`. A limit that the reader's graph does not place
    (a hidden Event, or none recorded against this one) makes the answer `unknown`."""
    if ends_at is not None and (ends_at == event or ends_at in before):
        return "ended"
    if starts_at is not None and starts_at in after:
        return "not_yet"
    started = starts_at is None or starts_at == event or starts_at in before
    not_ended = ends_at is None or ends_at in after
    return "holds" if started and not_ended else "unknown"


async def note_deleted_event(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    event_id: uuid.UUID,
    event_name: str,
    user_id: uuid.UUID,
) -> int:
    """Before an Event is deleted: a note on each relationship it bounded, restricted to staff,
    saying so. The key then clears the reference, so the relationship does not silently become
    unbounded and the note is the only record (ADR 0405). Returns how many notes were left."""
    bounded = (
        await session.execute(
            select(Relationship.entity_id, Relationship.starts_at, Relationship.ends_at).where(
                Relationship.tenant_id == tenant_id,
                or_(Relationship.starts_at == event_id, Relationship.ends_at == event_id),
            )
        )
    ).all()
    for relationship_id, starts_at, _ends_at in bounded:
        verb = "started" if starts_at == event_id else "ended"
        entity = await session.get(Entity, relationship_id)
        assert entity is not None
        information = Information(
            tenant_id=tenant_id,
            entity_id=relationship_id,
            title="An Event that bounded this was deleted",
            type="note",
            is_public=False,
            created_by=user_id,
        )
        session.add(information)
        await session.flush()
        payload = Payload(tenant_id=tenant_id, information_id=information.id)
        await write_description(
            session,
            payload=payload,
            content=f'The Event "{event_name}" {verb} this relationship and was deleted.',
            locale="und",
        )
    await session.flush()
    return len(bounded)
