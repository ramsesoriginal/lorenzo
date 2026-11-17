# 0490 - Mirror, turn and copy a drawing

Status: accepted, decided with the maintainer on 2026-11-17. Part of [RFC 0050](../rfcs/0050-the-web-interface.md) (slice UI-E, Maps). Tracked in [#1267](https://github.com/ramsesoriginal/lorenzo/issues/1267).

## Context

A tournament table is laid out so both sides meet the same ground: what stands in one half stands, turned or mirrored, in the other. Drawing it twice by hand never quite matches. A Map holds one drawing for an entry, so a second copy of a piece of terrain is a second entry.

## Decision

- **Mirror across** reflects the selected drawing about the sheet's middle from top to bottom, so left becomes right; **Mirror down** about its middle from side to side, so top becomes bottom; **Turn 180°** turns it about the sheet's middle, both at once. Each changes the drawing in place, as one history step ("Mirrored Ruin across", "Turned Ruin 180°"). Every shape is moved point by point, a circle by its middle, and what a part carries, a height and its unit, is kept.
- **Copy to…** puts the selected drawing, as it is or mirrored or turned (one choice), on another entry: one found by name that is not on this Map yet, or a new Location, open to the library as the Map is. It keeps the original's role, line and drawing order, and is one history step ("Copied Ruin to Ruin (east), turned 180°"). An entry already drawn here is refused, by name: a Map holds one drawing for an entry.
- **A drawing of cells** ([ADR 0481](0481-cells-as-merged-outlines-and-larger-drawings.md)) stays cells when it lands on whole cells: on squares and rectangles over a sheet a whole number of cells across. Where it would not, on hexes, whose rows are offset, or on a sheet that is not a whole number of cells across, the action is refused and says why; nothing changes.
- **Where:** in the Selected panel, for any drawing, on a Map that is not a sphere; and on the command line, `MIRROR ACROSS`, `MIRROR DOWN`, `TURN` for the selected drawing, and `COPY TO name`, `COPY ACROSS TO name`, `COPY DOWN TO name`, `COPY TURNED TO name`, where a name no entry has makes a new Location.
- **The pure parts** are in `apps/maps/src/lib`: the three transforms of a geometry about a sheet, and whether a drawing of cells lands on cells.

## Built

- **Whether cells land is worked out, not foreseen.** The moved drawing is read as cells again ([ADR 0481](0481-cells-as-merged-outlines-and-larger-drawings.md)); where it is not, the action is refused as "Mirrored down, its cells would not land on whole cells of this grid. Nothing was changed." On pointed-top hexes a mirror across can land where the sheet allows it, while a mirror down or a half turn meets the offset rows; on flat-topped hexes the other way round.
- **A command typed while a change is being written waits for it** and is then carried out; before, the Map dropped it unsaid. This holds for every command, not only these.
- The controls are in the Options tab of the Map panel, under the selected drawing's own, as "Mirror and copy".

## Validation and delivery

Unit tests: each transform of every shape, twice is the original, values kept; cells that land and cells that do not, on each kind of grid; the commands and their refusals. Browser tests against the real API: a drawing mirrored and turned in place, undone; copied turned to a new Location and to a found entry, with the original's role and order; an entry already here refused; cells on hexes refused; axe in light and dark with the controls shown.

## Excluded

Turning by other angles, mirroring about another line than the sheet's middle, copying to another Map, and a drawing mode that copies as it draws.
