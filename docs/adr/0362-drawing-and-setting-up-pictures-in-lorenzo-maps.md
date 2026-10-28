# 0362 - Drawing and setting up pictures in Lorenzo Maps

Status: accepted with the maintainer on 2026-10-28; RFC 0048 slice 9. Extends
[ADR 0339](0339-the-map-renderer.md) and [ADR 0353](0353-authoring-a-map-in-lorenzo-maps.md) for the
layers of [ADR 0361](0361-map-layers.md). Desktop only.

## Decision

**The renderer draws a picture and fetches nothing.** `MapModel.layers` is a list of
`{id, href, size: [width, height], opacity, calibration}` that the host made: `href` is a `data:image/`
URL (anything else is not drawn) and `size` the picture's natural size in pixels. `layout` places each
as an `image` primitive of class `m-layer` above the sheet and below the grid and every placement, with
no entry, no accessible name and no hit, and `paintSvg` writes it with `setAttribute` only. The matrix
that carries the picture's pixels onto the sheet is pure and tested: *fit the sheet* scales uniformly
to the extent and centres; two anchors, taken in pixels with the picture's real proportions, give a
turn, one scale and a move; three give an affine map. A `Groups.layers` switch (on) hides them, and a
sphere draws none.

**The app loads a layer the way it loads any file.** For each visible layer it fetches
`GET /payloads/{id}/content` with the bearer, makes a `data:` URL from the bytes (an SVG as well, ADR
0360; never a `blob:` URL for it), and measures the picture by decoding it. A layer that cannot be read
or decoded is left out and the page says how many were. The page shows a **Pictures** switch when
there are layers; a Map with none changes nothing.

**Setting up pictures** is a section of *Settings* for those who may write, and a Map that is a sphere
does not offer it:

- **Add a picture**: a file (png, jpeg, webp, gif or svg), a title, and *Everyone in the library may
  see it* (defaulting to the Map's own). The app creates an Information of type `picture` on the Map,
  uploads the file to it and adds the layer at the top. A refusal of the upload (a size, a type, an SVG
  the lint refuses) is shown as given and leaves no Information behind.
- **Each layer** lists its title and shows: *Fit the sheet* or *Set by two points*, the latter as two
  rows of fields (where in the picture, as a percentage across and down, and where on the sheet, its x
  and y); an opacity; **Move up** and **Move down**; **Replace the picture** (the file is added to the
  Information and the old one removed, so the layer *needs review*); **Mark reviewed** when it does;
  and **Remove** (the layer and its Information, after asking).
- A layer that *needs review* says so to the writer, in words, with what to do: look at the picture
  against the places and mark it reviewed, or set it up again.

**What the picture may not do.** It is under the marks and never a target: a click on it is a click on
the sheet. Pinning to a point of the picture is always done with the sheet's own coordinates, which the
pointer already says.

## Validation and delivery

Renderer: the matrix of each calibration (fit with wide and tall pictures, two anchors turned and
scaled, three anchors sheared), that a `data:` URL is drawn and another is not, the order of the
primitives, no hit, the switch, and the Scene of a Map with no layer unchanged. App unit tests for the
fields as calibration. Browser tests against the real API: a writer adds a picture (and one the lint
refuses is shown as refused), sets it by two points and sees it move, reorders two layers, replaces
one and sees *needs review* and clears it, and removes one; a player who may not see the Information
sees the Map without it and a player who may sees it with the switch; a sphere offers no Pictures;
axe in light and dark with the section open.

## Excluded

Dragging, turning or scaling a picture on the map, choosing points by clicking on a preview, a
three-point form, tiles and zoom levels of a large picture, a theme drawing the picture differently,
and hotspots from an SVG's own elements.
