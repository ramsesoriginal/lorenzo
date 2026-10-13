# 0260 - Bench: dragging in the tree

Status: accepted

## Context

"Move to…" ([ADR 0244](0244-bench-link-buttons-and-move-to.md)) puts an entry under another by choosing from a list. In the explorer's tree the same thing is what a hand reaches for: take the row, put it on the entry it should hang under. [RFC 0042](../rfcs/0042-bench-workbench-interface.md) slice W-D kept it as the one open item.

## Decision

- **In the tree order, a row is dragged by its name** (an entry that can have parents: the kinds `PUT /entities/{id}/parents` accepts) and **dropped on another row**, which then is its parent. Nothing else changes: it is the same `entry.set-parents` command as "Move to…", one change, undone in one step.
- **The place it was dragged from is what is replaced.** An entry with several parents shows once under each, so the row dragged says which parent is meant: that parent is swapped for the target and the other parents stay. A row at the top level has none to swap, so the target is added.
- **Dropping on the empty part of the list takes the entry out of the place it was dragged from** (to the top level, if that was its only parent).
- **Only drops that make sense are accepted.** Not on itself or anything under it (a loop), not on a parent it already has; those rows do not light up and nothing is sent.
- Dragging is off while the filter is on or when the list is not the tree (by kind, A to Z): the rows there are not places in a tree. "Move to…" stays for the keyboard and for those orders.
- The decision is a function without a screen (`movedParents`), tested alone; the browser tests drag a row onto a row, onto what is under it, and onto the empty list.

## Consequences

- Dragging with a keyboard or a touch screen is not covered; "Move to…" is the way there.
- A drop onto a row that has not been opened yet opens it first, as any other command does.
