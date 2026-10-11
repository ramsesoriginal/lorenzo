# 0257 - Bench: moving tabs with the keyboard

Status: accepted

## Context

Tabs could be reordered (Alt+←/→), split out (Alt+Shift+arrows) and floated (Alt+F) with the keyboard, but not moved to the group beside, docked back, or even walked through with plain arrows. Nothing said what happened, and the chords were not listed anywhere.

## Decision

- **Arrows, Home and End on a tab** go to the other tabs of its group and choose the one they reach (the ARIA tabs pattern).
- **Ctrl+Alt+arrows** move the tab into the group beside its own on that side (`workspace/neighbour.ts`: among the groups that start where this one ends and share some of its extent, the nearest, then the one that overlaps most). At an edge it says there is no group there.
- **Alt+D** docks a floating tab's window back, as Alt+F floated it.
- **It is said:** float, dock and move announce what happened in a polite live region (`role="status"`, visually hidden).
- **The palette lists the chords** ("Keyboard shortcuts for tabs"). The dialog takes the focus itself, since the key that chose the command is still down and would press a Close button at once.

## Consequences

- A tab in a floating window moves with the pointer, or is docked first; Ctrl+Alt applies to tabs in the workbench only.
