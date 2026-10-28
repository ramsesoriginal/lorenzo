"""Is a polygon simple? Exact integer arithmetic on millionths, and a budget of segment tests.

A polygon is simple when its edges never cross or touch except where neighbours meet, a hole lies
inside the outer ring, and no ring touches or sits inside another hole (ADR 0337). Concave is
allowed; a star that crosses itself is not.
"""

from __future__ import annotations

from collections.abc import Sequence

from lorenzo_map.errors import MapDocumentError
from lorenzo_map.limits import SIMPLICITY_BUDGET

IntPoint = tuple[int, int]
Ring = Sequence[IntPoint]


def _orient(a: IntPoint, b: IntPoint, c: IntPoint) -> int:
    value = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    return (value > 0) - (value < 0)


def _within(a: IntPoint, b: IntPoint, p: IntPoint) -> bool:
    """p, known to be on the line through a and b, is between them."""
    return min(a[0], b[0]) <= p[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= p[1] <= max(a[1], b[1])


def _touch(a: IntPoint, b: IntPoint, c: IntPoint, d: IntPoint) -> bool:
    """The closed segments ab and cd share at least one point."""
    o1, o2 = _orient(a, b, c), _orient(a, b, d)
    o3, o4 = _orient(c, d, a), _orient(c, d, b)
    if o1 != o2 and o3 != o4:
        return True
    return (
        (o1 == 0 and _within(a, b, c))
        or (o2 == 0 and _within(a, b, d))
        or (o3 == 0 and _within(c, d, a))
        or (o4 == 0 and _within(c, d, b))
    )


def _inside(ring: Ring, p: IntPoint) -> bool:
    """p is strictly inside the ring (a point on its boundary is not)."""
    inside = False
    n = len(ring)
    for i in range(n):
        a, b = ring[i], ring[(i + 1) % n]
        if _orient(a, b, p) == 0 and _within(a, b, p):
            return False
        if (a[1] > p[1]) != (b[1] > p[1]):
            # Which side of p the edge crosses the horizontal through p, exactly.
            cross = (b[0] - a[0]) * (p[1] - a[1]) - (p[0] - a[0]) * (b[1] - a[1])
            if (cross > 0) == (b[1] > a[1]):
                inside = not inside
    return inside


def check_polygon(rings: Sequence[Ring]) -> None:
    """Refuses the polygon unless it is simple. Raises a MapDocumentError that says why."""
    edges: list[tuple[int, int, IntPoint, IntPoint, int, int]] = []
    sizes: list[int] = []
    for ring_index, ring in enumerate(rings):
        n = len(ring)
        sizes.append(n)
        for i in range(n):
            a, b = ring[i], ring[(i + 1) % n]
            if a == b:
                raise MapDocumentError("a polygon has an edge of no length")
            edges.append((min(a[0], b[0]), max(a[0], b[0]), a, b, ring_index, i))
    # Neighbours within one ring meet at a vertex and must not run back over each other.
    for ring in rings:
        n = len(ring)
        for i in range(n):
            a, b, c = ring[i], ring[(i + 1) % n], ring[(i + 2) % n]
            if _orient(a, b, c) == 0 and (
                (b[0] - a[0]) * (c[0] - b[0]) + (b[1] - a[1]) * (c[1] - b[1]) < 0
            ):
                raise MapDocumentError("a polygon doubles back over itself")
    edges.sort(key=lambda e: e[0])
    spent = 0
    count = len(edges)
    for i in range(count):
        lo_i, hi_i, a, b, ring_i, index_i = edges[i]
        y_low, y_high = min(a[1], b[1]), max(a[1], b[1])
        j = i + 1
        while j < count and edges[j][0] <= hi_i:
            _lo_j, _hi_j, c, d, ring_j, index_j = edges[j]
            j += 1
            spent += 1
            if spent > SIMPLICITY_BUDGET:
                raise MapDocumentError("a polygon is too complex to check")
            if min(c[1], d[1]) > y_high or max(c[1], d[1]) < y_low:
                continue
            if ring_i == ring_j:
                n = sizes[ring_i]
                if (index_i - index_j) % n in (1, n - 1):
                    continue  # neighbours; handled above
            if _touch(a, b, c, d):
                raise MapDocumentError("a polygon touches or crosses itself")
    if len(rings) > 1:
        outer = rings[0]
        for hole in rings[1:]:
            if not _inside(outer, hole[0]):
                raise MapDocumentError("a hole must lie inside the outer ring")
        for i, one in enumerate(rings[1:], start=1):
            for j, other in enumerate(rings[1:], start=1):
                if i != j and _inside(other, one[0]):
                    raise MapDocumentError("a hole must not lie inside another hole")
