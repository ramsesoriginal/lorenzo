# 0407 - The graph renderer and its layout engines

Status: accepted, decided with the maintainer on 2026-11-05; [RFC 0049](../rfcs/0049-lorenzo-social-relationships-and-social-webs.md)
slices 7, 10 and 15. Follows [ADR 0339](0339-the-map-renderer.md); identity §18.

## Decision

`packages/graph-renderer` is a framework-free TypeScript package that draws a graph of entries from what it is given and
nothing else: no external library (no d3, no layout library), no canvas, no network. It ships source and a stylesheet.
Lorenzo Social is its first consumer; Bench's Relations view and the Beings relationships slot are the named second
consumers, which is why it is a package from the start, as `map-renderer` was.

**Three steps, kept apart.**

1. `layout(model, view, theme) -> Scene`: pure, plain JSON data, ordered primitives (paths, circles, text, markers,
   icons) with stable ids, numbers rounded to two decimals, a bounding box and the node or edge each came from. NaN and
   Infinity are rejected. The same input is the same bytes.
2. `paintSvg(scene, svg)`: `createElementNS`, `setAttribute` and `textContent` only; text a person wrote is never parsed.
   Called again it updates in place, so a focused node stays focused.
3. `hitTest(scene, point)` and the interaction module (pan and zoom by pointer and keys, select, centre on, move a node in
   `manual`), which emit events and never fetch or write.

**The model** is nodes (id, name, icon key, flags), edges (id, ends, direction, label, status `direct | derived |
uncertain`, an optional value and scale), groups to draw as hulls, hand positions and the view.

**Layout engines**, each `(graph, params, seed) -> positions`, a closed list in code that grows by ADR and is shared
with the API's `layout` check by one source and a golden test: `circle`, `radial` (polar rings by steps from a focus),
`stress` (stress majorization), `forceatlas2`, `manual`. All are written by us. A layered engine, for family trees and
lineage, is its own later slice; an octilinear and a lane layout wait for their themes.

**Determinism.** An integer seeded generator, fixed iteration counts, stable ordering by id, and only +, −, ×, ÷ and
square root; our own sine and cosine for the circle, because `Math.sin`, `Math.cos` and `Math.exp` are
implementation-approximated and an iterative layout amplifies the difference between browsers. A golden test runs the
same input in two engines and compares the bytes.

**Themes** are code modules naming brand tokens, never a color. One default theme now. Later themes (a family tree, an
underground map, a git log) are new modules and, where one needs it, a new engine, through the same contract; a theme
cannot add a field, a role or a request, and the data does not change.

**Grammar** (identity §18): three edge styles (solid direct, dashed derived, inherited or indirect, dotted uncertain), an
arrowhead for direction, selection as a fill that never changes a shape, nothing told by color alone. A relationship's
type is told by its label and an optional icon, never by a line style of its own; the Bench prototype's per-type line
styles are not adopted, and the documented exception Maps took for routes is not repeated.

**Limits** (*proposed default*): 500 nodes and 2,000 edges a Scene, and above that the app asks for a smaller selection.
Layout is a pure function and may run in a worker; the package never starts one.

**Reading it without sight.** The `<svg>` is a named group of buttons (axe reports focusable marks inside `role="img"`);
each node is focusable with a name; the arrow keys move along edges, Enter opens, Escape closes. A list in the document is
the primary non-visual form: one sentence a relationship, kept in step with the selection. Nothing is hover-only.

**Tests.** Scene JSON snapshots for each engine and edge status; the SVG strings `paintSvg` writes; `hitTest` and the
interaction's pure reducers; a golden corpus run in two JavaScript engines; and a Playwright golden of the default theme,
light and dark.

## Excluded

An external library, a physics engine in the paint step, drawing relationships on a Map, a layered engine and further
themes (their own slices), animation beyond what the brand allows, and any fetch or write from the package.
