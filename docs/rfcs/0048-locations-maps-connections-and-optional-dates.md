# 0048 - Locations, Maps, connections and optional dates

Status: accepted for the fourteen delivery slices agreed with the maintainer on 2026-10-23, and built.
Decisions: one ADR per slice, written before its implementation (the Locations and Maps ADRs, 0330 to 0377 with the Writing ADRs among them, are in the [ADR index](../adr/README.md)).
This narrows [RFC 0026](0026-world-model-axes-and-address.md); it does not accept either of RFC 0026's
axis candidates as a whole. It uses [RFC 0028](0028-time-causality-and-calendars.md) only through the
date association that is already built, and accepts nothing of RFC 0028's Part 2.

## Purpose

Give libraries places and maps. A **Location** is an entry of its own kind, from a universe overview
down to one floor of a building, in any setting (fantasy, sci-fi, modern, realistic, abstract). A
**Map** is an entry of its own kind that draws entries: generated from data, laid over an authored
picture, or both. Roads, rivers, portals, stairs and shortcuts exist as data, so that a distance can
be computed when the data to compute it exists and is otherwise unknown. Locations and Maps can
optionally be tied to a calendar period; neither needs one.

The data structures already include RFC 0026's frames and axes. The client side is narrow: one new
app, no user interface for placing things on axes, no mobile support yet.

## Decided inputs

These were decided with the maintainer before the design below was worked out. They are inputs.

1. **Narrowing.** Data and API include RFC 0026's sub-slices 2 to 6 (frames and placement, the
   player read, the GM read, position in space, connections). Outside this RFC: timeline variants
   (`entity_variant`) and the general time, causality and history work (RFC 0028 Part 2). There is
   no UI for placing things on axes.
2. **Hierarchy.** Locations form a separate single-parent "part of" tree. `containment` stays the
   physical "stuff is in stuff" relation, and nothing new feeds
   [ADR 0046](../adr/0046-gm-reachability-widens-to-surroundings.md) GM reachability.
3. **Kinds.** A Location may be any other kind as well (being, item, calendar period, ...). Every
   combination is allowed and each is proved in the publish kind matrix.
4. **Geometry.** Validated JSON in Postgres, no PostGIS. No external service and no third-party
   package for maps: no tile provider, no map library, no real-world basemap. A limited importer
   for real-world data may come much later.
5. **Renderer.** Hand-written SVG in a framework-free package that reproduces the Bench design
   ([docs/design/bench/screens/15-map.jpg](../design/bench/screens/15-map.jpg) and its prototype) as
   closely as possible, pixel-perfect as the goal, and that is built from stored data alone. A new
   static Astro app hosts viewing and editing. Bench integration is deferred.
6. **Pictures.** Map pictures stay in `payload_picture` (10 MB per picture, 20 MB of pictures and
   30,000 entries for a repository). SVG upload is allowed now; embedding SVG is deferred.
7. **Distance first.** Travel time is deferred. Time is optional: a Map or Location with no period
   association behaves exactly as it does today.
8. **Six coordinate systems**, chosen by the author with no default and no default unit: free plane,
   square grid, rectangular grid, hex grid (flat-top and pointy-top, a per-map setting), sphere,
   and outline-only (a schematic that measures nothing). Grids take sub-grids (a cell divided
   n by m; hex apertures such as 3, 4 or 7), and any system can draw a visual-only grid overlay.
9. **Data and look are separate.** The data says what things are and where. A *theme* turns that into
   a picture. The Bench mock-up is the default theme; neutral, hand-painted, distorted-schematic and
   shaded-relief themes must be buildable later from the same data. An explicit per-shape style
   (solid, dashed, dotted, double; thin to thick) is an author's choice and sits in the data.
