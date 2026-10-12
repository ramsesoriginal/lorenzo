# 0275 - Bench: icons used throughout, an appearance popover, and a focused Write layout

Status: accepted, decided with the maintainer on 2026-10-12.

Builds on [ADR 0274](0274-the-atlas-grows-for-bench-kinds-and-states.md) (the atlas) and [ADR 0250](0250-bench-layout-presets.md) (layout presets).

## Decision

- **Icons where they reinforce state or kind** (identity §17): panes in tabs, the dock and layout buttons, status chips and the status bar, kinds on parents, links and picker rows, palette commands, and icon buttons instead of text stand-ins. Words still say the thing; the icon only helps.
- **Appearance popover**: the "Aa" button in the top bar opens a dialog with Theme (System / Light / Dark) and Writing font (as in the design prototype). Both are remembered on the device; System follows `prefers-color-scheme` live. The palette has the same choices.
- **Write is a focus layout**: while the active preset is Write (and only then) the entry pane hides its meta area, breadcrumb, "Inherits from" and "Notes". Conflict and attention rows stay visible. The shell exposes the preset as `data-layout` on its root and the rule is plain CSS.

## Consequences

Nothing is lost in Write: switching back to Inspect shows everything unchanged.
