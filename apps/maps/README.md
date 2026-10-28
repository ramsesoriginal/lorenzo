# Lorenzo Maps

Static Astro app for the places of a library: Locations, their part-of tree and, in later slices of
[RFC 0048](../../docs/rfcs/0048-locations-maps-connections-and-optional-dates.md), maps drawn from them.
[ADR 0330](../../docs/adr/0330-locations-the-kind-and-the-part-of-tree.md),
[ADR 0331](../../docs/adr/0331-a-location-may-be-any-kind.md) and
[ADR 0332](../../docs/adr/0332-lorenzo-maps-the-app.md). Desktop only for now: no phone layout, no offline use.

A Location is an entry kind. It sits in a single-parent tree that skips levels: a universe, a village
and one floor of a building are all Locations, and a floor is an ordinary Location in the one above
it. The tree is not containment. A reader sees every Location they may see under its nearest visible
ancestor, so a hidden level in between leaves no trace, and the page says "in" or "within" for every
step. Those who may write Locations (Authors, GMs and full-visibility Owners and Organizers) add,
rename, move and open or close them to the library; everyone else reads only what is visible.

A Map is an entry kind too ([ADR 0336](../../docs/adr/0336-maps-the-kind-its-system-and-its-placements.md)
to [ADR 0340](../../docs/adr/0340-the-map-view-in-lorenzo-maps.md)). `/maps/` lists the Maps a person may
see and `/map/` draws one with [`@lorenzo/map-renderer`](../../packages/map-renderer): places, people,
roads and names can be switched off, the drawing zooms and pans, and selecting a mark, here or in the
"Places on this map" list, opens a panel, and hovering or focusing a mark or a row opens the entry's card ([ADR 0350](../../docs/adr/0350-location-and-map-previews.md)). Those who write Locations can author a Map
([ADR 0351](../../docs/adr/0351-writing-placements-in-bulk.md) to
[ADR 0353](../../docs/adr/0353-authoring-a-map-in-lorenzo-maps.md)): *Make a Map* on `/maps/`, and on
`/map/` *Edit this map* with Pin, Circle, Line and Area tools (a handle is dragged; every point is also a
number field), role, line and drawing order, "place the children" of a Location drawn as an area,
undo and redo, and *Settings* (name, sheet, the Location it shows, theme name, who sees it). A Map may be a grid of squares, rectangles or hexes (the
hexes' orientation is always chosen), or have a grid drawn over it; a Grid switch, the cell under the
pointer in words, *Snap to the grid* and a *Cells* tool for regions of whole cells come with it
([ADR 0354](../../docs/adr/0354-grid-systems-square-rectangular-and-hex.md) to
[ADR 0356](../../docs/adr/0356-authoring-on-a-grid.md)). A Map may be a *sphere*, with places given by
longitude and latitude and drawn flat, as Mercator or as a globe; a reader may choose how it is drawn
for themselves and turn a globe, the pointer says where it is in words, and a writer draws pins, lines
and areas on it ([ADR 0357](../../docs/adr/0357-the-sphere-system.md) to
[ADR 0359](../../docs/adr/0359-authoring-on-a-sphere.md)). A Map may have pictures under it, which a
writer adds, places by fitting the sheet or by two points, orders, replaces and removes in the Pictures section
of Settings, and which a reader may hide with the Pictures switch
([ADR 0360](../../docs/adr/0360-pictures-a-stored-fingerprint-svg-and-when-to-leave-postgres.md) to
[ADR 0362](../../docs/adr/0362-drawing-and-setting-up-pictures-in-lorenzo-maps.md)). A Location page lists
the connections it is an end of and lets a writer join it to another place or remove a connection, and a placed
entry's side panel says where it leads and on which other Maps the far end is
([ADR 0363](../../docs/adr/0363-connections-the-kind-and-its-two-ends.md) to
[ADR 0365](../../docs/adr/0365-connections-in-lorenzo-maps.md)). A Map page can measure how far one place is
from another, by the straight line on the Map in its author's own unit and, when a number stat is chosen, by the
connections, and a square or rectangular grid says how it counts a diagonal
([ADR 0366](../../docs/adr/0366-straight-line-distance-on-a-map.md) to
[ADR 0368](../../docs/adr/0368-distance-in-lorenzo-maps.md)). When the library has a calendar the Maps list can
be looked at through a date, chosen with the shared period picker, saying which Maps are tied to it, not tied to a
date or tied to other dates ([ADR 0371](../../docs/adr/0371-the-periods-a-date-is-tied-through.md) to
[ADR 0373](../../docs/adr/0373-the-date-lens-in-lorenzo-maps.md)). *Look* and
a *Legend* are for everyone ([ADR 0352](../../docs/adr/0352-the-look-of-a-map.md)). The drawing is a named group of buttons, because axe reports focusable marks
inside `role="img"` (`nested-interactive`), and a mark whose drawn text is not its name carries that text
in its name (a person's initials), as `label-content-name-mismatch` requires.

## Development

Set `PUBLIC_API_BASE_URL`, `PUBLIC_AUTHGEAR_ENDPOINT` and `PUBLIC_AUTHGEAR_CLIENT_ID` from `.env.example`.
Use Node and pnpm from the repository. `mise run //apps/maps:dev` serves port 4328. The app owns
`lint`, `test`, `build` and `test-e2e` tasks; the browser tests run against the real API on a disposable
database, with launcher ports of their own (Authgear 4415, API 8780, site 4346). Reads are held in memory
for a few seconds under the viewer's scope (`@lorenzo/read-cache`); nothing private is kept in browser
storage. Only the appearance preference is remembered.

## Hosting

See [docs/operations/maps-setup.md](../../docs/operations/maps-setup.md). The planned Pages address is a
fallback until configured; cross-app destinations are resolved through `GET /app-links`.

## Page frame

The header, skip link, welcome, footer and theme toggle come from
[`@lorenzo/app-shell`](../../packages/app-shell/README.md) over the shared brand;
`src/layouts/Base.astro` only names the product, its page links and its welcome text.
