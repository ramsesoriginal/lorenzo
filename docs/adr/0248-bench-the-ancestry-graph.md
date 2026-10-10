# 0248 - Bench: the ancestry graph

Status: accepted

## Context

Slice B10 of [RFC 0039](../rfcs/0039-bench-authoring-offline-and-extensibility.md) and a pane of the design ([01](../design/bench/screens/01-workbench.jpg), [05](../design/bench/screens/05-stats.jpg)): where an entry sits among what it inherits from.

## Decision

- **A pane, "Ancestry",** drawn as SVG: the selected entry highlighted, what it inherits from above it (up to four rows), what inherits from it below it, and its relatives so it is seen among its kind: its siblings, and the other children of what it inherits from. An arrow goes from each entry to what it inherits from. Opened from the palette ("Open Ancestry"), and it follows the selected entry like the other panes.
- **The layout is plain data** (`shell/ancestryLayout.ts`) and tested without a DOM: rows by how far up an entry is (the farthest way, so one that inherits from entries at different heights sits below all of them), a row of at most six, the entry's own children that do not fit counted and said ("3 more under this entry"), nodes that never overlap and stay inside the width, loops stopped.
- **An entry opens when it is clicked,** or when it has the focus and Enter or Space is pressed. Each is a button to a screen reader ("Open Sword", "Undead (this entry)").
- **It draws from the list Bench already has** (names and parents): no reads, no API.

## Not in scope

Labels with a stat on each entry (the design shows "1.5 kg"); they need every entry's stats and come with the compare grid's reads. Dragging an entry to change its parent.

## Consequences

- A repository where one entry has hundreds of children shows six and says how many more; the Parents and children pane lists them all.
