"""A bounded shortest-route search over the connections a reader sees (ADR 0367).

Pure: the caller hands in a way to read the connections touching some places, already limited to
what the reader sees, so a hidden connection, end or length is absent before the search begins and
cannot change the answer, the route, a counter or an error. Dijkstra over a cost that is compared
in order: the legs with no length, the sum of the lengths, the number of legs, then the
connections' ids, so a route that is measured beats one that is not and a tie is always broken the
same way.
"""

from __future__ import annotations

import heapq
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Literal

#: At most this many places are discovered, connections read and legs in one route.
MAX_PLACES = 2_000
MAX_CONNECTIONS = 10_000
MAX_LEGS = 64
#: How many not yet read places share the statement that reads the next one.
BATCH = 100

NO_ROUTE = "no known route"
TOO_MUCH = "too much to search"

State = Literal["known", "partial", "unknown", "limit_reached"]


@dataclass(frozen=True, slots=True)
class Edge:
    """A connection between `a` and `b`; one way goes from `a` to `b` only. `length` is None when
    it has none that can be used."""

    connection: uuid.UUID
    a: uuid.UUID
    b: uuid.UUID
    one_way: bool
    length: float | None


@dataclass(frozen=True, slots=True)
class Leg:
    connection: uuid.UUID
    start: uuid.UUID
    end: uuid.UUID
    length: float | None


@dataclass(slots=True)
class Outcome:
    state: State
    legs: list[Leg] = field(default_factory=list)
    total: float = 0.0
    unmeasured: int = 0
    reason: str | None = None


Expand = Callable[[list[uuid.UUID]], Awaitable[list[Edge]]]
_Cost = tuple[int, float, int, tuple[str, ...]]


async def find_route(
    source: uuid.UUID,
    target: uuid.UUID,
    expand: Expand,
    *,
    max_places: int | None = None,
    max_connections: int | None = None,
    max_legs: int | None = None,
) -> Outcome:
    """The best route from `source` to `target`: `known` when every leg has a length (the shortest
    such), `partial` when only a route with unmeasured legs exists (the one with fewest, then the
    shortest), `unknown` when there is none, `limit_reached` when a cap stopped the search."""
    max_places = MAX_PLACES if max_places is None else max_places
    max_connections = MAX_CONNECTIONS if max_connections is None else max_connections
    max_legs = MAX_LEGS if max_legs is None else max_legs
    if source == target:
        return Outcome("known")
    start: _Cost = (0, 0.0, 0, ())
    best: dict[uuid.UUID, _Cost] = {source: start}
    came: dict[uuid.UUID, tuple[uuid.UUID, Edge]] = {}
    heap: list[tuple[_Cost, uuid.UUID]] = [(start, source)]
    out: dict[uuid.UUID, list[tuple[Edge, uuid.UUID]]] = {}
    seen: set[uuid.UUID] = set()
    settled: set[uuid.UUID] = set()
    cut = False
    while heap:
        cost, place = heapq.heappop(heap)
        if place in settled or best[place] != cost:
            continue
        settled.add(place)
        if place == target:
            return _outcome(source, target, came, cost)
        if cost[2] >= max_legs:
            cut = True
            continue
        if place not in out:
            wanted = [place]
            for _, other in heap:
                if other not in out and other not in settled and other not in wanted:
                    wanted.append(other)
                    if len(wanted) >= BATCH:
                        break
            reading = set(wanted)
            for edge in await expand(wanted):
                seen.add(edge.connection)
                if len(seen) > max_connections:
                    return Outcome("limit_reached", reason=TOO_MUCH)
                if edge.a in reading:
                    out.setdefault(edge.a, []).append((edge, edge.b))
                if edge.b in reading and not edge.one_way:
                    out.setdefault(edge.b, []).append((edge, edge.a))
            for each in wanted:
                out.setdefault(each, [])
        for edge, far in out[place]:
            if far in settled:
                continue
            step = _add(cost, edge)
            if far not in best:
                if len(best) >= max_places:
                    return Outcome("limit_reached", reason=TOO_MUCH)
            elif step >= best[far]:
                continue
            best[far] = step
            came[far] = (place, edge)
            heapq.heappush(heap, (step, far))
    if cut:
        return Outcome("limit_reached", reason=TOO_MUCH)
    return Outcome("unknown", reason=NO_ROUTE)


def _add(cost: _Cost, edge: Edge) -> _Cost:
    unmeasured, total, legs, ids = cost
    if edge.length is None:
        unmeasured += 1
    else:
        total = round(total + edge.length, 6)
    return unmeasured, total, legs + 1, (*ids, str(edge.connection))


def _outcome(
    source: uuid.UUID,
    target: uuid.UUID,
    came: dict[uuid.UUID, tuple[uuid.UUID, Edge]],
    cost: _Cost,
) -> Outcome:
    legs: list[Leg] = []
    place = target
    while place != source:
        before, edge = came[place]
        legs.append(Leg(edge.connection, before, place, edge.length))
        place = before
    legs.reverse()
    return Outcome(
        "known" if cost[0] == 0 else "partial",
        legs=legs,
        total=cost[1],
        unmeasured=cost[0],
    )