10. **Terrain is data.** Rivers, hills, lakes, forests, roads and contours are entries with
    placements, not decoration. A contour set is one entry whose parts each carry a value and a
    unit label. A shape is a point, circle, polyline, cubic Bézier path, simple polygon (never
    self-crossing, concave allowed, holes allowed) or a multi-part of those. A placement belongs to
    one (map, entry) pair, so one entry has different geometry on different maps. Positions never
    inherit.
11. **Roles and tags.** A closed list of *roles* in code names the kind of stuff a placement is
    (optional, at most one per placement, additive only by ADR, unknown roles draw neutrally).
    Tags stay ordinary library data. The editor may suggest tag names per role as client-side
    hints; nothing is stored or seeded. The user-facing words are **Location** and **Map**.

## Hard invariants

Every slice must hold these, and each is pinned by a test.

- **G1.** Nothing is seeded. Absence means "not modeled", never unknown, default or timeless. An
  unused feature costs zero rows, zero form fields and zero response keys.
- **G2.** No NOT NULL time column on any placement or position table, no implicit "now", no global
  clock. "Where is my stuff" takes no time argument.
- **G3.** New positions, axes and connections never feed ADR 0046 GM reachability.
- **G4.** Nothing private leaks through a pin, line, region, count, pagination, preview card, error
  message, computed distance or route. A hidden thing is absent, not a placeholder. Visibility is
  filtered in SQL before traversal and pagination ([ADR 0109](../adr/0109-player-knowers-knower-listing-and-information-list.md);
  [ADR 0321](../adr/0321-constant-clock-ratios-and-reader-conversion.md) is the precedent for graph
  reads).
- **G5.** No genre, unit or vocabulary default in the schema, API strings, roles or UI.
- **G6.** Everything travels through repository copy, update and release: a registry line in
  `copyable_tables.py`, the `repository_read` policy, a planner step, digest and diff handling, a
  release-document format bump with its reader, a kind-matrix row.
- **G7.** Every tenant table has `tenant_id`, `ENABLE` and `FORCE ROW LEVEL SECURITY` and composite
  same-tenant foreign keys ([ADR 0117](../adr/0117-same-tenant-references-by-composite-foreign-keys.md)).

## What this narrows

### Of RFC 0026

Taken: sub-slices 2 to 6. Left out: 7 (timeline variants) and 8 (the time and causality RFC). B0
(composite tenant foreign keys) is done, as ADR 0117. This RFC settles:

- **D1.** Position in space is not a fifth axis and not RFC 0026's `spatial_position`. Locations have
  their own tree (`location_part`), and an entry is *at* a Location through `entity_location`.
- **D2.** "One position per axis" is the primary key `(entity_id, axis)`. No surrogate key, no time
  column.
- **The axis candidates.** An axis is a format-checked token with a reserved list in code
  (`timeline`, `universe`, `plane`, `sphere`), widened only by ADR. This is closer to RFC 0026's
  Candidate 1 than to its Candidate 2 (no registry table), and it keeps the token open in shape.
  The four words are platform structure, and the first ADR on axes says so in one sentence.
- **The resolver.** One Python-built batched recursive-CTE builder taking the visibility fragment as
  a mandatory argument replaces the `world_address(uuid[])` SQL function. No `SECURITY DEFINER`.
- **Connections.** A connection has two ends as columns, not one endpoint row per end. RFC 0026's
  reason for a row per end was per-end time, which is out of scope. See "Connections and distance".

Unchanged from RFC 0026's baseline: frames are ordinary entries, nothing is seeded, positions never
inherit through prototypes, the address is opt-in on reads, the player read is viewer-relative and
vocabulary-free, connection kinds are prototypes, mirrors are connections, no time column on any
placement table. D3 (absence in a timeline) and D4 (two positions on one axis) stay open and are not
needed here.

### Of RFC 0028

Nothing of Part 2. Optional time is a *lens* over the existing `entry_calendar_period` association
(["tied to"](../adr/0309-calendar-periods-events-and-date-associations.md), never "existed at"). `state_as_of`
is reserved and not used.

## Design

