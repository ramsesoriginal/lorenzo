"""How far one entry is from another: the straight line on a Map, or a route over the connections
the reader sees (ADR 0366, 0367). Reads only; nothing is stored."""

from __future__ import annotations

import math
import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from lorenzo_map import straight_distance
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.orm import aliased

from lorenzo_api.config import get_settings
from lorenzo_api.connections import readable
from lorenzo_api.dependencies import CurrentUser, SessionDep, get_tenant_or_404
from lorenzo_api.entry_visibility import require_visible_entry, visible_entry_clause
from lorenzo_api.exceptions import (
    EntityNotFoundError,
    InvalidDistanceError,
    StatDefinitionNotFoundError,
)
from lorenzo_api.information_visibility import InformationVisibility
from lorenzo_api.models import (
    Connection,
    Entity,
    Map,
    MapPlacement,
    StatDefinition,
    StatValueType,
    VEffectiveStat,
)
from lorenzo_api.rate_limit import enforce_user_rate_limit
from lorenzo_api.routers.connections import EntryStub, entry_stubs
from lorenzo_api.routers.locations import standing
from lorenzo_api.routing import Edge, Leg, find_route

router = APIRouter(
    prefix="/tenants/{tenant_id}", tags=["distance"], dependencies=[Depends(get_tenant_or_404)]
)

_NO_ENTRY = "No such entry in this library"
_NO_MAP = "No such Map in this library"
_NOT_ONE_MAP = "they are not drawn on one Map"
_NUMERIC = (StatValueType.INT, StatValueType.FLOAT)


class LegOut(BaseModel):
    """One step of a route: the connection, the place it leaves and the one it arrives at, and its
    length in the unit of the answer (null when it has none)."""

    connection: EntryStub
    start: EntryStub
    end: EntryStub
    length: float | None = None


class DistanceOut(BaseModel):
    """An answer. `value` only when `state` is `known`; `partial` says what is measured so far in
    `at_least` and how many legs have no length; `unknown` and `limit_reached` say why in `reason`.
    An unknown distance is never zero."""

    mode: Literal["route", "straight"]
    state: Literal["known", "partial", "unknown", "limit_reached"]
    value: float | None = None
    at_least: float | None = None
    unit: str | None = None
    unmeasured_legs: int | None = None
    route: list[LegOut] = []
    map: EntryStub | None = None
    reason: str | None = None


async def _visible(
    session: SessionDep, user: CurrentUser, tenant: uuid.UUID, identity: uuid.UUID, what: str
) -> None:
    try:
        await require_visible_entry(session, tenant_id=tenant, entity_id=identity, user_id=user.id)
    except EntityNotFoundError:
        raise EntityNotFoundError(detail=what) from None
    # An entry that is not there has no audience to refuse it: it is the same 404.
    if (
        await session.scalar(
            select(Entity.id).where(Entity.tenant_id == tenant, Entity.id == identity)
        )
        is None
    ):
        raise EntityNotFoundError(detail=what)


async def _stat(
    session: SessionDep, tenant: uuid.UUID, identity: uuid.UUID, *, numeric: bool
) -> StatDefinition:
    found = await session.scalar(
        select(StatDefinition).where(
            StatDefinition.id == identity, StatDefinition.tenant_id == tenant
        )
    )
    if found is None:
        raise StatDefinitionNotFoundError(detail=f"No stat definition with id {identity}")
    if numeric and found.value_type not in _NUMERIC:
        raise InvalidDistanceError(detail="A route is measured in a stat that is a number")
    if not numeric and found.value_type is not StatValueType.BOOL:
        raise InvalidDistanceError(detail="A route avoids a tag, which is a yes-or-no stat")
    return found


def _length(value_int: int | None, value_float: float | None, computed: Any) -> float | None:
    """What a connection's effective value of the stat comes to as a length: a number that is not
    negative and is finite. A formula, a missing value and anything else is no length."""
    if computed is not None:
        return None
    value = value_float if value_float is not None else value_int
    if value is None or not math.isfinite(value) or value < 0:
        return None
    return float(value)


def _reader(
    session: SessionDep,
    vis: InformationVisibility,
    tenant: uuid.UUID,
    measure: uuid.UUID,
    avoid: uuid.UUID | None,
) -> Any:
    """Reads the connections touching some places, each with its length: only those the reader
    sees with both ends, and none that carries the tag to avoid."""
    length = aliased(VEffectiveStat)
    tag = aliased(VEffectiveStat)

    async def expand(places: list[uuid.UUID]) -> list[Edge]:
        stmt = (
            select(
                Connection.entity_id,
                Connection.end_a,
                Connection.end_b,
                Connection.one_way,
                length.value_int,
                length.value_float,
                length.computed_entity_id,
            )
            .join(Entity, Entity.id == Connection.entity_id)
            .outerjoin(
                length,
                and_(
                    length.entity_id == Connection.entity_id,
                    length.stat_definition_id == measure,
                ),
            )
            .where(
                Connection.tenant_id == tenant,
                Connection.end_a.in_(places) | Connection.end_b.in_(places),
                readable(vis),
            )
            .order_by(Connection.entity_id)
        )
        if avoid is not None:
            stmt = stmt.outerjoin(
                tag,
                and_(tag.entity_id == Connection.entity_id, tag.stat_definition_id == avoid),
            ).where(tag.value_bool.is_not(True))
        rows = (await session.execute(stmt)).all()
        return [
            Edge(row[0], row[1], row[2], bool(row[3]), _length(row[4], row[5], row[6]))
            for row in rows
        ]

    return expand


