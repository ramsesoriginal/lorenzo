# 0475 - The generator contract

Status: accepted, decided with the maintainer on 2026-11-16. Part of [RFC 0050](../rfcs/0050-the-web-interface.md) (slice UI-E, Maps); follows [ADR 0421](0421-maps-redesign.md) and [ADR 0465](0465-maps-moves-into-the-web-shell.md), which ask for an ADR per planned tool. Tracked in [#1210](https://github.com/ramsesoriginal/lorenzo/issues/1210).

## Context

Four planned tools make more than a person draws by hand: Cave system, Fill by marching squares, Fill by wave function collapse and Height brush. Each gets its own ADR for its algorithm, options and output. This one decides what they share.

## Decision

- **A generator is a pure function** of its region, its options, its seed and, where its ADR says, placements read from a Map. The same input gives the same output, digit for digit, in every browser: no `Math.random`, no clock, and only whole-number hashing, the four operations and square roots. Its random numbers come from the renderer's seeded source.
- **The seed** is a whole number from 0 to 999,999, an option of type `seed` ([ADR 0470](0470-a-tool-declares-its-options.md)). Its first value is drawn by the page from the browser's `crypto`, outside the function; a person can type any seed; **Roll** takes the next number.
- **The region** is the selected placement when it is one area without holes or one circle, and otherwise the whole sheet; a tool for a grid works on the cells of that region. What is already drawn there is ignored.
- **The preview** is drawn as an overlay and never stored. It is worked out again when an option changes. **Compare** splits the drawing at a divider, the preview on one side and the Map as it is on the other; the divider is dragged, and is a slider for the keyboard. The renderer gains a filled area in its overlay and a clip for it, and still knows nothing of editing.
- **The output** belongs to one entry, chosen or made as for any drawing tool, as one placement with a part for each piece; a tool whose ADR says so writes a few placements, one for each entry it draws. **Role** is an option of each generator and starts at none. An applied generator keeps no tool and no seed: it is ordinary geometry at once.
- **Apply** recomputes from the Map as it is, writes one batch of at most 100 operations ([ADR 0351](0351-writing-placements-in-bulk.md)) and records one history step whose name carries the tool, the seed and a count ("Drew a cave system, seed 4821: 6 caves in the whole sheet"). Undo is one batch back. **Discard** writes nothing. A Location made for the output stays if the write is refused, as [ADR 0353](0353-authoring-a-map-in-lorenzo-maps.md) says.
- **A result always passes the validator, or is not offered.** The page checks a result against the limits of [ADR 0337](0337-geometry-roles-and-the-validator.md) and for simple polygons before Apply. A result that does not fit is refused in the preview, naming the limit and the option to change, and Apply is off. Nothing is made coarser without being asked, and no limit is raised here.
- **The check is the TypeScript mirror ADR 0337 foresaw,** for limits and simple polygons only, in `apps/maps/src/lib`, tested against `packages/map-engine/golden/geometry.json`. The API's validator stays the one that decides.
- **Golden vectors.** Each generator has inputs and outputs in `packages/map-engine/golden`; the TypeScript tests reproduce the outputs and the Python tests pass each through the validator.
- **Code.** The algorithms are written here, in `apps/maps/src/lib`, with no library; they move to a package when a second app needs them ([ADR 0098](0098-branding-css-app-and-package.md) and the package guide).
- **Where.** Not on a sphere, and not below the width that offers drawing. A reader without writing standing sees none of it.
- **The command line** takes `SEED n`, `ROLL`, `APPLY`, `DISCARD`, `COMPARE ON` and `COMPARE OFF`, and each option by its name.

## Consequences

- The four generators are decided one by one: Cave system, Fill by marching squares, Fill by wave function collapse (its rules learned from cells already drawn, on this Map or another), and Height brush (a field the page builds from an entry's height lines and never stores).
- Stored heights, a raster of any kind, and small Maps used as tiles are not decided here.

## Built

The shared pieces are built first, with no tool; the editor's preview, Apply and Discard come with the first generator.

- **The mirror is the whole validator,** not only limits and simple polygons: the golden corpus asks every implementation to agree on each of its documents, and it does, on all of them (`apps/maps/src/lib/validate.ts`). Its limits are read against the engine's own file in a test. The turn of three points is worked out in whole numbers of any size, as the engine does. One difference is known: the size in bytes is measured on this side's JSON, which may write a number a character longer or shorter than the API's at the very edge of the limit.
- **The renderer** has a filled `area` in its overlay and `setOverlayDivide(fraction)`: shapes marked `clipped` are drawn to the right of the divider only, through one clip path, and the divider is a line. The divider's slider is the app's.
- **The seed** is an option type with no first value. The page draws it from `crypto` when the option is first shown; **Roll** takes the next number and 0 after 999,999.
- **A result over a limit** is refused with a sentence that names the limit and, from the tool, what to change (`fits` in `generator.ts`).
- **The commands** `ROLL`, `APPLY`, `DISCARD`, `COMPARE ON` and `COMPARE OFF` are read; with no generator as the tool they answer that.

## Validation and delivery

Unit tests: the seed's range and Roll; the region of a selection; the mirror against the golden corpus; a result over each limit refused with its reason; the history step's name. Renderer tests: the filled overlay and the clip. Browser tests come with the first generator.

## Excluded

Animation, a preview worked out on a server, generators that run without a person, and any change to the limits.
