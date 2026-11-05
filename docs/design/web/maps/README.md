# Maps: design

A fresh design of Lorenzo Maps, from the jobs people do there. The system it is built on is in [the web design](../README.md): the shell, the templates, the states and the decisions D1 to D29. The account hub, Writing, and Calendars with Sessions are decided. This page holds the brief, the questions and the decision log for this app.

Status: decided (MP1 to MP6). The prototype is built and ready for review.

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

## The prototype

In `prototype/`. It links `apps/brand` in place and unchanged, and extends the shell prototype through its hooks. The map is an SVG stand-in for the renderer's drawing; everything around it is the design. Plain HTML, CSS and JS.

```bash
python3 -m http.server 8731   # from the repository root
# open http://localhost:8731/docs/design/web/maps/prototype/index.html
```

A private single-page copy is built with `node build-review-copy.mjs --fragment OUT_DIR`. The controls bar switches the role (a GM, a reader).

### Reading

- **The gallery (MP1).** A card per Map with a small drawing, its system and its date tie, and "Make a Map" first. Making one has no default system, and hexes ask for their orientation. **Looking at a date** (the shared time filter, CS7) groups the Maps as tied to that date, not tied to a date, or tied to other dates. A reader does not see a Map that is not open to the library. A library with no Map shows the empty state (`empty-map`).
- **Locations.** A tab with search and the tree of "part of". A GM sees closed Locations and can open or close them; a reader sees no trace of a closed one, and a Location inside it appears under its nearest visible ancestor, in words ("in Customs house, within Old town, within Harbour town"). Through a date the list is by name, tied first, and says the tree is not shown. A Location page has its connections (join, remove with Undo), where characters are ("here", "elsewhere, at …", "unknown"), and, for a writer, its place in the tree. GMs see the lint.
- **The Map (MP3).** It fills the page. Floating controls: Places, a date, Edit this map, Layers, Look (only for you, in this browser), Legend, the way a sphere is drawn (flat, Mercator, a globe), zoom and frame. Selecting a mark, or a place in the list, slides a panel over: where it is "in … within …", the date it is tied to, **where it leads and on which other Maps the far end is,** and **Measure from here** (a straight line in the author's unit, and the connection's length, or "unknown"). The panel also holds the searchable Places list, and, for a writer, Settings: name, sheet, the Location shown, theme name, who sees it, and Pictures (show, opacity, add, replace, remove).

### Drawing (MP4, MP6)

- **The layout.** C's header of tools and outliner and sidebar, A's options bar, Layers and History, and B's command line under the Map. The Map is full-bleed under everything. It is Dense.
- **The tool registry.** `mp-tools.js` holds one list that declares every tool (group, icon, key, input, output, options, planned, needs). The header's groups, their flyouts, the options bar, the command line's tool names, the key map and **Search all tools** are all drawn from it. 13 tools today: Select; Pin, Circle; Line, Spline, Freehand, Area, Cells; Height line, Height brush; Cave system, Fill by marching squares, Fill by wave function collapse. A tool needing a grid says so on a plane. **Adding a tool is adding one entry.**
- **The tools that exist.** Pin, circle, line, spline (a smooth curve through the points), freehand (simplified as set), area, a height line with a value and unit, and cells on a grid Map.
- **Generators preview, then apply.** A cave system (cellular automata, traced by marching squares), a fill by marching squares (noise, with optional height lines) and a fill by wave function collapse (on a grid) work on the selected Area or the whole sheet. Each shows a **preview overlay that is never stored,** has a **seed** and a Roll, and **Apply** writes ordinary placements in one history step that names the tool and the seed. **Discard** writes nothing.
- **The height brush is drawn and marked planned,** with the reason: a heightmap is a raster, the Map holds none, and it needs its own decision. It paints a prototype-only field so its place in the layout can be judged. Its height lines are ordinary lines.
- **Every number is typeable.** The Item tab shows each point as two fields; a point outside the sheet is refused with the range. The arrow keys nudge a selection (a cell on a grid). Snap to the grid or to 5 units.
- **Keyboard first.** A key per tool (V P C L S F A G T H), Enter to finish, Backspace to take back a point, Escape to cancel, Delete, Ctrl Z and Ctrl Shift Z, `/` for the command line, Space to pan, the wheel to zoom, Home to frame.
- **The command line.** It asks for what comes next ("LINE  Next point (x,y), [C]lose, Enter to finish") and takes `PIN x,y`, `CIRCLE x,y x,y`, `LINE x,y x,y …`, a tool's name, `SEED n`, `ROLL`, `APPLY`, `DISCARD`, `UNDO`, `REDO`, `FIT`, `SELECT name`, `HELP`; a generator runs from it. A planned tool says why.
- **History is the undo surface.** Each step has a name ("Drew a cave system, seed 4821: 6 caves in the whole sheet"), a person can step to any of them, and the redo steps stay shown.
- **Dragging an entry from the outliner onto the Map places it,** with a **Place** button as the keyboard twin.
- **Wave function collapse and Cells** work on "The lamp tunnels", a grid of squares.
- **On a phone** the Map reads in full (the panel is a sheet). "Edit this map" opens a page that says drawing needs a larger window and offers the small changes: the name, who sees it, and a pin's numbers.

