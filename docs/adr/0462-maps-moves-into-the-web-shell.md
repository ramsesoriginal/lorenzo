# 0462 - Maps moves into the web shell

Status: accepted, being built as a stack of pull requests (M0 to M6, from 2026-11-12). Slice UI-E of [RFC 0050](../rfcs/0050-the-web-interface.md) for Maps. The design is [docs/design/web/maps](../design/web/maps/README.md) (MP1 to MP7) and the decision is [ADR 0421](0421-maps-redesign.md); this ADR says how the app is moved to it, in what order, and where it differs from the design on purpose. Follows [ADR 0440](0440-calendars-moves-into-the-web-shell.md) and [ADR 0441](0441-sessions-moves-into-the-web-shell.md), which did the same for Calendars and Sessions.

## Context

Maps still draws its own header and a plain `wrap`. The design puts it in the web shell, with a gallery of Maps as its Home, Locations as a tab, a Map that fills the page under floating controls with a panel that slides over, a phone that reads everything, and a drawing view built as a toolbox over a registry of tools.

## Decision

- **The frame is the web shell** (`AppPage shell="web"`). The tabs are Maps (the gallery, and a Map's page) and Locations (and a Location's page). The Map's page uses the `workspace` template and the others `list-detail`. The palette, the apps sheet and the status bar are the shell's, and the account menu holds Appearance.
- **A stack of ten pull requests, each on the one before and each tested and green:** M0 this frame, M1 the gallery, M2 Locations, M3 the Map's read side, M4 phone and tablet, M5a the toolbox, the options bar and the tool registry, M5b the outliner, dragging onto the Map and the sidebar with History, M5c the command line, M5d remappable keys and the Shortcuts dialog, and M6 the audit.
- **A gallery card's small drawing is drawn in the browser, lazily.** The renderer paints a Map to SVG from its placements, and the Map's page already reads them. Cards are filled as they come into view, a few at a time, from what this reader may see, so nothing hidden can be in a drawing (D24). A stored preview made on save is not built: one stored image cannot be right for every reader, so it would need a rule for what the whole library may see and a table of its own, and it is worth that only if this proves too slow in a large library.
- **The drawing view owns single-key shortcuts while it has focus,** and says so in the Shortcuts dialog. The shell's chord key (G) is refused for a tool, and a person who has turned single-key shortcuts off keeps them off.
- **Planned tools are drawn as entries of the registry and do nothing.** Spline, Freehand, Height line, Height brush, Cave system, Fill by marching squares and Fill by wave function collapse appear as "planned" with the reason, and are built later, each with its own ADR (ADR 0421). They are tracked in an issue.
- **What does not change:** the map renderer, the API, and what a refusal says.

## Checked against the design

Filled in as each slice lands.

| Part | Slice | State |
| --- | --- | --- |
| The frame, tabs, palette, status bar | M0 | done |
| The gallery of Maps, its cards and the date lens | M1 | done: a card draws the Map small (up to 300 placements this reader may read, a few cards at a time, as the card comes into view), says what it is drawn on and how it is tied to a date (or "Not open to the library" for a writer), and "Any date" opens the date lens; with one library the app begins at its gallery; "Make a Map" opens its form. Where it differs from the design: the search box stays, because finding a Map by name is not to be lost. |
| Locations and a Location's page | M2 | done: the page has Any date and Add a Location as its own actions, a row says the dates it is tied to and, for a writer, whether it is open or closed (read as the row comes into view), and a Location says where it sits as links ("in A, within B"), with its parts and its connections as cards side by side. Not drawn, because the API does not give them: "1 Map" on a row, "On these Maps" and "Where is…" (#1214). |
| The Map: floating controls and the slide-over panel | M3 | done: the Map fills the page (the `workspace` template) under a card that names it and says what it is drawn on, with Places beside it; Layers, Look, Legend (and Projection on a sphere) are floating controls that open one small panel at a time, and the zoom floats at the foot. A panel slides over from the side with the tabs Selected, Places and, for a writer, Settings (Pictures in it), and it stays on the tab it was on when the page is drawn again; choosing a place opens it on Selected unless the tools are on, and starting to draw puts it away so the Map is clear. Distance is in the Places tab. What a writer draws with sits in the title card and a dock under it, until the toolbox (M5a). Differences from the design: no "Any date" on a Map (a date lens is for the lists), and the "Measure from here" button is the Distance section, as it was. |
| Phone and tablet | M4 | done: below 720px the panel is a sheet from the foot, the controls sit low, and "Edit this map" does not offer drawing but the small changes of screen 31 (the name, whether the Map is open to the library, and a selected pin's x and y), each the same write the larger window makes. A tablet gets the larger layout. |
| The toolbox, the options bar and the tool registry | M5a | done in part: the tools are one list of declarations (`tools.ts`: name, group, icon, key, input, output, ready or planned with a reason), the toolbox is drawn from it in its groups (Select, Place, Draw) with a key for each, "All tools" finds any of the 13 by name, group or key and lists the planned ones (spline, freehand, height line, height brush, the three generators) with their reasons, and the editor owns the single keys while the drawing has the focus, so the shell's G chord does not take Cells' key, a key typed into a field stays the field's, and a person who has turned single keys off keeps them off. The toolbox is compact for a fine pointer, not the Dense setting of the shell; the options bar is the panel under the toolbox, as it was, and gives way to the sidebar in M5b. |
| The outliner, dragging, the sidebar and History | M5b | done in part: while the tools are on, the Places tab lists the places of the library that are not on this Map yet (found by name, 50 at a time), each with a Place button that puts it at the centre of the view, and each row can be dragged onto the sheet to be put where it is dropped; the History tab lists every step by name ("Placed Harbour", "Moved Old Town"), with a way back to any of them, the undone ones staying listed until something new is done. Not yet: the options bar stays the panel under the toolbox rather than moving into the sidebar, and the outliner lists places only, not other kinds of entries. |
| The command line | M5c | |
| Remappable keys and the Shortcuts dialog | M5d | |
| The audit | M6 | |

## Consequences

- The Maps end-to-end tests that drove the old header and toolbar are moved as each part moves. The accessibility checks leave the shell's status bar out, because that is the shell's own chrome.
- The old `Libraries` tab is gone: choosing a library is the shell's switcher.
