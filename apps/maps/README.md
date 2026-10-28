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
undo and redo, and *Settings* (name, sheet, the Location it shows, theme name, who sees it). *Look* and
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
