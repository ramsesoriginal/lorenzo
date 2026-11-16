# 0477 - The Fill by marching squares generator

Status: accepted, decided with the maintainer on 2026-11-16. Part of [RFC 0050](../rfcs/0050-the-web-interface.md) (slice UI-E, Maps); the second generator of [ADR 0475](0475-the-generator-contract.md), on the tracer of [ADR 0476](0476-the-cave-system-generator.md). Tracked in [#1210](https://github.com/ramsesoriginal/lorenzo/issues/1210).

## Decision

- **The tool.** Fill by marching squares (group Generate, key M). It works on the region ADR 0475 names, previews, and on Apply writes one entry's placement. Not on a sphere.
- **Its output is areas and, when asked for, height lines,** all parts of the one placement: a `polygon` part for each area with its holes, and a `polyline` part that carries a `value` and a `unit` for each height line, closed by ending where it began. What the areas are (a wood, a lake, high ground) is the person's to say with the role and the entry's name.
- **The algorithm:**
  1. A field of 64 cells across is laid over the box around the region. A cell at the edge of the field, outside the region, or beside one that is, holds 0.
  2. Every other cell holds smooth noise from the seed, between 0 and 1: random values on a coarser lattice, **Scale** cells of it across, joined smoothly, and half as much again of the same at twice the fineness.
  3. The areas are where the field is above **Level**, traced by marching squares as the caves are. An area smaller than **Smallest area** cells is left out, and so is a hole smaller than that.
  4. With **Height lines** above 0, that many more levels are traced, evenly between Level and the top of the field, each a height line inside the areas. The first carries **First height**, each next one **Step** more, all in **Unit**.
- **Its options**, with ADR 0475's Seed and Role: **Scale** (2 to 20, 8 at first), **Level** (0.20 to 0.80, 0.50 at first), **Smallest area** (1 to 60 cells, 4 at first), **Height lines** (0 to 8, 0 at first), **First height**, **Step** and **Unit**. The last three have no first value: a height and its unit are never invented ([ADR 0473](0473-the-height-line-tool.md)). With Height lines above 0 the preview says they are needed, and Apply is off until they are given.
- **When a result does not fit** a placement, the preview says what to change: fewer Height lines or a larger Scale for points, a larger Smallest area for parts.
- **The history step** is "Drew a fill, seed 4821: 3 areas and 6 height lines in the whole sheet".
- **The pure parts** are `fill.ts` and, shared with the caves, `field.ts` (a field over a region) in `apps/maps/src/lib`. Golden vectors are in `packages/map-engine/golden/fills.json`, read by both languages as the caves' are.

## Validation and delivery

Unit tests: the golden vectors; the same seed and options twice; another seed differs; areas and lines inside the region; every result passes the mirrored validator across many seeds; Level, Scale and Smallest area do what they say; height lines carry their values and close; a result over a limit, and height lines without their heights, are refused with their sentences. Browser tests against the real API: the preview, height lines asked for without and with their heights, Apply writing exactly what the function gives, the values on the Map, undo; axe in light and dark with the preview on.

## Excluded

A field painted by hand or read from a picture, a fill of cells on a grid (the wave function collapse generator), shading by height, and several kinds of area from one run.