The sketches below fix the shape. Each slice's ADR fixes names, constraints and limits.

### Locations, placement and frames

```sql
location(entity_id PK, tenant_id NOT NULL)                           -- pure marker
location_part(child_entity_id PK, parent_entity_id NOT NULL, tenant_id NOT NULL,
  level_ordinal numeric NULL,                                         -- sibling stacking only
  CHECK (child_entity_id <> parent_entity_id), both FKs -> location)
entity_location(entity_id PK, location_entity_id NOT NULL, tenant_id NOT NULL,
  CHECK (entity_id <> location_entity_id), FK -> entity, FK -> location)
frame(entity_id, axis text CHECK (axis ~ '^[a-z][a-z0-9_]{0,31}$'), tenant_id NOT NULL,
  PRIMARY KEY (entity_id, axis))                                      -- a designation, not a kind
entity_frame(entity_id, axis, frame_entity_id, tenant_id NOT NULL,
  PRIMARY KEY (entity_id, axis), CHECK (entity_id <> frame_entity_id),
  FK (tenant_id, frame_entity_id, axis) -> frame)
```

- A root is a Location with no `location_part` row. Part-of is single-parent, skip-level legal, and
  untyped; a floor is an ordinary child Location and stacking is the optional ordinal. A universe, a
  village and one floor are all root Locations. Stairs, lifts, portals and mirrors are connections,
  never part-of edges.
- Part-of is acyclic on write: a recursive ancestor check inside the write transaction under an
  advisory lock, with a depth cap and no trigger. Readers keep their depth cap and path guard, so
  a cycle that arrives through a repository ends a chain without naming a row.
- **Containment wins.** `with_you`, `stashed` and `carried in` come from containment alone. A place is
  read only at the root of an entry's containment chain, and a place row on a contained entry is
  ignored by every reader. Containment never implies "inside the interior": a Location that is also
  a bag keeps its contents (carried in) and its interior (places inside) as two independent facts,
  reported under two separate read keys.
- Placement is one row per entry, any kind, no time column, not inherited down part-of.
- Frames are ordinary entries carrying a designation. An entry can be a frame on several axes. A
  multiverse is frame-in-frame nesting, never an axis. A timeline is membership only. Frame
  resolution is per axis, nearest explicit row wins, along the entry's own row, its containment
  chain, its place and the place's part-of ancestors. Never through prototypes.
- Reads: a player's `GET .../entities/{id}/whereabouts?relative_to=` (`with_you | stashed |
  elsewhere | unknown`, plus the knowledge-gated title of one differing Location, and no axis word,
  path, depth, ordinal or coordinate), the GM's opt-in `GET .../entities/{id}/address` with segments
  tagged `contained_in | at | part_of | frame`, and a GM-only lint that stores nothing.
- Writes: authors and GMs only. Targets are resolved under the writer's own visibility and a hidden
  target answers the same 404 as a missing one.

### Maps

```sql
map(entity_id PK, tenant_id NOT NULL,
  system jsonb NOT NULL,                  -- lorenzo.map-system/1
  subject_entity_id NULL,                 -- the Location this map depicts: an authored pointer
  theme_hint text NULL,                   -- a theme name from code
  view jsonb NULL)                        -- visual-only overlays, sphere projection
map_layer(map_entity_id, position smallint, information_id, calibration jsonb NULL, opacity real NULL,
  PRIMARY KEY (tenant_id, map_entity_id, position))   -- zero rows = a pure data map
map_placement(map_entity_id, entry_entity_id, geometry jsonb NOT NULL,   -- lorenzo.geometry/1
  role text NULL, style jsonb NULL, z smallint, bytes integer, minx, miny, maxx, maxy,
  PRIMARY KEY (tenant_id, map_entity_id, entry_entity_id))
