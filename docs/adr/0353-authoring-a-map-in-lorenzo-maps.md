# 0353 - Authoring a Map in Lorenzo Maps

Status: accepted with the maintainer on 2026-10-27; RFC 0048 slice 6. Adds writing to the read-only
view of [ADR 0340](0340-the-map-view-in-lorenzo-maps.md), over the routes of
[ADR 0338](0338-reading-and-writing-maps.md) and [ADR 0351](0351-writing-placements-in-bulk.md), with
the looks of [ADR 0352](0352-the-look-of-a-map.md). Desktop only, as the app is.

## Decision

**Who.** The controls below exist for those the API lets write (`can_manage` on the Map header, as
the Locations page already uses it); for everyone else the page is unchanged. The API decides every
write; the page only decides what to offer.

**Making and setting up a Map.** `/maps/` offers writers *Make a Map*: a name, whether everyone in the
library may see it, a plane or an outline, a width and a height, and optionally a unit and how many of
it one unit of the sheet is. `/map/` offers writers *Settings*: the name (the entry's own rename), the
same fields as above (the extent changes no placement), the Location the Map shows (found by name; the
Locations the writer may see), the Map's theme name (ADR 0352), and whether everyone in the library
may see it. Saving settings is the replace of ADR 0338 under `If-Match`, with the library's usual
"changed meanwhile" answer.

**Drawing.** *Edit this map* turns on a toolbar: **Select**, **Pin**, **Circle**, **Line** and **Area**,
with **Undo** and **Redo**.

- A drawing tool first asks *what are you drawing*: an entry found by name (any entry the writer may
  see) or a **new Location** with a name and whether to open it to the library (on when the Map is
  open). An entry already on the Map says that drawing it again replaces its drawing.
- **Pin**: one click. **Circle**: a click for the centre, a click for the edge. **Line** and **Area**:
  a click for each point, **Enter** or a double click to finish, **Backspace** removes the last point,
  **Escape** cancels; a line needs two points and an area three. The part drawn so far, and a rubber
  band to the pointer, are an overlay of the view, never a stored thing.
- Finishing writes the placement (the role is the one chosen for the entry's kind: `site` for a pin,
  none otherwise, to be set in the panel), selects it and returns to Select. A new Location is made
  with its own route first and then placed; if the placement is refused the Location stays, and the page
  says so.
- A server refusal (a polygon that crosses itself, a limit) is shown as it is given, the draft is kept
  and nothing else changes.
- Coordinates are kept to two decimals and are the Map's own units; a click outside the sheet is not
  taken.

**Editing.** With a placement selected the panel shows what a writer may change: its **role** (the 21,
in words, or none), **line** (the pattern and weight, or the theme's own), **drawing order**, a link to
the entry, and **Remove from this map**. For a placement of a single part that is a point, circle,
line or area (no curves, no holes) the panel also lists its **points as numbers** (x and y, a radius
for a circle), with add and remove, so everything can be done without a pointer; and the view shows
**handles** that are dragged to move a point, a centre or an edge, and a drag of the selected shape
itself moves it. A placement of several parts, curves or holes shows "Drawn with the API" and keeps the
role, line, order and remove controls. Each change is one write when it is finished (a drag on release,
a field on leaving it) and the view is updated from what the API returned, never ahead of it.

**Place the children.** For a selected Location drawn as a circle or an area, the panel says how many
of its visible parts are not yet on this Map and offers to place them: one pin each, with the role
`site`, laid out on a grid inside the shape, in one batch (ADR 0351, at most 100 at a time, the page says
when more remain). It writes explicit rows and nothing else.

**Undo and redo.** Every write the page makes (a draw, an edit, a remove, a batch) is one entry of a
history of the last 50, kept in the page's memory and gone when it is left. Undo writes back what the
placements were before (a redraw or a remove, or one batch for several), redo what they became. It is
a convenience, not a version control: it does not look at what others changed in between, and says so
when a write is refused.

**The look and the legend.** *Look* (the Map's own, Default or Plain) is offered to everyone and
remembered in the browser, and a **Legend** section lists what the Map's roles look like (ADR 0352).

**In the renderer.** The view gains what an editor needs and nothing that knows about editing: a
`Tool` (`down`, `drag`, `up`, `click`, `move`, `key`, a cursor) that receives the pointer in drawing
units instead of the selection while it is set, an `Overlay` of lines, areas, discs and handles in drawing
units that is drawn above the marks and hit-tested first, `setTool`, `setOverlay` and `setTheme`. A view
with no tool behaves exactly as before.

**Accessibility.** Every tool and control is a button or a field with a name; drawing has the numeric
path above (a pin is two fields and a button); the toolbar says which tool is on; a finished or refused
write is announced; the drawing stays a named group of buttons (ADR 0339).

## Validation and delivery

Unit tests for the pure parts: the geometry a tool builds and the edits made to it (rounding, add and
remove a point, move, a circle's radius, the grid of children), the history, and the renderer's overlay
and handle hit test. Browser tests against the real API: a writer makes a Map, draws a pin for an entry
and a new Location as an area, edits a role, a point by number and a handle by drag, undoes and redoes,
places the children of an area, removes a placement, changes the settings and the look; a player sees
none of the controls and the same Map; a refused write (a crossing polygon) leaves the draft; axe in
light and dark with a tool on and a panel open.

## Excluded

Curves and holes in the editor, several parts in one placement, drawing on a grid or a sphere (slices 7
and 8), pictures and layers, connections, snapping and guides, copy and paste, a drawing by several
writers at once, and any phone layout.
