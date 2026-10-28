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
