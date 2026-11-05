# Maps: design

A fresh design of Lorenzo Maps, from the jobs people do there. The system it is built on is in [the web design](../README.md): the shell, the templates, the states and the decisions D1 to D29. The account hub, Writing, and Calendars with Sessions are decided. This page holds the brief, the questions and the decision log for this app.

Status: the brief and its questions. No direction is chosen yet.

## What the app is for

Maps holds the places of a library and draws them. Two kinds of entry carry it:

- A **Location** is a place, from a universe down to one floor of a building. Locations sit in a tree of "part of" that skips levels. The tree is not containment: a village and a floor are both Locations, and nothing says one holds the other in the world.
- A **Map** is an entry that draws entries: generated from data, laid over a picture, or both. It has a coordinate system chosen by its author (a free plane, a grid of squares, rectangles or hexes, a sphere, or an outline that measures nothing).

Roads, rivers, stairs and portals are data, so that a distance is computed when the data exists and is otherwise unknown. Locations and Maps can be tied to a calendar period; neither needs to be. Sources: [the app's README](../../../../apps/maps/README.md), [RFC 0048](../../../rfcs/0048-locations-maps-connections-and-optional-dates.md), ADRs [0330](../../../adr/0330-locations-the-kind-and-the-part-of-tree.md) to [0340](../../../adr/0340-the-map-view-in-lorenzo-maps.md), [0350](../../../adr/0350-location-and-map-previews.md) to [0368](../../../adr/0368-distance-in-lorenzo-maps.md), and [0371](../../../adr/0371-the-periods-a-date-is-tied-through.md) to [0377](../../../adr/0377-the-date-lens-on-locations-in-lorenzo-maps.md). Frames and axes have no screen and are not designed here.

**What this design does not draw.** The map itself, its marks, its themes and its looks, are drawn by the framework-free renderer package from stored data alone, and reproduce Bench's map design ([RFC 0048](../../../rfcs/0048-locations-maps-connections-and-optional-dates.md), input 5). Bench is not redesigned here. This design is for everything around the drawing: the page, the lists, the panels, the tools, the settings.

## Already decided

- **The date lens uses the shared time filter** (CS2, CS7). A Maps list or a Locations list is looked at through one date, from the periods things are tied to, and nothing is inferred. The component is built once and shared.
- **The shell** (D12 to D29): the header, the app's own Home, the status bar, the palette, overlays, loading, empty and error states. `empty-map` is on the [illustration list](../mascot-images.md).
- **Words and gestures from Writing:** drag and drop with a menu twin, undo as a whole, a refusal that says why.

## The jobs

Ordered by who arrives and what they need in the first minute.

| Who | The job | Needs from the data |
| --- | --- | --- |
| A reader | Find a place by name, or walk the tree from a world down to a room | Locations the reader may see, each under its nearest visible ancestor |
| A reader | See where a thing is, as one character would say it | whereabouts: with you, stashed, elsewhere, unknown, and at most one name |
| A reader | Read a Map: zoom and pan; switch places, people, roads, names and pictures on and off; see what a mark is | the placements and the Map's look |
| A reader | Follow a mark: its panel, its card on hover, where it leads and on which other Maps the far end is | the entry, its connections |
| A reader | Measure how far one place is from another | the straight line in the author's unit; by connections when a number stat is chosen; how a grid counts a diagonal |
| A reader | Choose how a sphere is drawn for themselves: flat, Mercator, or a turnable globe | the Map's system |
| A reader | Look at the lists through a date | the periods Maps and Locations are tied to |
| A writer | Add, rename, move, open or close, and order Locations | the tree, who may see each |
| A writer | Make a Map: a name, who sees it, a plane or an outline or a grid or a sphere, a size, a unit | the Map header |
| A writer | Draw on it: pins, circles, lines, areas, cells; undo and redo; set a role, a line style, a drawing order | placements |
| A writer | Place the children of a Location that is drawn as an area | the tree and the area |
| A writer | Put pictures under a Map: fit the sheet or give two points, order, replace, remove | pictures |
| A writer | Join one place to another, or take a connection away | connections |
| A GM | Read the library's addresses and the Location lint | the GM's address and the lint |

Roles in play: Author, GM, full-visibility Owner or Organizer (they write Locations and Maps), and everyone else (they read what is visible).

## What stays true, whatever it looks like

Rules about behaviour and honesty, not about pictures. They hold in any direction (RFC 0048, G1 to G7).

- **A hidden thing is absent** (D24). No placeholder, no count of what is missing, and nothing private through a pin, a line, an area, a card, a count, a page of results, an error, a distance or a route. A hidden level in the tree leaves no trace; a Location is shown under its nearest visible ancestor.
- **The page says "in" or "within" for every step,** because the tree is not containment.
- **Absence means "not modelled", never unknown or default.** A feature that is not used costs no field and no row. Where a whereabouts or a distance cannot be known, it says so in words ("unknown"), and nothing is invented.
- **There is no default unit, system, genre or vocabulary.** The author chooses the coordinate system and the unit, and the reader sees the author's words.
- **No time is assumed.** A Map or Location with no period behaves as it always did. "Where is my stuff" takes no time.
- **Positions never inherit.** An entry has its own geometry on each Map.
- **A Map's data and its look are separate.** A reader may change a look and how a sphere is drawn for themselves; it is remembered in the browser and never changes what is stored.
- **A refusal is shown as it is given,** the draft is kept, and nothing else changes (a shape that crosses itself, a limit, a version that changed meanwhile).
- **Coordinates are the Map's own units,** kept to two decimals. A click outside the sheet is not taken, and every point is also a number a person can type.
- **Every drawing is reachable without a pointer.** The drawing is a named group of buttons; a mark whose drawn text is not its name carries that text in its name (a person's initials).
- **The API decides every permission;** the page decides only what to offer.
- **Words** follow identity §14.3 and the ADRs: Location, Map, place, part of, in, within, pin, circle, line, area, cell, sheet, theme, connection.

## Visual or structural decisions in the old documents

Named here so each can be kept or dropped on purpose. None carries over by default.

| From | What it decided | The question |
| --- | --- | --- |
| ADR 0332 | Desktop only: below 720px one column and larger targets, but no phone layout of its own | What does Maps do on a phone and a tablet? |
| ADR 0332 | Locations: a list with name search, a tree of roots with their parts, and a Location page | Does the Locations area keep that shape? |
| ADR 0340 | `/maps/` lists Maps and `/map/` draws one; selecting a mark opens a panel; "Places on this map" is a list; hover or focus opens a card | Where do the panel, the places list and the switches go? |
| ADR 0353 | **Edit this map** turns on a toolbar: Select, Pin, Circle, Line, Area (and Cells), with Undo and Redo | How do the tools appear? |
| ADR 0353 | A tool first asks what you are drawing: an entry found by name, or a new Location | Does that question stay a dialog? |
| ADR 0353 | **Settings** holds the name, the sheet, the Location shown, the theme name, who sees it, and the Pictures section | Where do settings and pictures live? |
| ADR 0352 | **Look** and **Legend** are for everyone | Where do they sit? |
| ADR 0365 | A placed entry's panel says where it leads and on which other Maps the far end is | Does that stay a line in the panel? |
| ADR 0358 | A reader chooses how a sphere is drawn and turns a globe | Does the choice stay beside the Map? |

## Questions

1. **Where does the app begin?** Maps has its own Home (D16).
   - **A. A gallery of Maps.** Each Map as a card with a small drawing of it, its system and its date tie; "Make a Map" first; Locations a tab beside it.
   - **B. The Locations tree and search first.** The way to a place, with Maps a tab.
   - **C. A start from you.** Where your characters are now (their whereabouts), your recent Maps, then the gallery.
2. **Phone and tablet.** The old design is desktop only. On a phone:
   - **A. Read everything, write on a larger window.** Reading, panning, zooming, the panel as a sheet and the list all work. Drawing says it needs a larger window and offers what a phone can do: rename, move a pin by its numbers, change who sees it.
   - **B. Full drawing on a phone** by touch, with every tool.
   - **C. Reading only on a phone,** with no writing at all.
3. **The Map page.** Where do the selected mark, the places list, the switches, the Look and the legend go?
   - **A. A docked panel beside the Map,** with tabs: Selected, Places, Layers and legend. The Map is large and calm.
   - **B. The Map fills the page,** with small floating controls on it and a panel that slides over from the side.
   - **C. A split: the places list on the left, the Map on the right,** with the selected mark in a drawer under it.
4. **Drawing.** Drag and drop was liked in Writing.
   - **A. A toolbar over the Map,** as today: pick Pin, Circle, Line, Area, then click.
   - **B. A small palette on the Map,** with actions that appear beside what is selected, so the tools are close to the work.
   - **C. Place by dragging.** Drag an entry from the list or a search onto the Map to place it; the tools are for shapes. A right-click gives the same actions as a menu, and every gesture works from the keyboard.
5. **Old decisions.** From the table above: which carry over? "All except …" is a good answer.

## Decision log

Nothing is decided here yet.
