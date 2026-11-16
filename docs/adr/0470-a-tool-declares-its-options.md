# 0470 - A tool declares its options

Status: accepted, decided with the maintainer on 2026-11-16. Part of [RFC 0050](../rfcs/0050-the-web-interface.md) (slice UI-E, Maps); follows [ADR 0421](0421-maps-redesign.md) and [ADR 0465](0465-maps-moves-into-the-web-shell.md), which ask for an ADR per planned tool. Tracked in [#1210](https://github.com/ramsesoriginal/lorenzo/issues/1210).

## Context

The design says a tool is a declaration that also names its options (MP6), and that the options bar, the command line and the palette are drawn from it. The registry (`apps/maps/src/lib/tools.ts`) has no options, and the one option the editor has, *Snap to the grid*, is a checkbox the toolbar draws by hand. Every planned tool has options, so this comes first.

## Decision

- **A tool lists its options.** An option has an id, a name in words, one word the command line calls it by, a type and a first value. The types are `toggle`, `number` (with a least, a most and a step), `text` (with a longest length), `choice` (a closed list) and `seed` ([ADR 0475](0475-the-generator-contract.md)). A type is built with the first tool that has one; this slice builds `toggle`, and `number` comes with the Spline tool ([ADR 0471](0471-the-spline-tool.md)). A number is kept to a whole count of its steps.
- **The Options tab draws them,** under the tool's name, each a named field that takes effect as it is typed, never on leaving it. A tool with no option shows none.
- **The command line sets them:** the option's word, then the value (`SNAP OFF`, later `TENSION 0.4`, `SEED 4821`). A toggle takes `ON` and `OFF`. A value out of range is refused with the range, and a name the tool on does not have is refused with the names it has. The reading is pure (`command-line.ts`).
- **Values live in the page's memory,** one per tool and option, and are gone when the page is left, unless the tool's own ADR says a value is remembered. An option marked shared has one value for every tool that lists it.
- **An option may need a grid,** as a tool may: on a Map without one it is neither drawn nor accepted.
- **The first option is *Snap to the grid*** ([ADR 0356](0356-authoring-on-a-grid.md)): shared, needing a grid, on at first, listed by Select, Pin, Circle, Line, Area and Cells. It moves from the toolbar to the Options tab and gains its command, `SNAP ON` and `SNAP OFF`. What snapping does is unchanged.

## Consequences

- A built tool is an entry that becomes ready, its options and its behaviour; no tool draws its own options.
- The toolbar loses the snap checkbox.

## Validation and delivery

Unit tests for the pure parts: the options of a tool on a Map with and without a grid, the first values, a shared value, and the reading of an option line (set, refused value, unknown name). Browser tests: the grid tests set snapping in the Options tab and from the command line.

## Excluded

Remembering option values between visits, options a person adds, and any option of a planned tool before its own ADR.
