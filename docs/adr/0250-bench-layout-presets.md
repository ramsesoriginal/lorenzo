# 0250 - Bench: layout presets

Status: accepted

## Context

The top bar of the design has **Write / Inspect / Compare** ([screens](../design/bench/README.md)). In the prototype they are not modes of the editor: each button rearranges the docked panes. The prototype's `buildTree` is the reference.

## Decision

- **Write** is the entry alone. **Inspect** is the Explorer, the Entry, and the Stats and Links panes side by side. **Compare** is the Explorer on the left; the Entry and the Stats/Links on top; the Table and the Ancestry graph along the bottom.
- **Panes in floating windows stay floating,** and **any other docked pane stays with the entry** (the compare grid, and the formula and pictures panes that come later). A preset places only the panes it knows (Explorer, Entry, Stats, Links, Table, Ancestry).
- **Which one is pressed is worked out, not stored.** `activePreset` compares the shape of the layout (which panes sit in which group, nested by direction; not the sizes or the active tab) with what each preset would make from it. Move a pane by hand and none is pressed; put the shape back and it is again. The default layout is Inspect.
- **Pure functions** in `workspace/presets.ts`, like the rest of the workspace model, tested without a DOM: each preset's arrangement, floats left alone, applying a preset twice changing nothing, and the shape check.
- **Where:** a switch in the title bar, and palette commands "Layout: Write / Inspect / Compare". Choosing one saves the layout like any change.

## Not in scope

Remembering a person's own arrangements as named layouts.

## Consequences

- A preset can close a pane it does not know where to put: the Table or the Ancestry graph when Inspect is chosen. Open them again from the palette.
