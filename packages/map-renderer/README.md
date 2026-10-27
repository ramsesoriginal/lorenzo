# @lorenzo/map-renderer

Hand-written SVG drawing of a Lorenzo Map ([ADR 0339](../../docs/adr/0339-the-map-renderer.md)).
No map library, no tiles, no canvas, no network, no runtime dependency: it draws what it is given
and never fetches, writes or stores anything. It ships TypeScript source, as the other packages
do, and Lorenzo Maps ([ADR 0340](../../docs/adr/0340-the-map-view-in-lorenzo-maps.md)) is its first
consumer.

```ts
import '@lorenzo/map-renderer/map.css'; // the classes the drawing uses, in brand tokens only
import { createMapView } from '@lorenzo/map-renderer';

const map = createMapView(host, {
  model: { system, placements }, // what the API returned, mapped onto the types below
  title: 'Map of Hollowmere',
  iconBase: brandUrl, // where the brand's icons.svg is served from
  onSelect: (entryId) => openPanel(entryId),
});

map.setGroups({ roads: false });
map.zoomIn();
map.centreOn(entryId);
```

The host needs a definite size (the drawing fills it) and the brand's `tokens.css`.

## Three steps

1. `layout(model, view, theme?) -> Scene`. Pure: the same input is the same bytes. The Scene is
   plain, JSON-serialisable data in the **screen pixels of the viewport** (so the `<svg>` has
   `viewBox="0 0 width height"` and no transform): an ordered list of primitives (`rect`, `path`,
   `circle`, `text`, `icon`), each with a stable `id` (entry id, part index, purpose), a class
   name, numbers rounded to two decimals, a `bbox`, the `entryId` it came from (none for the sheet)
   and, on the first primitive of each placement, an accessible `label`. A number that is not
   finite throws a `RangeError`.
2. `paintSvg(scene, svg, options)` draws a Scene with `createElementNS`, `setAttribute` and
   `textContent` only, never `innerHTML`: a name a person wrote is text. Called again it updates
   the elements in place, so a focused mark stays focused while the map is panned. `sceneToSvg`
   writes the same tree as a string (escaped), for golden tests.
3. `hitTest(scene, point) -> entryId | null` and `createMapView` (pan, zoom, select, "whole map",
   "centre on") work from a Scene. `view.ts` holds the interaction's arithmetic as pure reducers.

