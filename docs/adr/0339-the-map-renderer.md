# 0339 - The map renderer and its default theme

Status: accepted with the maintainer on 2026-10-23; RFC 0048 slice 4.

## Decision

`packages/map-renderer` is a framework-free TypeScript package, in the shape of the other shared
packages, that draws a Map from what the API returns and nothing else. No map library, no tile
service, no canvas, no network: it is hand-written SVG and it never fetches. It ships source, as the
other packages do, and Lorenzo Maps is its first consumer; Bench takes it later without a change.

**Three steps, kept apart.**

1. `layout(model, view, theme) -> Scene`: a pure function from the Map's system, its placements, the
   view (which role groups are shown, whether labels are, the selection, the zoom and pan) and a
   theme, to a plain-data `Scene`: an ordered list of primitives (paths, circles, text, markers)
   with stable ids, numbers rounded to a fixed number of decimals, each primitive's bounding box and
   the placement it came from. It rejects NaN and Infinity, and the same input is the same Scene,
   byte for byte.
2. `paintSvg(scene, svg)`: draws a Scene into an `<svg>` with `createElementNS` and `textContent`
   only, never `innerHTML`, as the Bench ancestry graph does. Text a person wrote is never parsed.
3. `hitTest(scene, point)` and the interaction module: pan (drag and keys), zoom (wheel, the buttons,
   `+` and `-`), select, and "whole map" and "centre on", from a Scene. The interaction module emits
   events and never fetches or writes; the app decides what a selection opens.

`project(system, point)` is the one place a position becomes a drawing position. For `plane` and
`outline` it is the identity, as storage and SVG are both y-down.

**Themes.** A theme is a code module: for each role, and for a placement with no role, how its
geometry is drawn (the kind of mark, its width, its dash, its fill, which tokens it takes), plus the
furniture around the drawing. The data never says how it looks, apart from a placement's own `style`
(ADR 0337), which a theme honours over its default. A theme names tokens of the brand
(`--surface-muted`, `--border-strong`, `--action`, `--action-surface`, `--success-surface`,
`--surface-warm`, `--text-primary` and the rest), never a colour, so dark mode follows the brand and
not a second palette. A theme cannot add a role, a field or a request. This slice has one theme, the
**default**, reproducing the Bench design (`docs/design/bench/screens/15-map.jpg` and its prototype):

| Placement | Drawn as |
| --- | --- |
| the sheet | a flat fill of the muted surface, to the extent and beyond |
| `water` (a line) | a band of the action surface, bordered by a slightly wider strong stroke, round-capped |
| `water` (an area) | the same colours, filled |
| `relief` | short dotted arcs, in the strong border colour, set in a row inside the shape and seeded from the entry's id so that nothing random is stored and the arcs never move |
| `built-up`, `territory` | a dashed strong outline and a warm fill at 70% |
| `vegetation` | a dashed strong outline and the success fill at 80% |
| `route` | a dotted line of the secondary text colour, round-capped, 3 units wide |
| a point (any role) | a 15-unit disc of the default surface with a strong border and the atlas icon of its kind, and its name beside it when names are shown |
| `presence` | a 12-unit disc of the action surface with the entry's initials |
| a selection | the action colour, solid; it never changes a mark's shape or icon |
| a hit-only placement | a hairline outline while "show places" is on |

The dotted route is the theme's choice for parity with the design: it is a documented exception to
the brand's rule that a dotted edge means unknown (identity section 18), and a placement's own solid
`style` overrides it. A role the theme does not know, and a placement with none, are drawn as the
neutral mark of their geometry. Roles group into the toggles Places (including no role), People
(`presence`), Roads (`route`) and Names; "show places" is a fifth switch that starts on.

**Reading it without sight.** The `<svg>` is `role="img"` with a title and a description; each
placement is focusable with an accessible name; and a "Places on this map" list, kept in step with the
selection, is the primary non-visual form. Pan and zoom work from the keyboard, nothing is
hover-only, and nothing is told by a colour alone (identity section 15).

**Tests.** Scene JSON snapshots for each shape and role (the same input, the same bytes); the
SVG strings `paintSvg` writes for a small map; `hitTest`; the interaction's pure reducers; and a
Playwright golden of the default theme's own rendering, light and dark, with a small tolerance on
pinned fonts. Likeness to the Bench design is reviewed by looking at the design beside the
rendering in the pull request, not by comparing pixels with a mock-up drawn by another tool.

## Excluded

Grid and sphere projections (slices 7 and 8), pictures and layers (slice 9), drawing and editing
(slice 6), links and routes drawn from connections (slice 10), themes other than the default and a
way to choose one (slice 6), and animation beyond what the brand allows (calm, short, reduced-motion
respected).

## Addendum: what the browser check changed (2026-10-23)

Axe reports a focusable mark inside `role="img"` as `nested-interactive`, so the app draws the map as
a named `role="group"` of buttons (`PaintOptions.role` and `MapViewOptions.role` already allowed it);
`img` stays the renderer's default for a drawing nobody can focus into. A mark's accessible name
holds any text drawn in it that the name lacks, so a person's initials are read as "Bram the guide,
BT, presence" (`label-content-name-mismatch`; a parenthesis does not count, as axe drops
parentheticals). `iconBase` is the directory the brand's `icons.svg` is served from, not the file.
