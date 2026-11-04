# 0392 - Bench: the second icon pass

Status: accepted, decided with the maintainer on 2026-11-04.

Builds on [ADR 0275](0275-bench-appearance-popover-and-a-focused-write-layout.md) and [ADR 0391](0391-the-icon-atlas-grows-to-every-ui.md) (the atlas now has an icon for every concept).

## Decision

- **Text stand-ins become icons** where they stood for an action or a mark: `×` on formula rows, `−`/`+` on stat chips, `ƒ` on stats with a formula, `⋯` on picture actions, `…` on a picture still loading, `+` for adding a picture. Left as text: the `×` between a count and an item in a pack (it is multiplication) and the arithmetic in formula text.
- **The toolbar over a text** is one shared component (`shell/textToolbar.ts`) for the entry's description and notes: Bold, Italic, Heading, Quote, Bulleted and Numbered list, Code (the actions of `@lorenzo/lorenzoscript-editor`, now a Bench dependency) and the two that start a link or a picture. Every button is an icon, named for readers and in its tooltip.
- **Honest state:** the status bar tells a conflict, something needing attention and a change waiting apart (`conflict`, `error`, `waiting`); sign in and out carry `login`/`logout`; _Aa_ is the `appearance` icon and its Theme choices `theme-system/light/dark`.
- Words stay beside every state and action that is not a plain tool button (identity §17.8).

## Consequences

The toolbar is no longer two text buttons, so tests find its buttons by their accessible names.