### What it fakes

All data is made up and held in memory (`mp-data.js`). The map is an SVG stand-in, not the renderer. Only the Harbour, the Lamp tunnels and the Reach open; the others show a placeholder. The sphere is a hand-drawn few shapes with three projections. Saving, pictures and connections change nothing outside the page. The height brush is not stored.

### What was checked

- 71 scripted checks in Playwright, all passing: the gallery and the date lens, making a Map, the tree for a GM and for a reader, the in-words path under a hidden level, the Location page, the read view (panel, where it leads, measuring, layers, look, legend, settings, a globe), a reader's limits, every drawing tool by key and pointer and by numbers, history, all three generators and their preview, Apply, Undo and Discard, the planned tool, the command line (typed lines, pins, a generator, an unknown command), the tool palette, drag from the outliner, a grid Map with cells and wave function collapse.
- axe-core: no violations on seventeen states (the gallery, a date lens, Locations, a Location, the read view with the panel, the places list, settings and the legend, a sphere, the drawing view, a generator preview, an item, the tool search, a flyout, a grid Map) at 1440 and 430 wide, in light and dark (the landmark-region rule is off for the page's overlays).
- Touch targets of at least 44px at 430 wide, on five routes, apart from inline text links and the shell's account button (43px).
- No console errors.

### What was not checked

A screen reader (the drawing is a named group, and the marks are reachable through the Places list), a real touch device, colour-blindness simulation, Safari and Firefox, drawing on a touch screen, a large Map with thousands of placements, and the real renderer.

### Findings

- **Key letters clash with the shell.** The shell's single-key switch uses G as the start of a chord, and the drawing view wants G for Cells. A person can turn single keys off (WCAG 2.1.4), but the drawing view should own its keys while it has focus and say so in the shortcuts list.
- **A tool needs the sheet's free area.** The floating header, options bar and docks cover the top and right of the sheet, so a point near the top cannot be clicked. The drawing view should pan to keep the pointer's area clear, and the options bar should never wrap onto the sheet.
- **A class named `.fl` and an id named `hdr` clashed with the shell's.** Prefix an app's classes and ids, and have the brand lint for a duplicate.
- **Option inputs must commit as they are typed,** not on blur, or a click on the Map arrives before the name does.
- **The generated "cave" polygons are chunky** at a coarse grid; the real tool needs smoothing and a minimum area as options.
- **A raster is the open question for heights.** Height lines are data the Map holds; a painted heightmap is not.

### Screens

In `screens/`, 31 images: the gallery, a date, Locations, a Location as a reader (01 to 05); the Map, its panel, measuring, the legend, settings, a globe (06 to 11); the drawing view, a line, a spline, a height line, a cave preview and applied, wave function collapse, the planned brush, the command line, the tool search, history, the flyout and a selected Area (12 to 24); dark (25, 26); 834 (27); 430 (28 to 31).

## Open questions

1. A drawing view's keys: should the single letters (V P C L S F A G T H) be remappable in a shortcuts dialog from the start?
2. A generator's preview shows over the region only. Should it also offer a split (before and after), or a ghost over the whole sheet?
3. When an Area is applied from a generator, should it keep a record of its tool and seed (so "Roll again" can regenerate until the person edits it), or become ordinary geometry at once as now?
4. The tool list will grow. Is the five-group header (Select, Place, Draw, Terrain, Generate) right, or should Generate be its own panel?