```

- A map shows exactly the entries that have a placement. There is no "show all children" mode and
  no read-time expansion; "place the children" is an editor action that writes explicit rows.
  Pins, regions, hotspots and links are all placements of entries; there is no annotation table.
- **Systems** (`lorenzo.map-system/1`): `plane`, `square`, `rect`, `hex` (with `orientation`),
  `sphere`, `outline`, each with its own optional measurement block (`{size, unit}`, cell size,
  radius) and nothing invented when absent. The kind lives in the JSON, not in a database CHECK;
  an unknown kind reads as outline with distance unknown. Grid sub-grids (`sub`) and visual overlays
  (in `map.view`) never feed distance. Positions are continuous drawing-plane units; storage is
  y-down and only the renderer flips it. Spheres use longitude and latitude, no Bézier parts, no
  wrap, and a region over the antimeridian is two parts; the projection is a drawing choice.
  There is one documented hex convention and tie rule.
- **Geometry** (`lorenzo.geometry/1`): parts of `point`, `circle`, `polyline`, `bezier`, `polygon`
  (rings: outer then holes), each part with an optional `value` and `unit`. No entry id, payload id
  or colour inside the JSON, so a copy never rewrites JSON. One validator in `packages/map-engine`
  (Python authoritative, TypeScript mirror, one golden corpus) is the only way rows enter, from the
  API, from batches and from the repository planner. Simplicity is checked on write only.
- **Roles.** The draft list of 21: `water`, `ground`, `relief`, `vegetation`, `diffuse`, `celestial`,
  `built-up`, `structure`, `interior`, `barrier`, `passage`, `route`, `conduit`, `territory`,
  `boundary`, `hazard`, `presence`, `object`, `isoline`, `marker`, `site`. A role says the kind of
  stuff, the geometry says the shape (water as a line is a river, as an area a lake) and tags say the
  name. A role drives default drawing, toggle groups, filtering and the legend, and never
  validation, visibility, distance or reach. A new role must be drawn or grouped differently by a
  theme, be inexpressible by role, geometry and tag together, and be explainable in one sentence
  that names how it is drawn rather than what it is. The ADR for the maps core fixes the list.
- **Themes** are code modules in the renderer package. A map carries at most a theme *name*.
  Precedence: the viewer's local choice, then the map's name, then the built-in default. The scale
  bar, compass and legend are theme furniture, not data.
- **Pictures.** A layer points at the Information row that owns the picture and inherits that row's
  audience. Calibration anchors are fractions of the image; annotations are stored only in map
  coordinates, so replacing a picture never moves a placement. A changed picture fingerprint raises
  "needs review". `image/svg+xml` joins the allow-list, served only through the bearer-gated payload
  route with a server-fixed content type, `X-Content-Type-Options: nosniff` and a
  `default-src 'none'; sandbox` policy, drawn only as an image (as a `data:` URL, never as a blob
  URL the page can reach), with one reject-not-rewrite lint used by upload and by the repository
  planner. Hotspots are always our own placements over the image, never SVG element ids.
- **Reads.** `GET .../maps/{id}` returns the header and visible layers; `GET .../maps/{id}/placements`
  is keyset-paged after the visibility join, with a `bbox`, `role` and `min_diag` filter, no total and
  no revision counter. Counts are opt-in and cover direct visible children. Clients use
  `packages/read-cache`, keyed per viewer and library.
- **Hover** reuses the preview endpoint ([ADR 0264](../adr/0264-link-previews.md)) with new `location`
  and `map` templates; the card is extracted to a package first.
- **Caps** apply to every library (placement bytes, parts, vertices, placements per map, maps per
  library, write batch size). Library-wide totals are measured and readable by the owner and
  enforced only for repositories, through the quota path that exists.

### Connections and distance

```sql
connection(entity_id PK, tenant_id NOT NULL,
  end_a NOT NULL, end_b NOT NULL, one_way boolean NULL CHECK (one_way IS NOT FALSE),
  CHECK (end_a <> end_b), FK end_a -> entity, FK end_b -> entity)
