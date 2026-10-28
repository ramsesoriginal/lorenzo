"""The route search on its own (ADR 0367): the costs, the caps and the order of ties, against a
graph held in memory."""

import uuid

from lorenzo_api.routing import NO_ROUTE, TOO_MUCH, Edge, find_route


def ident(n: int) -> uuid.UUID:
    return uuid.UUID(int=n)


class Graph:
    """Edges by name; it counts how many reads the search made."""

    def __init__(self, *edges: Edge) -> None:
        self.edges = edges
        self.reads: list[list[uuid.UUID]] = []

    async def expand(self, places: list[uuid.UUID]) -> list[Edge]:
        self.reads.append(list(places))
        return [e for e in self.edges if e.a in places or e.b in places]


def edge(n: int, a: int, b: int, length: float | None, one_way: bool = False) -> Edge:
    return Edge(ident(1000 + n), ident(a), ident(b), one_way, length)


async def test_the_shortest_measured_route_is_known():
    graph = Graph(edge(1, 1, 2, 10), edge(2, 2, 3, 5), edge(3, 1, 3, 20), edge(4, 3, 4, 7))

    got = await find_route(ident(1), ident(4), graph.expand)

    assert got.state == "known" and got.total == 22 and got.unmeasured == 0
    assert [(leg.start, leg.end) for leg in got.legs] == [
        (ident(1), ident(2)),
        (ident(2), ident(3)),
        (ident(3), ident(4)),
    ]


async def test_a_measured_route_beats_a_shorter_one_with_a_leg_that_has_no_length():
    graph = Graph(edge(1, 1, 4, None), edge(2, 1, 2, 100), edge(3, 2, 4, 100))

    got = await find_route(ident(1), ident(4), graph.expand)

    assert got.state == "known" and got.total == 200 and len(got.legs) == 2


async def test_without_a_measured_route_the_one_with_fewest_unmeasured_legs_is_partial():
    graph = Graph(
        edge(1, 1, 2, None),
        edge(2, 2, 4, None),
        edge(3, 1, 3, 30),
        edge(4, 3, 4, None),
    )

    got = await find_route(ident(1), ident(4), graph.expand)

    assert got.state == "partial" and got.unmeasured == 1 and got.total == 30
    assert [leg.end for leg in got.legs] == [ident(3), ident(4)]


async def test_a_one_way_connection_is_followed_one_way_only():
    graph = Graph(edge(1, 1, 2, 4, one_way=True))

    forward = await find_route(ident(1), ident(2), graph.expand)
    back = await find_route(ident(2), ident(1), graph.expand)

    assert forward.state == "known" and forward.total == 4
    assert back.state == "unknown" and back.reason == NO_ROUTE


async def test_no_route_is_unknown_and_never_zero():
    got = await find_route(ident(1), ident(9), Graph(edge(1, 1, 2, 1)).expand)

    assert got.state == "unknown" and got.reason == NO_ROUTE and got.total == 0 and got.legs == []


async def test_the_same_place_is_a_known_nothing():
    graph = Graph()

    got = await find_route(ident(1), ident(1), graph.expand)

    assert got.state == "known" and got.total == 0 and got.legs == [] and graph.reads == []


async def test_a_tie_goes_to_the_lower_connection_id():
    graph = Graph(edge(7, 1, 2, 5), edge(3, 1, 2, 5), edge(5, 1, 2, 5))

    got = await find_route(ident(1), ident(2), graph.expand)

    assert [leg.connection for leg in got.legs] == [ident(1003)]


async def test_fewer_legs_win_a_tie_of_length():
    graph = Graph(edge(1, 1, 2, 5), edge(2, 2, 3, 5), edge(3, 1, 3, 10))

    got = await find_route(ident(1), ident(3), graph.expand)

    assert [leg.connection for leg in got.legs] == [ident(1003)]


async def test_the_caps_say_so_and_are_never_an_unknown():
    chain = [edge(n, n, n + 1, 1) for n in range(1, 10)]

    legs = await find_route(ident(1), ident(10), Graph(*chain).expand, max_legs=3)
    places = await find_route(ident(1), ident(10), Graph(*chain).expand, max_places=4)
    connections = await find_route(ident(1), ident(10), Graph(*chain).expand, max_connections=2)
    enough = await find_route(ident(1), ident(10), Graph(*chain).expand)

    for capped in (legs, places, connections):
        assert capped.state == "limit_reached" and capped.reason == TOO_MUCH
    assert enough.state == "known" and enough.total == 9


async def test_places_are_read_together_so_the_statements_stay_few():
    # A star: the hub's spokes are all in the frontier at once.
    graph = Graph(*[edge(n, 1, 100 + n, 1) for n in range(1, 30)], edge(99, 129, 200, 1))

    got = await find_route(ident(1), ident(200), graph.expand)

    assert got.state == "known" and got.total == 2
    assert len(graph.reads) <= 4
