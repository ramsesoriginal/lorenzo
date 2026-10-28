# 0350 - Location and Map previews, and the card in Lorenzo Maps

Status: accepted with the maintainer on 2026-10-27; RFC 0048 slice 5. Adds two templates to the
registry of [ADR 0264](0264-link-previews.md) and uses the package of
[ADR 0349](0349-the-entry-preview-package.md) in Lorenzo Maps. Replaces the "name only" hover of
[ADR 0340](0340-the-map-view-in-lorenzo-maps.md).

## Decision

**Two templates.** The registry gains `location` and `map`, each with no stats, the 200-character
excerpt, and inheritance of the description and main picture from the nearest ancestor that has one,
like the fallback. `template_for` prefers kinds in this order: `character`, `being`, `item_instance`,
`item`, `location`, `map`, then the fallback; an entry that is a Location and also a Being is a being's
card, since the numbers a being carries are what a reader wants first. `LinkPreviewOut.template` is
already free text, so no response shape changes, and the route, its visibility rule and its 404 for an
entry the caller may not see are those of ADR 0264: a hidden Location or Map has no card, a hidden
description is not in a visible one's, and nothing of the Map's placements, subject or position is in
the card. The card does not say where a Location is or what it is within; its page does.

**The words.** `kindLabel` says "Location" and "Map". Those are the only two new strings.

**The card in Lorenzo Maps.** `/map/` installs the package with the triggers it already has: a mark of
the drawing (`.m-mark`, the entry in `data-entry`) and a row of the places list (`.map-place`, which
gains the same attribute). Hovering a mark, focusing it with the keyboard and hovering or focusing a
list row open the card of that entry, with the picture, kind and the start of the description; Escape
closes it. Touch is off: Maps is a desktop app and a tap selects, as it does. The line that named the
hovered mark under the drawing is removed, since the card names it. `loadCard` reads
`GET .../entities/{id}/preview` through the app's client and caches per page; `loadPicture` is the
app's authenticated file loader, whose object URLs are already released when the page is left.
Selecting, the panel and the list are unchanged, and nothing is read about where an entry is drawn.

## Validation and delivery

API: `template_for` for each kind and for the order above; the card of a visible Location and of a
Map (template, label, empty stats, excerpt, an inherited description and picture); the same entries
as a player who may not see them (404) and a hidden description (not in the card); an entry that is a
Location and a Being. The package's tests and inventory-web's existing end-to-end tests of the card
cover the shared behaviour. Maps' end-to-end tests: hovering a mark and focusing a list row show the
card with the right name and kind and `aria-describedby`, Escape closes it, a mark of an entry the
player may not see has no card because it has no mark, and axe finds no violation with a card open, in
light and dark.

## Excluded

Stats for a Location or a Map (a count of what is drawn, a distance), a "within" line, a card on
Bench, a preview of a placement rather than of an entry, and any new read of the map's own data.
