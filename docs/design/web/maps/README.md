# Maps: design

A fresh design of Lorenzo Maps, from the jobs people do there. The system it is built on is in [the web design](../README.md): the shell, the templates, the states and the decisions D1 to D29. The account hub, Writing, and Calendars with Sessions are decided. This page holds the brief, the questions and the decision log for this app.

Status: decided (MP1 to MP6). The prototype is being built.

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

Decided with the maintainer, 2026-11-05, from the brief above.

### MP1. The app begins at a gallery of Maps

Each Map is a card with a small drawing of it, its coordinate system and its date tie. "Make a Map" comes first. Locations is a tab beside it. Turned down: the Locations tree first (B) and a start from the person's characters (C).

### MP2. A phone reads everything and writes on a larger window

Reading, panning, zooming, the panel as a sheet and the places list all work on a phone. Drawing says it needs a larger window, and offers what a phone can do: rename, move a pin by its numbers, change who sees a Map. Turned down: full drawing by touch (B) and reading only (C).

### MP3. The Map fills the page

Small floating controls sit on the Map (zoom, layers, Look, Legend, the way a sphere is drawn), and a panel slides over from the side for the selected mark, the places list and settings. Turned down: a docked panel (A) and a split with the list (C).

### MP4. Drawing is a toolbox, and entries can be dragged onto the Map

The conventions are those of Blender, Photoshop and AutoCAD, for people who draw all day:

- **A toolbox** of modal tools (Select, Pin, Circle, Line, Area, Cells), an **options bar** that changes with the tool, and a **properties** panel for the selection, with every number typeable.
- **Keyboard first:** one key per tool, Enter and Escape to finish and cancel, Backspace to take back a point, and the arrow keys to nudge. The pointer is never the only way (the rule above).
- **Snapping** to the grid and to other points, switched on and off, and a **history** of what was done, with undo and redo.
- **Navigation** that does not leave the tool: scroll to zoom, hold Space to pan, a key to frame what is selected.
- **Drag an entry** from the places list or a search onto the Map to place it. A right-click offers the same actions as a menu, and each gesture works from the keyboard.
- This asks for a **denser** layout than the rest of the web design, so the drawing view uses the Dense setting (D22) for its toolbox and panels.

Turned down: a toolbar alone (A, as it was) and dragging alone (C).

### MP5. The old decisions

All as recommended: the phone replaced by MP2; Locations a tab with search, the tree, and a list by name while a date is chosen; the two places (the gallery and the Map) kept, with the hover cards, and the panel and places list in the slide-over; the toolbar carried into the toolbox of MP4; the "what are you drawing" question a small popover at the tool instead of a dialog; Settings in the slide-over with Pictures as a section; Look and Legend as floating controls; where an entry leads as lines in the panel; the way a sphere is drawn as a floating control.

### MP6. The drawing view is C, with A's options bar, layers and history, and B's command line

- **From C (Blender):** a row of tools in a header over the Map, an outliner of the places, a sidebar with tabs, and drag from the outliner onto the Map.
- **From A (Photoshop):** an **options bar that changes with the tool**, a **Layers** panel and a **History** panel.
- **From B (AutoCAD):** a **command line** under the Map that asks for the next point and takes typed coordinates and commands.
- Turned down as the base: A's toolbox and B's ribbon.

**A tool set that grows.** More tools are coming: cave systems, filling parts of a Map by marching squares or wave function collapse, heights, height lines, splines, freehand, and more. The drawing view is built for that, not for the six tools of today:

1. **A tool is a declaration, not a layout.** Each tool states its name, group, icon, key, what it takes as input (a click, two clicks, a path, a drag, a brush, a region), the options it shows (a name, a type, a range, a seed), what it produces, and whether it can preview. The toolbox, the options bar, the command line, the palette and the key map are all drawn from these declarations, so a new tool adds one entry and no new screen.
2. **Tools are grouped, and a group scales.** The header shows one button per group (Select, Place, Draw, Terrain, Generate, Modify) with the group's current tool, and a flyout for the rest. **Search all tools** finds any tool by name or key, and the command line takes the tool's name. A tool the data cannot hold yet shows as **planned**, with the reason.
3. **A generator previews, then applies.** A generating tool (a cave system, a fill) works on a region: the chosen Area, or the whole sheet. It draws a **preview** as an overlay that is never stored, shows its options in the options bar (a **seed** among them, and a button to roll another), and does nothing to the Map until **Apply**. Apply writes ordinary placements in one step, with one history entry that names the tool and the seed. **Discard** drops it.
4. **What a tool makes is data the Map already holds,** or the tool says it needs a decision first. A cave is areas; a marching-squares fill is areas and contour lines; wave function collapse on a grid is cells; a spline, a freehand stroke and a contour are lines with a value. A **heightmap is a raster,** which the Map does not hold today: that tool is drawn, marked **planned**, and needs its own decision before it is built.
5. **Every tool has a keyboard and a number twin.** Each option is a field, each point is a number, and each command is a line the command line accepts. A generator can be run from the command line with its parameters.
6. **History is the undo surface** in the drawing view: each step is a name ("Drew a cave, seed 4821"), and a person can step back to any of them.
7. **The registry is the contract for the real app,** so a new tool is built against it (an ADR names the tool, its output and its data), and the design needs no change for it.

## The directions (drawn; C with parts of A and B chosen)

In `directions/`: the gallery (MP1), the read view with its slide-over panel (MP3), and three layouts for the drawing view (MP4), on the shell. The map is an SVG stand-in for the renderer's drawing, with made-up data. In all three the Map fills the page and the toolbox and panels float over it; the drawing view is Dense (D22). Run it:

```bash
python3 -m http.server 8731   # from the repository root
# open http://localhost:8731/docs/design/web/maps/directions/index.html
```

The controls bar switches the screen and whether a line is being drawn or an Area is selected. Screens are in `directions/screens/` (9 images).

| | A. Toolbox and panels | B. Ribbon and command line | C. Header and outliner |
| --- | --- | --- | --- |
| Model | Photoshop | AutoCAD | Blender |
| Tools | A vertical toolbox on the left, one key each | A ribbon with Draw, Modify, View and Map tabs, in groups | A row of tools in a viewport header, and a mode menu |
| Options | An options bar on top that changes with the tool | The ribbon, and a command line below that asks for the next point and takes typed coordinates | A "last operation" panel at the corner that stays editable |
| The selection | A Properties panel with Layers and History under it | A Properties palette that appears for a selection | An outliner of the places, and a sidebar with Item, Tool and View tabs |
| Placing by dragging | From a search in the options bar | From a list the person opens | From the outliner, which is always there |
| Best for | Drawing shapes by hand | Typing exact values | Working through many places by name |
| Cost | Three panels on the right take width | The ribbon and command line take height | The densest; the most to learn |

## Open questions

None for the choice. The prototype comes next.