Draw order: the sheet, then areas and water, other lines, pins, people; inside each by `z` then
entry id. Selection and hover only add a class (`m-on`, `m-hover`): they never change a mark's
shape or icon. Widths in map units (a river's band) scale with the zoom; strokes, pins and labels
are constant screen sizes.

## The contract

`System`, `Part` (`point`, `circle`, `polyline`, `bezier`, `polygon`), `Geometry`, `Style`,
`Placement`, `MapModel` and `View` are in `src/types.ts`; they are ADR 0336 to 0338 as the API
returns them. The roles are a closed list (`ROLES`); a role the list does not know is read as none.
Positions are drawing units, y down, and `project(system, point)` is the one place a position
becomes a drawing position (the identity for `plane` and `outline`).

`View`: `zoom` 1 fits the whole sheet in the viewport and 2 is twice that; `centre` is the drawing
point in the middle of the viewport; `groups` are Places (everything but presence and routes),
People (`presence`), Roads (`route`), Names (the labels) and `showPlaces` (a hairline outline for a
hit-only placement); `selection` and `hover` are entry ids.

## The default theme

| Placement | Drawn as |
| --- | --- |
| sheet | a flat fill of `--surface-muted` over the whole viewport |
| `water`, a line | a band 40 design units wide of `--action-surface` inside a 46 wide `--border-strong` border, round capped |
| `water`, an area | filled `--action-surface`, a `--border-strong` outline |
| `relief`, an area | short dotted arcs (`2 6`, 2 wide) in rows inside the shape, seeded from the entry's id and the part's index, so they never move and nothing is stored |
| `built-up`, `territory`, an area | dashed (`6 5`, 2 wide) strong outline, `--surface-warm` at 70% |
| `vegetation`, an area | the same outline, `--success-surface` at 80% |
| `route`, a line | dotted (`1 7`, 3 wide), `--text-secondary`, round capped |
| a point of any role | a 15 pixel radius disc (`--surface-default`, strong border) with the atlas icon of its first known kind (`kind-location` otherwise) and, with Names on, its name |
| `presence`, a point | a 12 pixel radius disc (`--action-surface`) with the first letters of the first two words of the name |
| any other role, or none | the neutral mark of its geometry: a thin strong line, a dashed outline with no fill, a pin |
| selection | the action colour, solid; a pin's ring is 3 wide |

A design unit is 1/1000 of the sheet's width, so a river is as wide on the screen on a 100,000 unit
sheet as on a 1,000 unit one (the Bench design's numbers are those of a 1000 wide sheet). A
placement's own `style` wins over the theme: `stroke` (`solid`, `dashed`, `dotted`, `double`,
`none`) and `weight` (`hairline` 1, `thin` 1.5, `regular` 2, `thick` 3, `heavy` 5 pixels). `none`
is hit-only: findable, focusable, drawn as nothing, or as a hairline outline with `showPlaces`.
`double` is an edge three times the weight with a gap of the sheet's colour over it. A river's band
takes the weight as a factor (`regular` is 1) and ignores the pattern; a pin takes neither.

## Adding a theme

A theme is a `Theme` (`src/theme.ts`): a `name`, the class of the sheet, `layer(placement, role)`
and `marks(input)`, which turns one part of a placement into `Mark`s (a `draw` of a line, area or
disc, a `text`, an `icon`) naming classes and widths. It never sees a stored coordinate or a
colour: the stylesheet gives the classes tokens. `layout` does the rest (projection, ids, rounding,
hit data, order, selection), so a second theme touches neither `layout` nor `paintSvg`. Only the
default exists (`defaultTheme`); choosing a theme is a later slice. Every class a theme writes
needs a rule in the stylesheet, which `test/css.test.ts` guards for the default theme.

## Interaction

`createMapView` pans by pointer drag and by the arrow keys, zooms by the wheel (toward the
pointer), `+` and `-` and `zoomIn`/`zoomOut`/`zoomTo` (clamped to 0.25 to 16), selects by click, or
Enter and Space on a focused mark (Escape clears), and has `fit()`, `centreOn(entryId)`,
`select`, `setHover`, `setGroups` and `setModel`. `onSelect` is called for what a person did, not
for `select()`; `onView` is called for every change of zoom or centre; `onHover` for the pointer
or the focus. It repaints at most once per animation frame, and uses no animation. There is no
pinch gesture.

## Looks and editing

`themes` / `themeNamed(name)` give the themes by name (`default`, `plain`; an unknown name is the default,
and `THEME_NAMES` is the list the API validates against, held to it by `map-engine/golden/themes.json`).
`setTheme(theme)` redraws with another without moving the view. `legend(model, theme)` is a pure list of
the roles on a Map with a swatch drawn by the theme, to be painted with `paintSvg`; it reads no name
(ADR 0352).

For an editor (ADR 0353) a view takes a `Tool` and an `Overlay`: `setTool(tool)` gives the pointer to the
tool in drawing units (`down`, `drag`, `up`, `click`, `dblclick`, `move`, `key`), and `setOverlay(shapes)`
draws lines, discs and draggable handles above the marks. A view with no tool behaves as before; the
renderer knows nothing of what the editor does with either.

## Grids

A system of kind `square`, `rect` or `hex`, or a Map's `overlay` grid, is drawn under the placements as
primitives of class `m-grid` and `m-grid-sub` (ADR 0355): lines for squares and rectangles, outlines for
hexes, and for a hex sub-grid a lattice of its own for each aperture (3, 4, 7). Cells under 6 pixels
are not drawn (8 for a sub-grid) and at most 6,000 at once; `gridPrims` also says whether the grid was
`drawn`, `too_fine` or `none`. `cellAt`, `cellCentre`, `cellPolygon`, `inGrid` and `cellCount` mirror
`packages/map-engine`'s functions and read the same `golden/cells.json`. `Groups.grid` is the switch.

## Tests

`pnpm run test` (vitest): Scene determinism, rejection of non-finite numbers, each shape and role,
zoom and centre arithmetic, the groups, the seeded arcs, golden SVG strings, `hitTest`, the view
reducers, a fake DOM for `paintSvg`, and the stylesheet guard. The drawing in a real browser, light
and dark, is the app's Playwright golden (ADR 0339).
