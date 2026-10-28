# 0337 - Geometry, roles and the one validator

Status: accepted with the maintainer on 2026-10-23; RFC 0048 slice 4.

## Decision

**The format.** A placement's `geometry` is `lorenzo.geometry/1`, a list of parts:

```json
{"format": "lorenzo.geometry/1", "parts": [
  {"shape": "point",    "at": [x, y]},
  {"shape": "circle",   "at": [x, y], "r": 40},
  {"shape": "polyline", "pts": [[x, y], [x, y]], "value": 100, "unit": "m"},
  {"shape": "bezier",   "start": [x, y], "segs": [[[c1x, c1y], [c2x, c2y], [ex, ey]]], "closed": false},
  {"shape": "polygon",  "rings": [[[x, y], [x, y], [x, y]], [[x, y], [x, y], [x, y]]]}]}
```

- A **point** marks a place; a **circle** has a positive radius; a **polyline** has at least two
  points; a **bezier** is a start and cubic segments (two controls and an end each), and `closed`
  makes a region of it; a **polygon** is an outer ring followed by holes, each ring of at least three
  points and not closed by repeating its first.
- A polygon is *simple*: its edges never cross or touch except at neighbouring vertices, a hole lies
  inside the outer ring and clear of every other ring. Concave is allowed. A star that crosses itself
  is refused. Simplicity is checked on write only.
- Any part may carry `value` (a finite number) and `unit` (at most 32 characters) together: a contour
  is one entry of many polylines, each with its height. Neither is read by this slice's renderer.
- Numbers are finite, carry at most six decimals, and none is larger than 1e7 in size. The JSON holds
  no entry id, no payload id and no colour: a copy never rewrites geometry, and how a shape looks is a
  theme's business (ADR 0339).
- A part is one of these shapes and nothing else; an unknown key is an error, so the format cannot
  grow by accident.

**The validator.** `packages/map-engine` (Python, in the shape of `packages/calendar-engine`, with
no database access) is the one way geometry and a system enter: from every API write, from the
repository planner, and from the update applier. It checks the forms above, derives the placement's
`bytes` (the length of its canonical JSON) and its bounding box (a superset: for a bezier, the hull
of its control points; for a circle, the square around it), and answers a generic 422 that echoes
nothing of the input. Simplicity uses exact integer arithmetic on coordinates quantised to six
decimals and an operation budget, so the worst legal polygon cannot hold a request; one fixture
measures it. A TypeScript mirror joins when something in the browser needs to validate (the editor,
slice 6), against the same golden corpus of accepted and refused documents in
`packages/map-engine/golden/`, which both languages must agree on.

**Limits.** One table, enforced for every library and recorded here with its owner: the placement
validator owns them, the write routes and the repository planner call it.

| Limit | Value |
| --- | --- |
| bytes of one placement's geometry | 64 KiB |
| vertices in one placement, controls included | 2,000 |
| parts in one placement | 256 |
| coordinate magnitude | 1e7 |
| placements on one Map | 5,000 |
| Maps in one library | 500 |

They begin strict and are loosened by ADR after measurement. Library-wide totals (Maps, placements,
bytes) are read by the owner and enforced for repositories through the quota path that exists
(ADR 0298); the 30,000-entry repository quota is reached by entries before any of these.

**Roles.** A placement may name a *role*: the kind of stuff it is, so a theme can draw it, a view
can group it and a legend can say it. The list is closed and lives in code, not in a database
check, and grows only by ADR:

`water`, `ground`, `relief`, `vegetation`, `diffuse`, `celestial`, `built-up`, `structure`,
`interior`, `barrier`, `passage`, `route`, `conduit`, `territory`, `boundary`, `hazard`,
`presence`, `object`, `isoline`, `marker`, `site`.

The role says the kind of stuff and the geometry says the shape: `water` as a line is a river, as
an area a lake. Tags, an entry's own, say what it is called. A role never validates a shape, never
gates visibility, never feeds a distance or reach. A write names a role this version knows or none;
a document that names one it does not know is read as having none. A role is added when a theme must
draw or group it differently, role, geometry and tag together cannot say it, and one sentence that
names how it is drawn rather than what it is can explain it. An editor may suggest tag names per role
in the client; nothing is stored or seeded.

**Style.** A placement may carry `style`: `{"stroke": "solid" | "dashed" | "dotted" | "double" |
"none", "weight": "hairline" | "thin" | "regular" | "thick" | "heavy"}`, each key optional. It is an
author's explicit choice for that placement and overrides the theme's default for it: how a road is
drawn without telling every road. `none` makes a placement *hit-only*: it draws no line of its own,
so a painted picture can show through, but it is still listed and focusable, and drawn with a
hairline outline while the view's "show places" switch is on (it starts on). It is never preselected.

## Validation and delivery

Tests: every accepted and refused shape in the golden corpus, from Python (this slice) and later
from TypeScript; limits at and over each bound; that a refusal echoes nothing; quantisation; the
bounding box as a superset; the worst legal polygon within its budget; roles known and unknown.

## Excluded

Self-crossing polygons, a drawn-polyline distance, per-part widths and colours, cells and grid
coordinates (slice 7), sphere coordinates (slice 8), and any role beyond the list.
