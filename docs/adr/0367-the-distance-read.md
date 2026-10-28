# 0367 - The distance read

Status: accepted with the maintainer on 2026-10-28; RFC 0048 slice 11. Reads the connections of
[ADR 0363](0363-connections-the-kind-and-its-two-ends.md) and the straight line of
[ADR 0366](0366-straight-line-distance-on-a-map.md). It stores nothing, caches nothing and calls no
service.

## Decision

`GET /tenants/{t}/distance?from=&to=&mode=route|straight[&measure=][&avoid=][&map=]` answers how far one
entry is from another, to any participant of the library. `from` and `to` are entries the reader sees (a
hidden or missing one is the generic 404); `mode` is `route` unless it says `straight`.

**One answer shape.** `{mode, state, value, at_least, unit, unmeasured_legs, route, map, reason}` with
`state` exactly one of `known | partial | unknown | limit_reached`:

- `value` only for `known`, and an unknown distance is never zero (an authored 0 is a `known` value);
- `partial` carries `at_least` (what is measured) and `unmeasured_legs` (how many legs have no length);
- `unknown` and `limit_reached` carry one `reason`, in fixed wording: *no known route*, *the Map has no
  scale* and the others of ADR 0366, *they are not drawn on one Map*, *too much to search*.

**The route read.** The graph is the explicit connections the reader sees with both ends, and nothing
else: a river, a forest or a hill does not route, and part-of and containment are never edges. A one-way
connection goes from `end_a` to `end_b`, a way both ways either way. The router is kind-blind.

- `measure` names a stat definition of the library and is required; it must be numeric (`int` or
  `float`), else a 422. A connection's length is the entry's effective value of it (its own, or inherited
  through its prototypes as ADR 0037 says); a stat that is a formula, a missing value, a negative one and
  a non-finite one are *no length*. The unit is the stat definition's own, so every leg of a route has the
  same unit and no conversion exists or is ever needed.
- `avoid` names a tag (a boolean stat definition); a connection that carries it is not an edge.
- A **bounded Dijkstra in the application** over a subgraph read in batches: the connections touching the
  frontier, with the visibility predicate of ADR 0363 in SQL, one statement per hop, so a hidden
  connection, end, length or placement is absent before the search begins and cannot change the state,
  the route, a counter or an error. A reader and a GM run one code path and differ only in what they
  see.
- **A route that is measured beats one that is not**: the cost is, in order, the legs with no length,
  the sum of the lengths, the number of legs, and the connections' ids. So a `known` answer is the
  shortest fully measured route when there is one; otherwise the route with fewest unmeasured legs and
  then the shortest is `partial`; with no route at all it is `unknown`. The route is the answer's
  `route`, each leg a connection stub, its two ends and its length (null for none).
- **Caps in code, counted over visible rows only**: 2,000 places and 10,000 connections read, and 64
  legs in one route; reaching one is `limit_reached`.
- `from` equal to `to` is `known`, zero, with no legs, after the visibility check.
- No recursive SQL, no materialised distances, no server cache, no external routing service.

**The straight read** needs both entries placed on one Map the reader sees. With `map=` it uses that Map
(a Map that is hidden, missing or does not hold both is *they are not drawn on one Map*); without it, the
one Map that holds both and the reader sees, and when there are several the answer is a 422 that asks for
`map=`. The answer is ADR 0366's, `known` with its unit or `unknown` with its reason, and `route` is
empty.

**Limiting.** A reader's requests are limited per user per instance with the token bucket of
`rate_limit.py` (`distance_rate_limit_per_minute`, 60, 0 turns it off), answering 429 with `Retry-After`
(ADR 0092's backstop: the statement timeout is the bound that counts). The limiter is written as a
helper any read may reuse.

## Validation and delivery

A route over three legs known, with a one-way leg both ways, a longer measured route chosen over a
shorter unmeasured one, a partial answer with its legs counted, no route, `avoid`, a measure that is not
numeric or missing, an inherited length and a formula, equal ends, the caps and `limit_reached`
(patched down), a hidden connection, end or length leaving no difference from its absence (two libraries
byte for byte), the same answer from a GM and from a reader who sees the same rows, ties broken by id, the
straight read on each kind, the Map chosen and the ambiguous 422, the limiter, and that no reach code reads
a connection's ends.

## Excluded

Travel time, speed, terrain and mode weighting, the k shortest routes, unit conversion, distance across
Maps, levels or libraries, a route through an entry nobody connected, and a route drawn on a Map by the
server.
