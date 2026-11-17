# 0482 - Splitting a drawing into entries

Status: accepted, decided with the maintainer on 2026-11-17. Builds on the parts editor of [ADR 0474](0474-editing-the-parts-of-a-placement.md). Part of [RFC 0050](../rfcs/0050-the-web-interface.md) (slice UI-E, Maps). Tracked in [#1267](https://github.com/ramsesoriginal/lorenzo/issues/1267).

## Context

A generator writes everything it draws as parts of one entry's placement ([ADR 0475](0475-the-generator-contract.md)), and a drawing of several parts can be made by hand too. A worldbuilder wants the fields of a fill, or the states of a continent, as places of their own, each with its name and its information.

## Decision

- **Split into entries** is an action of the parts list, for a drawing of two or more parts whose entry is a Location. It asks for a base name, the entry's name at first.
- **Each part becomes a new Location**, named from the base and numbered in drawing order ("Field 1", "Field 2", …), visible to whoever can see the original (it is public when the original is), and made a part of the original in the Location tree, so the original is their parent.
- **Each new Location is placed on this Map** with its part, a height line keeping its height, and with the original's role, line and drawing order. **The original's drawing is taken off this Map;** the original stays, as the parent of the new ones.
- **At most 100 parts** are split at once, the writes of one batch ([ADR 0351](0351-writing-placements-in-bulk.md)); a larger drawing is refused, naming the limit, before anything is made.
- **One history step**, "Split Fields into 6 entries", writes the placements as one batch. Undo puts the original's drawing back and takes the new ones off this Map; the new Locations stay in the library, as a Location made from the chooser does.
- The Locations are made one by one before the batch. If one cannot be made, nothing is placed, the panel names how many were made, and they stay in the library.

## Built

- Whether the original is open to the whole library is read when splitting; when the person splitting is not told, the new places are restricted.
- The action sits under the parts list with a short sentence of what it does; the base name is the entry's name at first.
- After the split nothing is selected, as the drawing that was selected is gone from the Map.

## Validation and delivery

Unit tests: the names and order, the parts as placements with the original's role, line and order, heights kept, the 100 limit. Browser tests against the real API: a fill of several areas split into Locations under the original, each on the Map, the original's drawing gone, undo and redo; a split refused over 100 parts; axe in light and dark with the action shown.

## Excluded

Merging entries into one drawing, splitting a part's holes off, splitting the drawing of an entry that is not a Location, and splitting on another Map than the one being edited.
