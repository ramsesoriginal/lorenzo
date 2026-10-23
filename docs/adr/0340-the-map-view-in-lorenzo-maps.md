# 0340 - The map view in Lorenzo Maps

Status: accepted with the maintainer on 2026-10-23; RFC 0048 slice 4.

## Decision

Lorenzo Maps ([ADR 0332](0332-lorenzo-maps-the-app.md)) gains a read-only view of a Map, using
`packages/map-renderer` ([ADR 0339](0339-the-map-renderer.md)) and the routes of
[ADR 0338](0338-reading-and-writing-maps.md). It is desktop only, as the app is.

**Pages.** `/maps/?tenant=…` lists the library's visible Maps (name, with a search) and links to each;
`/map/?tenant=…&id=…` (or `&slug=…`) is the view. The header's page links gain **Maps**, and the
app-links registry (ADR 0273) gains `map` and `map_by_slug` for `/map/`, filled from the registry
like the others. A Location's page links to the Maps that draw it only when a later slice adds that
read; nothing here asks the API "where is this drawn".

**The view.** A page head with the Map's name, its library, and for managers whether it is open to the
library; a toolbar of the toggles *Places*, *People*, *Roads*, *Names* and *Show places*, the zoom
buttons with the zoom as a percentage, *Whole map* and, once something is selected, *Centre on* its
name; the drawing; and a footer line with a tip. A selection opens a side panel: the entry's name as a
link to its page (a Location's own page; any other entry has no page here yet, so it is its name), its
kinds, and, for a Location, what it is within. A "Places on this map" list under the drawing mirrors
the selection and is how a keyboard or a screen reader reaches each placement. No control writes
anything in this slice.

The view reads the header once and the placements in pages until the Map is complete, up to the
renderer's visible limit, and says plainly when a Map holds more than it shows. It revalidates on each
open and keeps nothing in browser storage (ADR 0325). A Map that is not visible, or does not exist,
shows one message, the same for both. A library with no Maps says so; nothing is created for it.

**Hover.** A hovered or focused mark shows its name. The richer preview card of
[ADR 0264](0264-link-previews.md), with a picture and a line of text, arrives with the extraction of
the card into a package (slice 5); this slice builds no second copy of it.

**Look.** The page uses the brand's tokens only (the CSS guard checks the app's sheet), light and
dark, and follows the quiet interface the Bench and Beings designs set: no border but where it carries
meaning, no hover-only controls, 44-pixel targets on a coarse pointer.

## Validation and delivery

Browser tests against the real API: a GM places a Location pin, a region, a route and a presence
marker (through the API, as the app has no editor yet) and the view draws each, the toggles hide and
show their groups, zoom and "Whole map" move the drawing, selecting from the drawing and from the list
agree, a player sees only the placements of entries they can see with no trace of a hidden one, a
hidden Map and a missing one read alike, and axe finds no violation in light and dark.

## Excluded

Drawing, moving and removing placements (slice 6), the preview card (slice 5), choosing a theme,
and any phone layout.