```

- A connection is an entry; its kinds (road, stairs, lift, portal, mirror, shortcut, ferry) are
  prototypes, and nothing is seeded. A connection is shown only to a reader who can see both ends.
  Ends are entries, and the router is kind-blind. A hub (a stair shaft joining twelve floors) is a
  Location plus spokes written in one bulk request; n-ended connections are a later decision.
- The graph comes only from endpoint data. A drawn road is the connection entry's own placement and
  carries shape only. The router never reads a polyline or infers an endpoint, and redrawing a line
  never changes routing. Only explicit connections route: rivers, forests and hills do not, and
  part-of and containment are never travel edges.
- Length, speed and cost are ordinary stats with the author's unit. The caller names the measure:
  `GET .../distance?from=&to=&measure=<stat_definition_id>[&avoid=<tag>][&mode=route|straight][&map=]`.
  A missing or non-numeric measure is a 422. Units compare by exact normalised text; a mismatch
  makes the answer partial and is never converted.
- **Result states** are exactly `known | partial | unknown | limit_reached`, with `value` only for
  `known`. An unknown distance is never zero (an authored 0 is a legitimate `known` value). A
  route over a leg with no length is `partial`, carrying `at_least` and the count of unmeasured legs.
  "No path over the visible graph" is `unknown` with one wording, "no known route".
- **Straight-line distance** is a separate labelled answer and needs both placements on one map:
  euclidean times scale on a plane, a per-map metric (`chebyshev`, `manhattan`, `euclidean`,
  `alternating`) times cell size on a square or rectangular grid, hex distance on a hex grid, great
  circle on a sphere, and nothing on an outline map. Cross-map, cross-level and cross-scale
  distance is unknown. The geometry is a pure function in `packages/map-engine`, with golden vectors.
- **Routing** runs in the application: a bounded Dijkstra over a subgraph loaded by batched
  statements with the visibility predicate applied in SQL, so a hidden connection, end, length,
  placement or map is absent before traversal and cannot change the state, route, counters or error
  text. A reader and a GM run one code path and differ only in the visible set. Ties break on
  (cost, hops, connection ids). Caps are fixed in code and count only visible rows. No recursive
  SQL, no materialised distances, no server cache, no external routing service.
- A generic per-principal read limiter does not exist today; the distance slice adds one.

### Optional time

- The only mechanism is the existing `entry_calendar_period`. No new table and no column. A
  placement's time is its map's time, and a different layout in another era is another Map entry.
- A list of Maps (and, in a later slice, Locations) takes `tied_at` parameters by calendar
  coordinates, never a period id. An association matches when its period is the selected one or a
  structural ancestor of it in the same calendar (a year matches a day). Several associations are
  OR. Nothing is inferred: no recency ranking, no "latest before X", no nearest map.
- Every row is classified `tied`, `untied` or `other` and shown, with tied-elsewhere rows last and
  faded. An opt-in parameter excludes the other class before `LIMIT`. No parameter means today's
  response, with no extra key or join. There is no default date and no "Today" control; the picker
  opens empty and is absent when the library has no calendar.
- An association to a period or calendar the reader cannot see counts as absent. The wording is
  "tied to", "not tied to a date" and "tied to other dates", and never "existed at".
- Distance, route, whereabouts, address and inventory take no time argument.

## Rulings of 2026-10-23

Decided with the maintainer on the contested points.

1. **Release format.** The existing convention stands: one format bump per landing slice, every key
   always written (empty when unused), and new code reads older documents through a shim; an older
   deployment refuses a newer document, as it always has. G1 means rows, form fields and response
   keys.
2. **Axes.** The format-checked token with a reserved list in code, as above. Unknown tokens are
   refused by every writer and importer, with a per-library cap on distinct tokens fixed in code.
   Timeline, universe, plane and sphere are platform structure.
3. **A place and a container.** Containment wins. A containment write that puts an entry into a
   container clears the entry's place in the same transaction. A write that takes it out sets its
   place to the Location its former container resolves to (the container's own place, or that of the
   container it sits in, up to the root of the chain); if none resolves, no row is written. A place
   write on a contained entry is accepted and ignored with an identical response. The helper that
   does this lives in one place and the containment response shows nothing of it. Repository writers
   cannot use the helper, so the planner drops a conflicting row and readers keep ignoring a stray
   place row. Putting an entry back into a container clears the place again; the earlier place is
   not restored.
4. **A hidden level in the part-of chain.** The hierarchy skips it. A reader sees a visible Location
   under its nearest visible ancestor. The chain is derived at read time and never stored, no
   response marks that a level was skipped (a marker would reveal it exists), and the interface says
   "in" or "within" for every hierarchy line, never "part of directly". The "places inside" read
   descends through hidden levels and emits the visible Locations it reaches, and its counts and
   pages are computed over those. The depth cap counts hops whatever their visibility. The test is
   that a response is byte-identical whether a hidden middle level exists or the child sits
   directly under the grandparent. A GM lint lists visible Locations under hidden parents.
5. **SVG** is drawn as a `data:` URL image and never as a DOM-reachable blob URL. A later test
   that shows a typed blob is safe may change this by ADR.
6. **Dotted routes.** The default theme draws routes dotted for parity with the Bench design. This is
   a documented exception to the brand rule that dotted means unknown; a shape's own style
   override draws it solid.
7. **Connections** have two ends and take their length from a named stat. This deviates from RFC
   0026's row per end.
8. **Links and distance** wait for the connection slices. The first maps slice draws a portal only
   as drawn and has no "leads to" pin.
9. **The app** is `apps/maps`, "Lorenzo Maps", hosted as the Pages project `lorenzo-maps`. Writes are
   authors and GMs only. "Put this entry at this Location" is API and CLI only until the authoring
   slice.
10. **Time.** The lens lands for Maps first and for Locations as its own later slice, with its own
    parity tests. No Location dating editor ships before that lens.
11. **Hex.** One documented hex convention, and a 409 when the hex orientation or the sphere setting
    is changed once placements exist (other changes warn and mark the map "needs review").

### Adopted recommendations

Decided with the maintainer, without changes: one visibility fragment built once in the first slice
and imported by every later reader, with a parity test per reader; one dropped-row report shared by
copy, update and release; one limits table in an ADR with an owner per cap; `map.subject_entity_id`
as a nullable column with `ON DELETE SET NULL (subject_entity_id)`, never read by a resolver; a map
and its drawn Location may be one entry, with separate entries recommended in the UI; the preview
card extracted to `packages/entry-preview` before map hover; a stored SHA-256 on the picture before
the pictures slice; a reusable read limiter derived from the existing token bucket for the distance
endpoint (a per-instance backstop, with the statement timeout as the real bound); whole-copy
atomicity as the planner already has it; map drawings never read as where an entry is (the wording
is "drawn here"); a generated kind matrix for Location, Map and connection, with a refused-pairs
table as a later refactor; `kinds` in responses widened for the new kinds through the breaking-change
process; no `level_label` column; 21 roles and a two-setting admission rule; hit-only hotspots
(`stroke: none`) listed and focusable and never preselected; strict first limits (2,000 vertices,
64 KiB per placement, coordinates within 1e7, control-hull bounding boxes) loosened by ADR after
measurement; one stat per distance request with cross-scale and mixed-unit routes always partial
until conversion ships; a missing measure is a 422; `from` equal to `to` is known, zero, after the
visibility 404; `tied_at`, with coordinates as structured parameters, ordered by class, then name,
then id, and one byte-identical empty result.

## Delivery

Fourteen slices, each one ADR and one tested API-and-app vertical pull request, stacked after the
documentation pull request. A slice never lands a table without its repository line, because the
repository tests fail otherwise. No schema or UI for a later slice is built early to reserve space.

1. **Locations.** `location`, `location_part`, the shared visibility fragment, the kind-matrix
   generation and guard lifts for Location, list, search, root and parts reads, and the new app
   scaffold (sign-in, library choice, a tree and list with create, rename and reparent).
2. **Placement and the player read.** `entity_location`, containment wins, the containment helper,
   the resolver builder, whereabouts, and the ADR 0046 pin test.
3. **GM address and lint.** No schema.
4. **Maps core.** `packages/map-engine`, `map` and `map_placement`, the plane and outline systems,
   the geometry format, header and placement reads, `packages/map-renderer` with the default theme,
   and a read-only map view.
5. **Entry preview extraction**, with `location` and `map` templates.
6. **Map authoring.** Pan, zoom, select and draw, placement writes, roles, legend, group toggles,
   themes.
7. **Grids and hex**, with sub-grids and overlays.
8. **Sphere.**
9. **Pictures and layers.** The stored SHA-256, `map_layer`, calibration, SVG, and an ADR with the
   measurable triggers for object storage (nothing built).
10. **Connections.** `connection`, the bulk hub write, the all-ends-visible read, derived links.
11. **Distance.** Route distance first, then straight line, with the read limiter.
12. **Frames and axes.** `frame` and `entity_frame`, frame resolution in the reads. API only.
13. **Optional time on Maps.** The calendar-engine ancestor function and the lens.
14. **Optional time on Locations.**

Slices 1 to 3 give a working Locations app and RFC 0026's reads before anything is drawn. Frames are
last of the data work because no UI places things on axes and no other slice depends on them.

## Boundaries

- A map is a drawing. It never feeds whereabouts, the address, reachability or any position
  derivation, and an entry's presence marker on a map is not where it is. `entity_location` may
  disagree with a placement and the interface never says "you are here" from either.
- A map's `subject_entity_id` is an authored pointer that no resolver reads.
- Time never reaches a placement, a connection or a frame row. A schema-scan test pins it.
- Deleting a Location makes its children roots, removes its placements and place rows, and sets
  `map.subject_entity_id` to null; deleting a connection's end deletes the connection (the entry
  stays); deleting an entry removes its placements, frame rows and place row; a referenced calendar
  period still refuses deletion. Each row is a test in its slice's ADR.
- A visible Location is never listed under a hidden parent, and a hidden parent is never named.

## Not in scope

Timeline variants and `entity_variant`; RFC 0028 Part 2 and `state_as_of`; travel time, speed, mode
and terrain weighting, and k-shortest paths; unit conversion; n-ended connections; drawn-polyline
distance on the server; cross-map calibration and cross-map distance; a client UI for placing things
on axes; mobile; Bench integration; real-world basemaps and tile providers; inline SVG; object
storage (an ADR with triggers only); a per-library theme table; per-viewer server storage;
time-aware routing; descendant ("inside") matching for dates; a revision counter anywhere; seeded
rows of any kind.

## Consequences

Easier: a library gets a place tree and maps without learning any axis vocabulary; a plain village
needs one Location and no frame, system or scale it does not choose; a distance is honest about what
it does not know; a different look is a different theme over the same data.

Harder, and accepted:

- Skipping a hidden level shows a visible Location under a higher ancestor than its author set, and
  changing or deleting the hidden middle changes what a reader sees.
- Hub Locations, per-era Maps and city-sized Location sets spend the 30,000-entry repository quota
  before any other limit. A multi-year era is one explicit year association each.
- A map's pictures count against the 20 MB repository total, and a copy re-stores every byte.
- Cross-scale and mixed-unit routes are partial until unit conversion is decided.
- A tie to a period a reader cannot see reads as untied for that reader.
- Each slice carries a release-format bump, a registry line, a planner step and a kind-matrix row.
- Closed lists (axes, roles, systems, grid metrics) are shared by Python and TypeScript and drift
  unless one source and a golden test hold them together.
