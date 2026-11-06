# @lorenzo/graph-renderer

Hand-written SVG drawing of a graph of Lorenzo entries ([ADR 0407](../../docs/adr/0407-the-graph-renderer.md)).
No graph library, no canvas, no network, no runtime dependency: it draws what it is given and never
fetches, writes or stores anything. It ships TypeScript source, as the other packages do. Lorenzo
Social ([ADR 0408](../../docs/adr/0408-lorenzo-social-the-app.md)) is its first consumer; Bench's
Relations view and the Beings relationships slot are the named second consumers.

```ts
import '@lorenzo/graph-renderer/graph.css'; // the classes the drawing uses, in brand tokens only
import { createGraphView } from '@lorenzo/graph-renderer';

const graph = createGraphView(host, {
  model: { nodes, edges, groups }, // what the API returned, mapped onto the types
  title: 'The court of Hollowmere',
  iconBase: brandUrl, // where the brand's icons.svg is served from
  view: { layout: 'stress', seed: 7 },
  onSelect: (selection) => openPanel(selection),
  onOpen: (id) => goTo(id),
});
```

The host needs a definite size and the brand's `tokens.css`.

## Three steps

1. `layout(model, view, theme?) -> Scene`. Pure: the same input is the same bytes. The Scene is
   plain JSON in the screen pixels of the viewport (so the `<svg>` has `viewBox="0 0 width height"`
   and no transform): ordered primitives with stable ids and the node, edge or group each came from,
   numbers rounded to two decimals, a bounding box, and the `frame` that takes a pointer back to
   layout units. NaN and Infinity are refused.
2. `paintSvg(scene, svg, { title, iconBase })`. `createElementNS`, `setAttribute` and `textContent`
   only; text a person wrote is never parsed. Called again it updates in place, so a focused node
   stays focused. Each node is one focusable button named for the entry.
3. `hitTest(scene, point)` and the interaction module: pan and zoom by pointer and keys, select,
   centre on, move a node in `manual`, and arrow keys along edges. It emits events and never
   fetches or writes.

## Layouts

A closed list in [`src/layouts.json`](src/layouts.json), checked against the API's list by a test on
each side: `circle`, `radial` (rings by steps from a focus), `stress` (stress majorization),
`forceatlas2`, `manual` (hand placements kept, the rest on a circle) and `layered` (a circle until
its own slice). A hand placement pins a node in every layout. All are written here, deterministic by
an integer seeded generator, fixed iteration counts and only + - * / and square root; `sin` and `cos`
are our own because `Math.sin` is approximated differently by implementations.

## The grammar

Three edge styles (solid direct, dashed derived or inherited or indirect, dotted uncertain), an
arrowhead for a one-way tie, selection as a fill that never changes a shape, nothing told by colour
alone. A relationship's type is told by its label and an optional icon. A Scene holds at most 500
nodes and 2,000 edges (`LIMITS`).

## Themes

A theme is a code module naming sizes and class names; `graph.css` maps the classes onto brand
tokens, so there is no colour in the package. One default theme now.

## Checks

`mise run test` (Vitest): Scene snapshots for each engine, the SVG painting, hit testing, the pure
reducers, the stylesheet's tokens-only rule and the numbers. `mise run lint` is Biome and `tsc`.
