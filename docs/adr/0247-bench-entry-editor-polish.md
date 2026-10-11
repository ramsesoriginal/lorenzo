# 0247 - Bench: entry editor polish, and decimal stats

Status: accepted

## Context

The first of twelve slices that bring Bench to the design agreed on the prototype ([docs/design/bench](../design/bench/README.md), [RFC 0042](../rfcs/0042-bench-workbench-interface.md)). Four small things the screens show and Bench did not.

## Decision

- **A breadcrumb over the entry's name:** what it inherits from, farthest first, each a button that opens that entry. With several parents it follows the first (the explorer's order); the rest are in the Parents pane. It is pure data (`shell/ancestors.ts`), which the ancestry graph of the next slice reuses.
- **A count on the Links tab:** how many parents and children the selected entry has.
- **Pictures in the `![[` picker:** a small picture of each entry offered, as it arrives. They are read without drawing the page again, since a redraw would take the list away.
- **Decimal stats can be edited.** [ADR 0227](0227-bench-stat-values-and-tags.md) left them out because the API wants `3.0` for a float and the browser writes `3`. The body of a decimal write is now written by hand (`{"value":3.0,...}`, point kept). Typing takes a point or a comma, and nothing else (no exponent); a typo is put back as it was. Decimal stats appear in "Add a stat" and in the compare grid and the stat chips that follow.

## Not in scope

"Worked out by formula" in the stats pane: it needs the formula reads of the formula editor slice and comes with it.

## Consequences

- `canEditStat` is now true for every type; it stays as the one place that says so, in case a type is added the API cannot take.
