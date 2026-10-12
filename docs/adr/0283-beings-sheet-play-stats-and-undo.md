# 0283 - The being sheet in play: stat tiles, steppers, undo and where a number comes from

Status: accepted, decided with the maintainer on 2026-10-12. Slice U2 of [RFC 0043](../rfcs/0043-the-being-sheet.md); builds on [ADR 0276](0276-where-a-stat-value-comes-from.md) to [0279](0279-stat-hints.md) and [0282](0282-beings-sheet-shell-modes-and-sections.md). The design is [docs/design/beings](../design/beings/README.md); where this and the prototype disagree, the prototype wins.

## Context

At a table what people do with a being is small: take away seven hit points, switch a condition on, glance at three numbers. The shell ([ADR 0282](0282-beings-sheet-shell-modes-and-sections.md)) drew the stats; this slice makes them usable.

## Decision

- **The vocabulary decides how a stat is drawn.** The app reads the library's groups and definitions ([ADR 0281](0281-sheet-settings-and-the-sheet-read.md): readable by every participant) in the library's own order (`statVocabulary` in `packages/stat-values`; `statDefinitions`, for pickers, stays alphabetical). A number is a tile with its unit and, when the definition says so, its sign; text and enums are rows; tags are chips in the header.
- **Hints are read on the being.** A maximum hint gives "of 9", a resolved hint gives its value beside the number ("+3", signed when that definition is), a minimum hint gives the floor of a stepper. A hint to a stat the being has no value for shows nothing and stops nothing ([ADR 0279](0279-stat-hints.md)).
- **Where a value comes from.** A calculated tile opens a panel (a native `<details>`, nothing hover-only) that asks `GET .../stats/{id}/explanation` ([ADR 0276](0276-where-a-stat-value-comes-from.md)) and says the formula and what it read, with the total. An inherited tile says "From Dwarf". Solid is set on the being, dashed is inherited or calculated.
- **Pinned numbers** (`pin` on the definition) are what the sticky bar keeps in view; with none pinned, the first three numbers of the first group.
- **Play changes what the library calls `adjustable_in_play`**, and only for someone who may write: a number gets a stepper (−, +) and an adjuster that takes away, adds or sets an amount, never below its floor when it has one (and nowhere when it does not); a tag gets a toggle (`adjustable_in_play` governs tags in Play too). A calculated number cannot be changed. Changing an inherited number gives the being a value of its own, and undoing it removes that value again.
- **Each change in Play says what it did and can be undone:** "Hit points 31 → 24" in the undo bar and, through the one live region, to a screen reader; the changed tile is highlighted and shows the amount for a moment; **Undo** by button or Ctrl or Cmd+Z, up to 30 steps. A write that finds the value changed since it was read reads it again and says so ([ADR 0263](0263-inventory-web-editing-stat-values.md)).
- **Edit makes every value a field** in its tile, saved as you go, with **Use inherited** where the being holds the value itself. This replaces the separate stat forms. Edits are not undoable (design brief, open question 6).
- **A viewer who cannot read the vocabulary** (none now, for a participant) would see the stats the being has, ungrouped, and no controls.

## Not in scope

Pairs drawn as one tile, dots and clocks (entity templates); undo for notes and tags in Edit; changing text or enum values in Play.

## Consequences

Playing a being takes no more than a tap or two per change, and every change is a normal write the API checks. The stat forms of [ADR 0272](0272-beings-editing-stats-and-handing-over.md) are gone from the page; its three-state tag editor stays in Edit.
