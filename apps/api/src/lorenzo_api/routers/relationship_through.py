"""Relationship through: the chain of relationships one is stated to hold through (ADR 0402).

Nothing here derives a value, a direction or a type, and nothing checks that the steps join the
ends: a chain is authored. A reader sees the steps they may see, in order, with no gap and no
marker."""

from __future__ import annotations

import itertools
import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import aliased

from lorenzo_api.activity_log import record_activity
from lorenzo_api.dependencies import (
    CurrentUser,
    SessionDep,
    get_tenant_or_404,
)
from lorenzo_api.entry_visibility import visible_entry_clause
from lorenzo_api.etag import check_if_match, etag_for
from lorenzo_api.exceptions import (
    InvalidRelationshipError,
    MapPreconditionRequiredError,
)
from lorenzo_api.information_visibility import InformationVisibility
from lorenzo_api.models import Entity, EntityAudience, Relationship, RelationshipThrough
from lorenzo_api.relationships import (
    MAX_THROUGH_STEPS,
    lock_through,
    through_reaches,
    touch_relationship,
)
from lorenzo_api.routers.connections import EntryStub, entry_stubs
from lorenzo_api.routers.locations import require_manager, standing
from lorenzo_api.routers.relationships import RelationshipOut, _commit, _read, build_rows

router = APIRouter(
    prefix="/tenants/{tenant_id}",
    tags=["relationships"],
    dependencies=[Depends(get_tenant_or_404)],
)

#: A problems read lists at most this many rows.
MAX_PROBLEMS = 500


class ThroughPut(BaseModel):
    """The whole chain, in order. An empty list removes it."""

    model_config = ConfigDict(extra="forbid")
    via: list[uuid.UUID] = Field(max_length=MAX_THROUGH_STEPS)


class ThroughOut(BaseModel):
    """The steps the reader may see, in order. A hidden step leaves no gap and no marker."""

    via: list[RelationshipOut]


class RelationshipProblem(BaseModel):
    kind: Literal["through_ends_do_not_meet"]
    relationship: EntryStub
    detail: str


class RelationshipProblems(BaseModel):
    items: list[RelationshipProblem]


async def _steps(
    session: SessionDep, vis: InformationVisibility, tenant: uuid.UUID, identity: uuid.UUID
) -> list[RelationshipOut]:
    """The visible steps of one chain, in order."""
    own = aliased(EntityAudience)
    found = (
        await session.execute(
            select(
                Entity.id,
                Relationship.end_a,
                Relationship.end_b,
                Relationship.one_way,
                Entity.updated_at,
                own.is_public,
                Relationship.starts_at,
                Relationship.ends_at,
            )
            .select_from(RelationshipThrough)
            .join(Entity, Entity.id == RelationshipThrough.via_entity_id)
            .join(Relationship, Relationship.entity_id == Entity.id)
            .outerjoin(own, own.entity_id == Entity.id)
            .where(
                RelationshipThrough.tenant_id == tenant,
                RelationshipThrough.relationship_entity_id == identity,
                visible_entry_clause(vis, Entity.id),
            )
            .order_by(RelationshipThrough.step)
        )
    ).all()
    return await build_rows(session, vis, tenant, found)