async def _route(
    session: SessionDep,
    vis: InformationVisibility,
    tenant: uuid.UUID,
    source: uuid.UUID,
    target: uuid.UUID,
    measure: uuid.UUID | None,
    avoid: uuid.UUID | None,
) -> DistanceOut:
    if measure is None:
        raise InvalidDistanceError(detail="A route needs a stat to measure it in")
    stat = await _stat(session, tenant, measure, numeric=True)
    if avoid is not None:
        await _stat(session, tenant, avoid, numeric=False)
    outcome = await find_route(source, target, _reader(session, vis, tenant, measure, avoid))
    if outcome.state in ("unknown", "limit_reached"):
        return DistanceOut(mode="route", state=outcome.state, reason=outcome.reason)
    ids = {source, target}
    for leg in outcome.legs:
        ids |= {leg.connection, leg.start, leg.end}
    stubs = await entry_stubs(session, tenant, ids)
    route = [_leg(stubs, leg) for leg in outcome.legs]
    if outcome.state == "known":
        return DistanceOut(
            mode="route", state="known", value=outcome.total, unit=stat.unit, route=route
        )
    return DistanceOut(
        mode="route",
        state="partial",
        at_least=outcome.total,
        unit=stat.unit,
        unmeasured_legs=outcome.unmeasured,
        route=route,
    )


def _leg(stubs: dict[uuid.UUID, EntryStub], leg: Leg) -> LegOut:
    return LegOut(
        connection=stubs[leg.connection],
        start=stubs[leg.start],
        end=stubs[leg.end],
        length=leg.length,
    )


async def _straight(
    session: SessionDep,
    vis: InformationVisibility,
    tenant: uuid.UUID,
    source: uuid.UUID,
    target: uuid.UUID,
    on: uuid.UUID | None,
) -> DistanceOut:
    here, there = aliased(MapPlacement), aliased(MapPlacement)
    stmt = (
        select(Map, here, there, Entity.name)
        .join(here, here.map_entity_id == Map.entity_id)
        .join(
            there,
            and_(there.map_entity_id == Map.entity_id, there.tenant_id == here.tenant_id),
        )
        .join(Entity, Entity.id == Map.entity_id)
        .where(
            Map.tenant_id == tenant,
            here.entry_entity_id == source,
            there.entry_entity_id == target,
            visible_entry_clause(vis, Map.entity_id),
        )
        .order_by(Entity.name, Map.entity_id)
    )
    if on is not None:
        stmt = stmt.where(Map.entity_id == on)
    found = (await session.execute(stmt)).all()
    if not found:
        return DistanceOut(mode="straight", state="unknown", reason=_NOT_ONE_MAP)
    if on is None and len(found) > 1:
        raise InvalidDistanceError(
            detail="More than one Map holds both places; say which with `map`"
        )
    drawn, a, b, _ = found[0]
    answer = straight_distance(
        drawn.system,
        ((a.minx + a.maxx) / 2, (a.miny + a.maxy) / 2),
        ((b.minx + b.maxx) / 2, (b.miny + b.maxy) / 2),
    )
    stub = (await entry_stubs(session, tenant, {drawn.entity_id}))[drawn.entity_id]
    if answer["state"] == "known":
        return DistanceOut(
            mode="straight", state="known", value=answer["value"], unit=answer["unit"], map=stub
        )
    return DistanceOut(mode="straight", state="unknown", reason=answer["reason"], map=stub)


@router.get("/distance")
async def read_distance(
    tenant_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    from_: Annotated[uuid.UUID, Query(alias="from", description="The entry to measure from.")],
    to: Annotated[uuid.UUID, Query(description="The entry to measure to.")],
    mode: Annotated[
        Literal["route", "straight"],
        Query(description="`route` follows connections; `straight` measures on a Map."),
    ] = "route",
    measure: Annotated[
        uuid.UUID | None,
        Query(description="The number stat a connection's length is read from (a route)."),
    ] = None,
    avoid: Annotated[
        uuid.UUID | None,
        Query(description="A yes-or-no stat; a connection that has it is not followed (a route)."),
    ] = None,
    map: Annotated[  # noqa: A002 - the query parameter's name
        uuid.UUID | None, Query(description="The Map to measure on (a straight line).")
    ] = None,
) -> DistanceOut:
    """How far `from` is from `to` (ADR 0366, 0367): the straight line between the two places on a
    Map, or the shortest route over the connections the reader sees, measured in a stat. Only what
    the reader sees counts, so what is hidden changes no answer."""
    vis = await standing(session, user, tenant_id)
    enforce_user_rate_limit(
        "distance",
        per_minute=get_settings().distance_rate_limit_per_minute,
        user_key=f"user:{user.id}",
    )
    await _visible(session, user, tenant_id, from_, _NO_ENTRY)
    await _visible(session, user, tenant_id, to, _NO_ENTRY)
    if mode == "straight":
        if map is not None:
            await _visible(session, user, tenant_id, map, _NO_MAP)
            if await session.get(Map, map) is None:
                raise EntityNotFoundError(detail=_NO_MAP)
        return await _straight(session, vis, tenant_id, from_, to, map)
    return await _route(session, vis, tenant_id, from_, to, measure, avoid)
