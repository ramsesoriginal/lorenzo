# 0476 - The Cave system generator

Status: accepted, decided with the maintainer on 2026-11-16. Part of [RFC 0050](../rfcs/0050-the-web-interface.md) (slice UI-E, Maps); the first generator of [ADR 0475](0475-the-generator-contract.md), which says what every generator does. Tracked in [#1210](https://github.com/ramsesoriginal/lorenzo/issues/1210).

## Decision

- **The tool.** Cave system (group Generate, key K). It works on the region ADR 0475 names, previews, and on Apply writes one entry's placement. Not on a sphere.
- **Its output is areas:** one `polygon` part for each cave, its outline and, as holes, the pillars of rock that stand in it. Nothing says "cave" in the data: the role is the person's to choose and starts at none, and the entry is theirs to name.
- **The algorithm**, each step a pure function of what came before:
  1. A field of square cells is laid over the box around the region, **Size** cells across. A cell whose middle lies outside the region, and every cell at the edge of the field, is rock.
  2. Every other cell is rock with the chance **Density**, drawn in order from the seed.
  3. **Passes** times, every cell becomes rock when five or more of the nine cells around and under it are rock, and open otherwise (a cellular automaton).
  4. An open pocket of fewer than **Smallest cave** cells is filled with rock, and a pillar of fewer cells than that is opened.
  5. The field is softened once (each cell the mean of its nine), so that an outline is not a staircase, and the outlines are traced at the half-way level by marching squares, a crossing placed along a cell edge by where the level falls. An ambiguous square is decided by the mean of its four corners.
  6. A pillar belongs to the smallest cave that holds it. Coordinates are kept to two decimals; a point equal to the one before it is dropped, and a ring of fewer than three points with it.
- **Its options**, with ADR 0475's Seed and Role: **Size** (the cells across, 16 to 96, 48 at first), **Density** (0.30 to 0.60, 0.46 at first), **Passes** (0 to 8, 4 at first) and **Smallest cave** (1 to 60 cells, 6 at first). The first values of the first three are the prototype's.
- **When a result does not fit** a placement (2,000 points, 256 parts), the preview says so and what to change: a smaller Size or more Passes for points, a larger Smallest cave for parts. Nothing is made coarser unasked.
- **The history step** is "Drew a cave system, seed 4821: 6 caves in the whole sheet".
- **The pure parts** are `cave.ts` and `marching-squares.ts` in `apps/maps/src/lib`; marching squares is written to be used again by the fill generator. Golden vectors are in `packages/map-engine/golden/caves.json`: the TypeScript tests reproduce each output, and the Python tests pass each through the validator.

## Validation and delivery

Unit tests: the golden vectors; the same seed and options twice; another seed differs; a region that is an area or a circle keeps every cave inside it; every result passes the mirrored validator across many seeds; Smallest cave and Passes do what they say; a result over a limit is refused with its sentence. Browser tests against the real API: the preview, a rolled and a typed seed, Compare, Discard writing nothing, Apply writing one placement the API accepts with its history step, undo; axe in light and dark with the preview on.

## Excluded

Tunnels joining the caves, several levels, cave entrances, a painted texture, and any role or tag chosen for the person.
