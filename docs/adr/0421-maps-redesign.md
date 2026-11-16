# 0421 - Lorenzo Maps, redesigned

Status: accepted, decided with the maintainer on 2026-11-05. Part of [RFC 0050](../rfcs/0050-the-web-interface.md). The design is [docs/design/web/maps](../design/web/maps/README.md), MP1 to MP7. Follows [RFC 0048](../rfcs/0048-locations-maps-connections-and-optional-dates.md); the drawing of a Map belongs to the renderer package and is not designed here.

## Context

Maps has a gallery, a read view and a drawing view with a growing set of tools, and the maintainer asked for conventions that people who draw all day will know, and room for tools that do not exist yet.

## Decision

- **The app begins at a gallery of Maps** (MP1), each a card with a small drawing, its coordinate system and its date tie; "Make a Map" first; Locations is a tab.
- **A phone reads everything and writes on a larger window** (MP2): reading, panning, zooming and the panel as a sheet work; drawing says it needs a larger window and offers rename, moving a pin by its numbers and changing who sees a Map.
- **The Map fills the page** (MP3), with small floating controls and a panel that slides over for the selected mark, the places list and settings.
- **Drawing is a toolbox** (MP4, MP6): a header of tools by group over the Map, an options bar that changes with the tool, an outliner of the places, a sidebar of Item, Tool and View tabs, Layers, History as the undo surface, and a command line under the Map that takes typed coordinates and commands. Snapping, navigation that does not leave the tool, and drag from the outliner onto the Map, with a right-click menu twin and a keyboard path for each gesture. The drawing view is Dense (D22).
- **A tool is a declaration, not a layout** (MP6): name, group, icon, key, input, options, output, preview and the data it needs. The toolbox, the options bar, the command line, the palette and the key map are drawn from it. A generator previews, then applies as one history step with its seed in the name, and what it makes is data the Map already holds; a heightmap is a raster, which the Map does not hold, so that tool is drawn and marked **planned**.
- **Tool keys are remappable** (MP7), a Compare switch splits a generator's preview from the Map, and an applied generator becomes ordinary geometry at once.
- **A date lens** uses the shared time filter (CS2).

## Consequences

- The tool registry is the contract for the real app: a new tool is an ADR naming the tool, its output and its data.
- A hidden level of the Locations tree leaves no trace; a Location is shown under its nearest visible ancestor.
