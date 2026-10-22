"""Explicit shared/private clock relationships and reader-scoped conversion (ADR 0321)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from fractions import Fraction
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import or_, select, text

from lorenzo_api.clock_conversion import (
    MAX_CLOCKS,
    MAX_RELATIONS,
    ConversionLimit,
    Relation,
    RelationDefinition,
    Resolution,
    Step,
    Work,
    affine,
    canonical,
    overlap,
    resolve,
)
from lorenzo_api.clock_values import ReadingRange
from lorenzo_api.dependencies import (
    CurrentUser,
    SessionDep,
    get_tenant_or_404,
    require_tenant_participant,
)
from lorenzo_api.entry_visibility import visible_entry_clause
from lorenzo_api.exceptions import InvalidKindRequestError
from lorenzo_api.information_visibility import resolve_information_visibility
from lorenzo_api.models import Clock, ClockRelationship, Entity
from lorenzo_api.routers.clocks import (
    commit,
    conditional,
    endpoint,
    lock_clock_entries,
    mutation_lock,
    reading_rows,
    revision,
    ticking_clock,
)
from lorenzo_api.routers.event_order import require_event_order_access

router = APIRouter(
    prefix="/tenants/{tenant_id}", tags=["clocks"], dependencies=[Depends(get_tenant_or_404)]
)


class ClockRelationshipIn(RelationDefinition):
    is_shared: bool = False


class ClockRelationshipOut(ClockRelationshipIn):
    reference_clock_entity_id: uuid.UUID
    reference_clock_name: str


class ClockRelationshipsOut(BaseModel):
    items: list[ClockRelationshipOut]
    can_manage: bool


class ClockConversionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_clock_id: uuid.UUID
    target_clock_id: uuid.UUID
    reading: ReadingRange
    kind: Literal["reading", "duration"] = "reading"


class ClockPathStep(BaseModel):
    source_clock_id: uuid.UUID
    source_clock_name: str
    target_clock_id: uuid.UUID
    target_clock_name: str
    ratio: str
    offset: str


class ClockCandidate(BaseModel):
    source_clock_id: uuid.UUID
    source_clock_name: str
    source_reading: ReadingRange
    reading: ReadingRange
    path: list[ClockPathStep]


class ClockConversionOut(BaseModel):
    status: Literal["entered", "derived", "not_reckoned", "conflicting", "limit_reached"]
    reading: ReadingRange | None = None
    entered_reading: ReadingRange | None = None
    candidates: list[ClockCandidate] = []
    conflict_paths: list[list[ClockPathStep]] = []


class ClockRelationshipPreviewIn(RelationDefinition):
    reference_clock_entity_id: uuid.UUID
    reading: ReadingRange


class ClockRelationshipPreviewOut(BaseModel):
    kind: Literal["reading", "duration"]
    reading: ReadingRange


async def shared_read_lock(session: SessionDep, tenant: uuid.UUID) -> None:
    await session.execute(
        text(
            "SELECT pg_advisory_xact_lock_shared(hashtextextended('lorenzo:clocks:' || :tenant, 0))"
        ),
        {"tenant": str(tenant)},
    )


async def relationship_rows(
    session: SessionDep, user: CurrentUser, tenant: uuid.UUID, clock: uuid.UUID
) -> tuple[list[ClockRelationship], bool]:
    await endpoint(session, user, tenant, clock, Clock)
    vis = await resolve_information_visibility(session, tenant_id=tenant, user_id=user.id)
    manage = vis.is_admin or vis.manages_events
    query = (
        select(ClockRelationship)
        .where(
            ClockRelationship.tenant_id == tenant,
            or_(
                ClockRelationship.clock_entity_id == clock,
                ClockRelationship.reference_clock_entity_id == clock,
            ),
            visible_entry_clause(vis, ClockRelationship.clock_entity_id),
            visible_entry_clause(vis, ClockRelationship.reference_clock_entity_id),
        )
        .order_by(ClockRelationship.clock_entity_id, ClockRelationship.reference_clock_entity_id)
    )
    if not manage:
        query = query.where(ClockRelationship.is_shared.is_(True))
    return list(await session.scalars(query)), manage


def relationship_revision(rows: list[ClockRelationship]) -> str:
    return revision(
        [
            (r.clock_entity_id, r.reference_clock_entity_id, r.data, r.is_shared, r.updated_at)
            for r in rows
        ]
    )


@router.get("/clocks/{clock_id}/relationships")
async def relationships(
    tenant_id: uuid.UUID,
    clock_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    response: Response,
) -> ClockRelationshipsOut:
    rows, manage = await relationship_rows(session, user, tenant_id, clock_id)
    other = [
        r.reference_clock_entity_id if r.clock_entity_id == clock_id else r.clock_entity_id
        for r in rows
    ]
    names = {
        identity: name
        for identity, name in await session.execute(
            select(Entity.id, Entity.name).where(Entity.id.in_(other))
        )
    }
    response.headers["ETag"] = relationship_revision(rows)
    result = []
    for row, reference in zip(rows, other, strict=True):
        value = RelationDefinition.model_validate(row.data)
        if row.clock_entity_id != clock_id:
            value = value.inverse()
        result.append(
            ClockRelationshipOut(
                reference_clock_entity_id=reference,
                reference_clock_name=names[reference],
                **value.model_dump(),
                is_shared=row.is_shared,
            )
        )
    return ClockRelationshipsOut(items=result, can_manage=manage)


@router.put("/clocks/{clock_id}/relationships/{reference_id}")
async def save_relationship(
    tenant_id: uuid.UUID,
    clock_id: uuid.UUID,
    reference_id: uuid.UUID,
    body: ClockRelationshipIn,
    session: SessionDep,
    user: CurrentUser,
    response: Response,
    if_match: Annotated[str | None, Header()] = None,
) -> ClockRelationshipsOut:
    await require_event_order_access(session, user, tenant_id)
    await mutation_lock(session, tenant_id)
    await lock_clock_entries(session, tenant_id, [clock_id, reference_id])
    rows, _ = await relationship_rows(session, user, tenant_id, clock_id)
    conditional(if_match, relationship_revision(rows))
    await ticking_clock(session, user, tenant_id, clock_id)
    await ticking_clock(session, user, tenant_id, reference_id)
    if clock_id == reference_id:
        raise InvalidKindRequestError(detail="Choose two different clocks")
    first, second, value = canonical(
        clock_id,
        reference_id,
        RelationDefinition.model_validate(body.model_dump(exclude={"is_shared"})),
    )
    row = await session.get(ClockRelationship, (first, second))
    if row is None:
        row = ClockRelationship(
            tenant_id=tenant_id, clock_entity_id=first, reference_clock_entity_id=second
        )
        session.add(row)
    row.data = value.model_dump()
    row.is_shared = body.is_shared
    row.updated_at = datetime.now(UTC)
    await commit(session, tenant_id)
    return await relationships(tenant_id, clock_id, session, user, response)


@router.delete("/clocks/{clock_id}/relationships/{reference_id}")
async def remove_relationship(
    tenant_id: uuid.UUID,
    clock_id: uuid.UUID,
    reference_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    response: Response,
    if_match: Annotated[str | None, Header()] = None,
) -> ClockRelationshipsOut:
    await require_event_order_access(session, user, tenant_id)
    await mutation_lock(session, tenant_id)
    await lock_clock_entries(session, tenant_id, [clock_id, reference_id])
    rows, _ = await relationship_rows(session, user, tenant_id, clock_id)
    conditional(if_match, relationship_revision(rows))
    await endpoint(session, user, tenant_id, reference_id, Clock)
    row = next(
        (
            r
            for r in rows
            if {r.clock_entity_id, r.reference_clock_entity_id} == {clock_id, reference_id}
        ),
        None,
    )
    if row is not None:
        await session.delete(row)
        await commit(session, tenant_id)
    return await relationships(tenant_id, clock_id, session, user, response)


@router.post("/clocks/{clock_id}/relationship-preview")
async def preview_relationship(
    tenant_id: uuid.UUID,
    clock_id: uuid.UUID,
    body: ClockRelationshipPreviewIn,
    session: SessionDep,
    user: CurrentUser,
) -> ClockRelationshipPreviewOut:
    await require_event_order_access(session, user, tenant_id)
    await ticking_clock(session, user, tenant_id, clock_id)
    await ticking_clock(session, user, tenant_id, body.reference_clock_entity_id)
    if clock_id == body.reference_clock_entity_id:
        raise InvalidKindRequestError(detail="Choose two different clocks")
    ratio = Fraction(body.ratio)
    offset = (
        Fraction(0)
        if body.clock_anchor is None
        else Fraction(body.clock_anchor) - ratio * Fraction(body.reference_anchor or "0")
    )
    try:
        return ClockRelationshipPreviewOut(
            kind="duration" if body.clock_anchor is None else "reading",
            reading=affine(body.reading, ratio, offset),
        )
    except ConversionLimit:
        raise InvalidKindRequestError(
            detail="Conversion limit reached. Use smaller readings or ratios"
        ) from None


async def permitted_graph(
    session: SessionDep, user: CurrentUser, tenant: uuid.UUID
) -> tuple[list[Relation], dict[uuid.UUID, str]]:
    vis = await resolve_information_visibility(session, tenant_id=tenant, user_id=user.id)
    names = {
        identity: name
        for identity, name in await session.execute(
            select(Clock.entity_id, Entity.name)
            .join(Entity, Entity.id == Clock.entity_id)
            .where(
                Clock.tenant_id == tenant,
                Clock.ticking.is_(True),
                visible_entry_clause(vis, Clock.entity_id),
            )
            .order_by(Clock.entity_id)
            .limit(MAX_CLOCKS + 1)
        )
    }
    if len(names) > MAX_CLOCKS:
        raise ConversionLimit
    query = (
        select(ClockRelationship)
        .where(
            ClockRelationship.tenant_id == tenant,
            ClockRelationship.clock_entity_id.in_(names),
            ClockRelationship.reference_clock_entity_id.in_(names),
        )
        .order_by(ClockRelationship.clock_entity_id, ClockRelationship.reference_clock_entity_id)
        .limit(MAX_RELATIONS + 1)
    )
    if not (vis.is_admin or vis.manages_events):
        query = query.where(ClockRelationship.is_shared.is_(True))
    rows = list(await session.scalars(query))
    if len(rows) > MAX_RELATIONS:
        raise ConversionLimit
    return [
        Relation(
            r.clock_entity_id,
            r.reference_clock_entity_id,
            RelationDefinition.model_validate(r.data),
        )
        for r in rows
    ], names


def path_output(path: list[Step], names: dict[uuid.UUID, str]) -> list[ClockPathStep]:
    return [
        ClockPathStep(
            source_clock_id=s.source,
            source_clock_name=names[s.source],
            target_clock_id=s.target,
            target_clock_name=names[s.target],
            ratio=s.ratio,
            offset=s.offset,
        )
        for s in path
    ]


def conversion(
    relations: list[Relation],
    names: dict[uuid.UUID, str],
    sources: list[tuple[uuid.UUID, ReadingRange]],
    target: uuid.UUID,
    *,
    duration: bool,
) -> ClockConversionOut:
    entered = next((value for identity, value in sources if identity == target), None)
    candidates = []
    conflicts: list[list[ClockPathStep]] = []
    work = Work()
    for source, value in sources:
        result: Resolution = resolve(relations, source, target, value, duration=duration, work=work)
        if result.reading is not None:
            if source != target:
                candidates.append(
                    ClockCandidate(
                        source_clock_id=source,
                        source_clock_name=names[source],
                        source_reading=value,
                        reading=result.reading,
                        path=path_output(result.path, names),
                    )
                )
            conflicts.extend(path_output(path, names) for path in result.conflicts)
    values = [c.reading for c in candidates]
    if entered is not None:
        values.append(entered)
    mismatch = any(
        not overlap(first, second) for i, first in enumerate(values) for second in values[i + 1 :]
    )
    if conflicts or mismatch:
        return ClockConversionOut(
            status="conflicting",
            reading=entered,
            entered_reading=entered,
            candidates=candidates,
            conflict_paths=conflicts[:4],
        )
    if entered is not None:
        return ClockConversionOut(
            status="entered", reading=entered, entered_reading=entered, candidates=candidates
        )
    if not candidates:
        return ClockConversionOut(status="not_reckoned")
    # Compatible intervals constrain a common reading; intersect them rather than picking a source.
    lo = max(Fraction(v.lo) for v in values)
    hi = min(Fraction(v.hi) for v in values)
    lower = all(v.lo_inclusive for v in values if Fraction(v.lo) == lo)
    upper = all(v.hi_inclusive for v in values if Fraction(v.hi) == hi)
    return ClockConversionOut(
        status="derived",
        reading=ReadingRange(lo=str(lo), hi=str(hi), lo_inclusive=lower, hi_inclusive=upper),
        candidates=candidates,
    )


@router.post("/clock-conversions")
async def preview_conversion(
    tenant_id: uuid.UUID,
    body: ClockConversionIn,
    session: SessionDep,
    user: CurrentUser,
    response: Response,
) -> ClockConversionOut:
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    await shared_read_lock(session, tenant_id)
    await ticking_clock(session, user, tenant_id, body.source_clock_id)
    await ticking_clock(session, user, tenant_id, body.target_clock_id)
    response.headers["Cache-Control"] = "no-store"
    try:
        relations, names = await permitted_graph(session, user, tenant_id)
        result = conversion(
            relations,
            names,
            [(body.source_clock_id, body.reading)],
            body.target_clock_id,
            duration=body.kind == "duration",
        )
        # The preview's input is supplied by its caller, not a new entered Event reading.
        if result.status == "entered":
            result.status = "derived"
            result.entered_reading = None
        return result
    except ConversionLimit:
        return ClockConversionOut(status="limit_reached")


@router.get("/events/{event_id}/clock-readings/{clock_id}/derived")
async def derive_event_reading(
    tenant_id: uuid.UUID,
    event_id: uuid.UUID,
    clock_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    response: Response,
) -> ClockConversionOut:
    await shared_read_lock(session, tenant_id)
    rows, _ = await reading_rows(session, user, tenant_id, event_id)
    await ticking_clock(session, user, tenant_id, clock_id)
    response.headers["Cache-Control"] = "no-store"
    try:
        relations, names = await permitted_graph(session, user, tenant_id)
        return conversion(
            relations,
            names,
            [(r.clock_entity_id, ReadingRange.model_validate(r.data)) for r in rows],
            clock_id,
            duration=False,
        )
    except ConversionLimit:
        entered = next(
            (ReadingRange.model_validate(r.data) for r in rows if r.clock_entity_id == clock_id),
            None,
        )
        return ClockConversionOut(status="limit_reached", reading=entered, entered_reading=entered)
