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
| The gallery of Maps, its cards and the date lens | M1 | |
| Locations and a Location's page | M2 | |
| The Map: floating controls and the slide-over panel | M3 | |
| Phone and tablet | M4 | |
| The toolbox, the options bar and the tool registry | M5a | |
| The outliner, dragging, the sidebar and History | M5b | |
| The command line | M5c | |
| Remappable keys and the Shortcuts dialog | M5d | |
| The audit | M6 | |

## Consequences

- The Maps end-to-end tests that drove the old header and toolbar are moved as each part moves. The accessibility checks leave the shell's status bar out, because that is the shell's own chrome.
- The old `Libraries` tab is gone: choosing a library is the shell's switcher.
