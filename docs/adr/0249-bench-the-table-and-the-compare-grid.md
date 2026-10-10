# 0249 - Bench: the Table pane and the compare grid

Status: accepted

## Context

Slice B6 of [RFC 0039](../rfcs/0039-bench-authoring-offline-and-extensibility.md) and screens [03](../design/bench/screens/03-compare-grid.jpg) and [05](../design/bench/screens/05-stats.jpg): entries as rows, stats as columns, edited in place, own values told from inherited ones. The bulk read of effective stats (RFC 0041 K7) is not built.

## Decision

- **Two panes over one grid.** "Table" is the small one for the corner of the workbench: Name, Inherits from, and the first three numeric stats, with "Edit any cell; every view follows." and "Open as grid". "Compare" is the whole of it: a filter, "By inheritance" (a tree, children under what they inherit from, an entry with two parents under both) and "A to Z", a Columns menu to choose the stats shown (the first four numeric ones to start with), and a count.
- **Own is told from inherited.** An inherited cell is muted and says where it comes from ("↳ Sword 1.5"); a cell nothing sets shows a dash. The place a value comes from is the nearest entry above with a value of its own, nearest first (`valueSource`, plain data). Under the grid the focused cell is explained, with "Go to Sword".
- **Every write is an ordinary command** (`stat.set`), so it shows at once, is undone by the entry's Undo, waits without a connection, and can conflict like any stat. A typed cell is read by its stat's type: whole numbers, decimals with a point or a comma ([ADR 0247](0247-bench-entry-editor-polish.md)), text, and On/Off or a choice of values for tags and choices. A value that cannot be read is said and not sent.
- **Keyboard first.** Arrows move; Shift extends the selection; Enter or F2 edits; typing replaces what is there; Delete makes the selected cells inherit; Escape clears; Ctrl+C copies the selection as tab-separated text and a paste writes tab-separated text from the focused cell. Clicking selects, Shift-click extends, double-click edits. With cells selected a bar offers a value to Set, − and + (whole numbers by 1, decimals by 0.1), Fill down (the top cell's value down each column of the selection) and Make inherit.
- **The reads.** There is no bulk read yet, so the grid reads every entry's detail, six at a time, quietly (`Bench.loadAll`), and says "Reading 14 of 120 entries…" while it does. That is fine for hundreds of entries and slow for thousands; K7 replaces it without a change to the grid.
- **A float opens inside the page.** A window floated from the palette is placed so its own width fits (it was always placed for a 460 pixel one).

## Not in scope

Pasting from the clipboard button in the design (the paste key works), drag-selecting with the pointer, resizing columns, a "Paste values" dialog, and stats that are worked out by formula as columns.

## Consequences

- A column of a stat nothing sets is all dashes, which is the point: it shows where it is missing.