@router.get("/relationships/{relationship_id}/through")
async def get_through(
    tenant_id: uuid.UUID,
    relationship_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> ThroughOut:
    vis = await standing(session, user, tenant_id)
    entity, _ = await _read(session, vis, tenant_id, relationship_id)
    response.headers["ETag"] = etag_for(entity.updated_at)
    return ThroughOut(via=await _steps(session, vis, tenant_id, relationship_id))


@router.put("/relationships/{relationship_id}/through")
async def put_through(
    tenant_id: uuid.UUID,
    relationship_id: uuid.UUID,
    body: ThroughPut,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> ThroughOut:
    """Replaces the chain under `If-Match`. Steps the writer cannot see are kept where they are:
    a writer's list replaces only what the writer reads."""
    vis = await require_manager(session, user, tenant_id)
    entity, _ = await _read(session, vis, tenant_id, relationship_id)
    if if_match is None:
        raise MapPreconditionRequiredError(detail="Send the relationship's ETag as If-Match.")
    check_if_match(if_match, updated_at=entity.updated_at)
    wanted = list(body.via)
    if len(set(wanted)) != len(wanted):
        raise InvalidRelationshipError(detail="A relationship appears in a chain once.")
    if relationship_id in wanted:
        raise InvalidRelationshipError(detail="A relationship is not through itself.")
    for step in wanted:
        await _read(session, vis, tenant_id, step)
    await lock_through(session, tenant_id)
    for step in wanted:
        if await through_reaches(session, tenant_id=tenant_id, start=step, target=relationship_id):
            raise InvalidRelationshipError(
                detail="A relationship is not through itself, however far round."
            )
    existing = (
        await session.execute(
            select(RelationshipThrough.step, RelationshipThrough.via_entity_id).where(
                RelationshipThrough.tenant_id == tenant_id,
                RelationshipThrough.relationship_entity_id == relationship_id,
            )
        )
    ).all()
    seen = set(
        await session.scalars(
            select(Entity.id).where(
                Entity.tenant_id == tenant_id,
                Entity.id.in_([via for _, via in existing]),
                visible_entry_clause(vis, Entity.id),
            )
        )
        if existing
        else []
    )
    kept = [(step, via) for step, via in existing if via not in seen]
    if len(kept) + len(wanted) > MAX_THROUGH_STEPS:
        raise InvalidRelationshipError(
            detail=f"A relationship holds through at most {MAX_THROUGH_STEPS} others."
        )
    taken = {step for step, _ in kept}
    free = (n for n in itertools.count(1) if n not in taken)
    if seen:
        await session.execute(
            delete(RelationshipThrough).where(
                RelationshipThrough.tenant_id == tenant_id,
                RelationshipThrough.relationship_entity_id == relationship_id,
                RelationshipThrough.via_entity_id.in_(seen),
            )
        )
    for via in wanted:
        session.add(
            RelationshipThrough(
                relationship_entity_id=relationship_id,
                step=next(free),
                via_entity_id=via,
                tenant_id=tenant_id,
            )
        )
    await session.flush()
    await touch_relationship(
        session, tenant_id=tenant_id, relationship_id=relationship_id, user_id=user.id
    )
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="relationship.updated",
        target_type="entity",
        target_id=relationship_id,
    )
    await _commit(session, tenant_id)
    entity, _ = await _read(session, vis, tenant_id, relationship_id)
    response.headers["ETag"] = etag_for(entity.updated_at)
    return ThroughOut(via=await _steps(session, vis, tenant_id, relationship_id))


def _meets(first: tuple[uuid.UUID, uuid.UUID], steps: list[tuple[uuid.UUID, uuid.UUID]]) -> bool:
    """Whether the steps, in order, join one end of a relationship to the other, from either."""
    for start, goal in (first, first[::-1]):
        here = start
        for a, b in steps:
            if here == a:
                here = b
            elif here == b:
                here = a
            else:
                break
        else:
            if here == goal:
                return True
    return False


@router.get("/relationship-problems")
async def list_relationship_problems(
    tenant_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> RelationshipProblems:
    """For those who manage relationships: what looks wrong in what they can see (ADR 0402).
    Today, a chain whose steps do not join its ends, when every step is visible."""
    vis = await require_manager(session, user, tenant_id)
    ends = aliased(Relationship)
    rows = (
        await session.execute(
            select(
                RelationshipThrough.relationship_entity_id,
                RelationshipThrough.step,
                RelationshipThrough.via_entity_id,
                Relationship.end_a,
                Relationship.end_b,
                ends.end_a,
                ends.end_b,
            )
            .join(
                Relationship, Relationship.entity_id == RelationshipThrough.relationship_entity_id
            )
            .join(ends, ends.entity_id == RelationshipThrough.via_entity_id)
            .where(
                RelationshipThrough.tenant_id == tenant_id,
                visible_entry_clause(vis, RelationshipThrough.relationship_entity_id),
                visible_entry_clause(vis, RelationshipThrough.via_entity_id),
            )
            .order_by(RelationshipThrough.relationship_entity_id, RelationshipThrough.step)
        )
    ).all()
    # A chain with a hidden step is skipped: every one of its steps must be seen.
    total: dict[uuid.UUID, int] = {}
    for (identity,) in (
        await session.execute(
            select(RelationshipThrough.relationship_entity_id)
            .where(RelationshipThrough.tenant_id == tenant_id)
            .order_by(RelationshipThrough.relationship_entity_id)
        )
    ).all():
        total[identity] = total.get(identity, 0) + 1
    chains: dict[uuid.UUID, dict[str, Any]] = {}
    for identity, _step, _via, a, b, via_a, via_b in rows:
        chain = chains.setdefault(identity, {"ends": (a, b), "steps": []})
        chain["steps"].append((via_a, via_b))
    problems: list[uuid.UUID] = [
        identity
        for identity, chain in chains.items()
        if len(chain["steps"]) == total.get(identity) and not _meets(chain["ends"], chain["steps"])
    ][:MAX_PROBLEMS]
    stubs = await entry_stubs(session, tenant_id, set(problems))
    return RelationshipProblems(
        items=[
            RelationshipProblem(
                kind="through_ends_do_not_meet",
                relationship=stubs[identity],
                detail="The steps do not join one end of it to the other.",
            )
            for identity in sorted(problems, key=lambda i: (stubs[i].name, str(i)))
        ]
    )
